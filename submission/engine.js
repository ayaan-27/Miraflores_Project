import DATA from "./data.json" with {type:"json"};
export {DATA};
export const clone = value => structuredClone(value);
export const field = (doc,key) => {const v=doc?.fields?.[key]?.value;if(typeof v!=="string")throw Error(`Missing ${key} field.`);return v;};
export function cents(value){if(!/^\d{1,9}(?:\.\d{1,2})?$/.test(String(value)))throw Error("Use plain nonnegative USD amounts with at most two decimals.");const[a,b=""]=String(value).split(".");return Number(a)*100+Number(b.padEnd(2,"0"));}
export const dollars = n => (n/100).toFixed(2);
export const money = n => new Intl.NumberFormat("en-US",{style:"currency",currency:"USD"}).format(n/100);
export function parseLedger(text){
  text=text.replace(/^\uFEFF/,"").replace(/\r\n?/g,"\n");if(new TextEncoder().encode(text).length>1000000)throw Error("Keep the ledger under 1 MB.");
  const rows=[];let row=[],cell="",quoted=false;
  for(let i=0;i<=text.length;i++){const c=text[i]??"\n";if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(!quoted&&(c===","||c==="\n")){row.push(cell.trim());cell="";if(c==="\n"){if(row.some(Boolean))rows.push(row);row=[];}}else cell+=c;}
  if(quoted)throw Error("The CSV contains an unfinished quoted field.");
  const header=rows.shift()||[],required=["id","date","account","vendor","description","debit","credit","currency","document_id"];
  if([...header].sort().join()!==[...required].sort().join())throw Error("Use the sample ledger's nine column headers.");
  if(!rows.length||rows.length>2000)throw Error("Use 1–2,000 ledger rows.");
  const seen=new Set(),periods=new Set();
  const result=rows.map((values,i)=>{if(values.length!==9||values.some(v=>!v||v.length>300))throw Error(`Row ${i+2}: missing or oversized field.`);const r=Object.fromEntries(header.map((k,j)=>[k,values[j]]));if(!/^[\w-]{1,64}$/.test(r.id)||seen.has(r.id))throw Error(`Row ${i+2}: duplicate or invalid transaction ID.`);seen.add(r.id);
    const d=new Date(r.date+"T00:00:00Z");if(!/^\d{4}-\d{2}-\d{2}$/.test(r.date)||!Number.isFinite(d.getTime())||d.toISOString().slice(0,10)!==r.date)throw Error(`Row ${i+2}: invalid date.`);
    const period=r.date.slice(0,7);if(![DATA.catalog.period,DATA.catalog.previous_period].includes(period)||!DATA.catalog.accounts[r.account]||r.currency!=="USD")throw Error(`Row ${i+2}: use the supplied accounts, periods, and USD.`);periods.add(period);
    const debit=cents(r.debit),credit=cents(r.credit);if(Boolean(debit)===Boolean(credit))throw Error(`Row ${i+2}: enter either a debit or credit.`);r.amount_cents=debit-credit;return r;});
  if(periods.size!==2)throw Error("Include both September and October 2026.");return result;
}
export function allocation(amount,start,end,period="2026-10"){
  const valid=s=>{const d=new Date(s+"T00:00:00Z");if(!/^\d{4}-\d{2}-\d{2}$/.test(s)||!Number.isFinite(d.getTime())||d.toISOString().slice(0,10)!==s)throw Error("Invalid service date.");return d;};
  const a=valid(start),b=valid(end);if(start>end||a.getUTCDate()!==1||b.getUTCDate()!==new Date(Date.UTC(b.getUTCFullYear(),b.getUTCMonth()+1,0)).getUTCDate())throw Error("Partial-month or reversed service dates need manual review.");
  const first=a.getUTCFullYear()*12+a.getUTCMonth(),last=b.getUTCFullYear()*12+b.getUTCMonth(),count=last-first+1;
  if(count<1||count>60)throw Error("Service periods longer than 60 months need manual review.");
  const base=Math.floor(amount/count),extra=amount%count,rows=[];
  for(let i=0;i<count;i++){const m=first+i;rows.push({period:`${Math.floor(m/12)}-${String(m%12+1).padStart(2,"0")}`,expense_cents:base+Number(i<extra)});}
  return {rows,months:count,recognized_cents:rows.filter(r=>r.period<=period).reduce((s,r)=>s+r.expense_cents,0),current_expense_cents:rows.filter(r=>r.period===period).reduce((s,r)=>s+r.expense_cents,0),future_cents:rows.filter(r=>r.period>period).reduce((s,r)=>s+r.expense_cents,0)};
}
export function account(rows,code){const sum=period=>rows.filter(r=>r.account===code&&r.date.startsWith(period)).reduce((s,r)=>s+r.amount_cents,0),previous=sum("2026-09"),current=sum("2026-10"),change=current-previous;return {code,name:DATA.catalog.accounts[code],previous_cents:previous,current_cents:current,change_cents:change,material:Math.abs(change)>=500000&&(!previous||Math.abs(change)*5>=Math.abs(previous))};}
export function analyze(rows,code,docs){
  const a=account(rows,code),current=rows.filter(r=>r.account===code&&r.date.startsWith("2026-10")),previous=rows.filter(r=>r.account===code&&r.date.startsWith("2026-09"));
  const result={outcome:"hold",approval_allowed:false,account:a,findings:[],journal:[],allocation:[],adjustment_cents:0,adjusted_cents:a.current_cents,missing_document_id:null,driver:null,sources:{}};
  const add=(name,passed,detail,source_ids)=>result.findings.push({name,passed:Boolean(passed),detail,source_ids});
  result.sources.LEDGER={id:"LEDGER",kind:"Ledger extract",rows:[...previous,...current]};
  const duplicates=current.filter(r=>current.filter(x=>x.document_id===r.document_id).length>1);
  add("Posting uniqueness",!duplicates.length,duplicates.length?"Repeated source references need investigation.":"Each posting has a distinct source reference.",["LEDGER"]);if(duplicates.length)return result;
  const drivers=current.filter(r=>!previous.some(p=>p.vendor===r.vendor&&p.description===r.description&&p.amount_cents===r.amount_cents));
  const clear=drivers.length===1&&drivers[0].amount_cents===a.change_cents&&drivers[0].amount_cents>0;
  add("Variance bridge",clear,clear?"One additional posting accounts for the full movement.":"Multiple or changing components need manual review.",["LEDGER"]);if(!clear)return result;
  const driver=drivers[0];result.driver=driver;const invoice=docs[driver.document_id];
  if(!invoice){result.outcome="evidence_needed";result.missing_document_id=driver.document_id;add("Posting support",false,"The posting's source record is missing.",["LEDGER"]);return result;}
  result.sources[invoice.id]=invoice;
  const supported=field(invoice,"Entity")===DATA.catalog.entity&&field(invoice,"Vendor").toLowerCase()===driver.vendor.toLowerCase()&&field(invoice,"Currency")==="USD"&&cents(field(invoice,"Amount"))===driver.amount_cents;
  add("Posting support",supported,"Compare the entity, vendor, amount, and currency with the posting.",["LEDGER",invoice.id]);if(!supported)return result;
  const policy=docs["POL-CLOSE"];result.sources[policy.id]=policy;
  const policyOK=field(policy,"Basis")==="Accrual"&&field(policy,"Allocation")==="Equal monthly allocation over full calendar months";
  if(!policyOK){add("Close policy",false,"The supported accrual policy is unavailable.",[policy.id]);return result;}
  if(invoice.kind==="Payroll memo"){const ok=field(invoice,"Earned period")==="2026-10"&&field(invoice,"Approval")==="Approved"&&field(policy,"Bonuses")==="Expense in the earned period with approval";add("Earned-period support",ok,"The bonus memo must support the amount and the earned period.",[invoice.id,policy.id]);if(ok){result.outcome="explained";result.approval_allowed=true;}return result;}
  if(invoice.kind!=="Invoice")return result;
  const expected=field(invoice,"Agreement ID"),agreement=docs[expected];
  if(!agreement){result.outcome="evidence_needed";result.missing_document_id=expected;add("Service-period support",false,`${expected} is missing. Obtain the service dates before proposing a treatment.`,[invoice.id,policy.id]);return result;}
  result.sources[agreement.id]=agreement;
  const match=field(agreement,"Entity")===DATA.catalog.entity&&field(agreement,"Vendor").toLowerCase()===driver.vendor.toLowerCase()&&field(agreement,"Invoice ID")===driver.document_id&&field(agreement,"Currency")==="USD"&&cents(field(agreement,"Amount"))===driver.amount_cents&&field(agreement,"Authorized")==="Yes";
  add("Agreement match",match,"Check the agreement against the invoice and supplied authorization field.",[invoice.id,agreement.id]);if(!match)return result;
  let schedule;try{schedule=allocation(driver.amount_cents,field(agreement,"Service start"),field(agreement,"Service end"));}catch(e){add("Service allocation",false,e.message,[agreement.id,policy.id]);return result;}
  if(schedule.recognized_cents!==schedule.current_expense_cents){add("Prior-period effects",false,"The agreement affects an earlier close; manual review is required.",[agreement.id,policy.id]);return result;}
  const adjustment=driver.amount_cents>=cents(field(policy,"Prepaid threshold"))?schedule.future_cents:0;
  add("Service allocation",true,`${schedule.months} calendar month(s): ${money(schedule.current_expense_cents)} relates to October; ${money(schedule.future_cents)} relates to later periods.`,[agreement.id,policy.id]);
  Object.assign(result,{outcome:adjustment?"adjustment_proposed":"explained",approval_allowed:true,adjustment_cents:adjustment,adjusted_cents:a.current_cents-adjustment,allocation:schedule.rows});
  if(adjustment)result.journal=[{account:"1500",name:"Prepaid services",debit_cents:adjustment,credit_cents:0},{account:code,name:a.name,debit_cents:0,credit_cents:adjustment}];
  return result;
}
export class Review {
  constructor(ledger=DATA.ledger_csv){this.rows=parseLedger(ledger);this.docs=Object.fromEntries(Object.entries(clone(DATA.documents)).filter(([id])=>DATA.catalog.documents[id].available));this.cases={};}
  investigate(code){if(!account(this.rows,code).material)throw Error("This movement is below the review threshold.");return this.cases[code]={account_code:code,status:"awaiting_review",round:1,history:[],analysis:analyze(this.rows,code,this.docs),journal_posted:false};}
  decide(code,action,reviewer,note){const s=this.cases[code];if(!s||s.status!=="awaiting_review")throw Error("The case is not waiting for a review decision.");if(!["approve","hold","request_evidence"].includes(action))throw Error("Invalid review action.");if(reviewer.trim().length<2||note.trim().length<8)throw Error("Enter your name and a note of at least eight characters.");if(action==="approve"&&(!s.analysis.approval_allowed||s.analysis.findings.some(f=>!f.passed)))throw Error("Approval blocked: required support is unresolved.");if(action==="request_evidence"&&!s.analysis.missing_document_id)throw Error("No missing document is requested.");s.history.push({action,reviewer,note,round:s.round,at:new Date().toISOString()});s.status=action==="request_evidence"?"awaiting_evidence":action==="approve"?"approved":"held";return s;}
  addEvidence(code,record){const s=this.cases[code];if(!s||s.status!=="awaiting_evidence")throw Error("Request evidence before adding it.");const expected=s.analysis.missing_document_id,driver=s.analysis.driver;
    if(!record||record.id!==expected)throw Error(`This case is waiting for ${expected}.`);
    if(this.docs[record.id])throw Error("This source is already present.");
    if(field(record,"Entity")!==DATA.catalog.entity||field(record,"Vendor").toLowerCase()!==driver.vendor.toLowerCase()||field(record,"Currency")!=="USD"||cents(field(record,"Amount"))!==driver.amount_cents)throw Error("The source entity, vendor, currency, or amount does not match.");
    if(expected!==driver.document_id){if(record.kind!=="Service agreement"||field(record,"Invoice ID")!==driver.document_id||field(record,"Authorized").toLowerCase()!=="yes")throw Error("The agreement does not support this invoice.");allocation(driver.amount_cents,field(record,"Service start"),field(record,"Service end"));}
    const next={...this.docs,[record.id]:clone(record)},analysis=analyze(this.rows,code,next);this.docs=next;s.round++;s.analysis=analysis;s.status="awaiting_review";return s;}
}
