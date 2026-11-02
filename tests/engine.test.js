import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { importCSV, analyze, applyDecisions, summarize, cents, day, parseCSV, reviewCSV, clientRequest, normalize } from '../src/engine.js';
const sample = name => readFileSync(new URL(`../samples/${name}.csv`, import.meta.url),'utf8');
const bank=importCSV(sample('bank'),'bank'), receipts=importCSV(sample('receipts'),'receipts');
const analysis=analyze(bank,receipts);
const note={note:'Verified against original invoice.',at:'2026-11-02T00:00:00.000Z'};

test('representative sample has exact expected outcomes and exposure',()=>{
  assert.deepEqual(summarize(analysis),{total:12,resolved:6,outstanding:6,exposure:59350,ready:6,review:4,missing:2,excluded:0});
  assert.equal(analysis.find(t=>t.id==='B004').code,'PARTIAL_VENDOR');
  assert.equal(analysis.find(t=>t.id==='B012').matchedId,'R010');
  assert.equal(analysis.find(t=>t.id==='B008').code,'MULTIPLE_RECEIPTS');
});
test('confirming a partial match resolves one item and leaves original reason',()=>{
  const result=applyDecisions(analysis,{B004:{...note,action:'approve',receiptId:'R004'}});
  assert.equal(result.find(t=>t.id==='B004').status,'approved');
  assert.equal(result.find(t=>t.id==='B004').code,'PARTIAL_VENDOR');
  assert.equal(summarize(result).exposure,54500);
  assert.equal(summarize(result).outstanding,5);
});
test('shared receipt never auto matches and cannot be approved twice',()=>{
  assert.equal(analysis.find(t=>t.id==='B005').code,'SHARED_RECEIPT');
  assert.equal(analysis.find(t=>t.id==='B006').status,'review');
  assert.throws(()=>applyDecisions(analysis,{B005:{...note,action:'approve',receiptId:'R005'},B006:{...note,action:'approve',receiptId:'R005'}}),/already allocated/);
});
test('requested stays outstanding, exclusions resolve with a note, undo is recomputable',()=>{
  const result=applyDecisions(analysis,{B009:{...note,action:'request'},B011:{...note,action:'exclude'}});
  assert.equal(result.find(t=>t.id==='B009').status,'requested');
  assert.equal(summarize(result).outstanding,5);
  assert.equal(summarize(result).excluded,1);
  assert.equal(summarize(applyDecisions(analysis,{})).outstanding,6);
});
test('invalid import is rejected, including duplicate IDs in supplied difficult sample',()=>{
  assert.throws(()=>importCSV(sample('invalid-bank'),'bank'),/Duplicate ID/);
  assert.throws(()=>importCSV('date,description,amount\n2026-09-01,Foo,1','bank'),/column: id/);
  assert.throws(()=>importCSV('id,date,description,amount\nA,2026-02-30,Foo,1','bank'),/Invalid calendar/);
  assert.throws(()=>importCSV('id,date,description,amount\nA,2026-02-01,Foo,NaN','bank'),/Amounts/);
});
test('dates and integer cents reject rollover, floating ambiguity, symbols and excessive precision',()=>{
  assert.equal(cents('0.10')+cents('0.20'),30);
  assert.equal(cents('-45.00'),-4500);
  for(const n of ['1.001','$2.00','1,000.00','Infinity','0','1e3'])assert.throws(()=>cents(n));
  assert.equal(day('2024-02-29')+1,day('2024-03-01'));
  for(const d of ['2026-02-29','2026-13-01','09/01/2026'])assert.throws(()=>day(d));
});
test('CSV accepts BOM, CRLF, embedded commas, escaped quotes, multiline and blank lines',()=>{
  assert.deepEqual(parseCSV('\uFEFFa,b\r\n"hello, \"\"world\"\"","line1\nline2"\r\n\r\n'),[{a:'hello, "world"',b:'line1\nline2'}]);
  for(const csv of ['a,a\n1,2','a,b\n"open,2','a,b\n1,2,3','a,b\n"x"oops,2'])assert.throws(()=>parseCSV(csv));
});
test('vendor normalization is conservative; amount alone and opposite signs never match',()=>{
  assert.equal(normalize('Fígma, Inc.'),'figma');
  const b=importCSV('id,date,description,amount\nB,2026-09-01,Figma,15','bank');
  const r=importCSV('id,date,vendor,amount,reference\nR,2026-09-01,Adobe,15,x\nS,2026-09-01,Figma,-15,y','receipts');
  assert.equal(analyze(b,r)[0].status,'missing');
});
test('date window boundary is inclusive and adjustable',()=>{
  const b=importCSV('id,date,description,amount\nB,2026-09-04,Figma,15','bank');
  const r=importCSV('id,date,vendor,amount,reference\nR,2026-09-01,Figma,15,x','receipts');
  assert.equal(analyze(b,r,3)[0].status,'ready');
  assert.equal(analyze(b,r,1)[0].status,'missing');
  assert.throws(()=>analyze(b,r,-1));
});
test('duplicate bank records and duplicate receipt records are not resolved automatically',()=>{
  const b=importCSV('id,date,description,amount\nB,2026-09-01,Figma,15\nC,2026-09-01,Figma Inc,15','bank');
  const r=importCSV('id,date,vendor,amount,reference\nR,2026-09-01,Figma,15,x','receipts');
  assert.ok(analyze(b,r).every(t=>t.code==='DUPLICATE_BANK'));
  const rr=importCSV('id,date,vendor,amount,reference\nR,2026-09-01,Figma,15,x\nS,2026-09-01,Figma,15,x','receipts');
  assert.equal(analyze(b.slice(0,1),rr)[0].code,'MULTIPLE_RECEIPTS');
});
test('bad reviewer decisions and short notes cannot bypass matching rules',()=>{
  assert.throws(()=>applyDecisions(analysis,{B009:{...note,action:'approve',receiptId:'R001'}}),/not a valid candidate/);
  assert.throws(()=>applyDecisions(analysis,{B009:{action:'exclude',note:'no'}}),/reviewer note/);
  assert.throws(()=>applyDecisions(analysis,{NOPE:{...note,action:'exclude'}}),/Unknown transaction/);
});
test('exports preserve provenance, guard spreadsheet formulas and omit resolved request items',()=>{
  const result=applyDecisions(analysis,{B004:{...note,action:'approve',receiptId:'R004'}});
  const csv=reviewCSV(result);
  assert.match(csv,/team-coffee-receipt.jpg/);assert.match(csv,/PARTIAL_VENDOR/);
  assert.match(reviewCSV([{...analysis[0],merchant:'=WEBSERVICE("evil")'}]),/'=WEBSERVICE/);
  const draft=clientRequest(result);assert.match(draft,/B009/);assert.doesNotMatch(draft,/B004/);assert.match(draft,/No message has been sent/);
});
test('file size and row limits stop oversized imports',()=>{
  assert.throws(()=>parseCSV('x'.repeat(500001)),/500 KB/);
  assert.throws(()=>parseCSV('id,date,description,amount\n'+'A,2026-01-01,Foo,1\n'.repeat(1001)),/1000/);
});
