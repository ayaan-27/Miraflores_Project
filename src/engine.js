// Pure, deterministic matching and validation. All monetary comparisons use cents.
export const RULE_VERSION = '1.0.0';
export const MAX_BYTES = 500_000;
export const MAX_ROWS = 1000;

export class InputError extends Error {}

export function parseCSV(text) {
  if (typeof text !== 'string' || new TextEncoder().encode(text).length > MAX_BYTES) {
    throw new InputError('Each CSV must be 500 KB or smaller.');
  }
  text = text.replace(/^\uFEFF/, '');
  const rows = [];
  let row = [], field = '', quoted = false, closed = false;
  const pushField = () => { row.push(field.trim()); field = ''; closed = false; };
  const pushRow = () => { pushField(); if (row.some(x => x !== '')) rows.push(row); row = []; };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') { quoted = false; closed = true; }
      else field += c;
    } else if (c === '"') {
      if (field.length || closed) throw new InputError('Unexpected quote in CSV. Quote the entire field.');
      quoted = true;
    } else if (c === ',') pushField();
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      pushRow();
    } else {
      if (closed && !/\s/.test(c)) throw new InputError('Unexpected text after a closing CSV quote.');
      if (!closed) field += c;
    }
  }
  if (quoted) throw new InputError('Unclosed quote in CSV.');
  if (field || row.length || closed) pushRow();
  if (rows.length < 2) throw new InputError('Include a header and at least one data row.');
  if (rows.length > MAX_ROWS + 1) throw new InputError(`Limit each CSV to ${MAX_ROWS} data rows.`);
  const headers = rows.shift().map(x => x.toLowerCase());
  if (new Set(headers).size !== headers.length || headers.some(x => !x)) throw new InputError('CSV headers must be unique and nonempty.');
  return rows.map((values, i) => {
    if (values.length !== headers.length) throw new InputError(`Data row ${i + 1}: expected ${headers.length} columns, found ${values.length}.`);
    return Object.fromEntries(headers.map((key, j) => [key, values[j]]));
  });
}

export function cents(value) {
  if (!/^-?\d{1,9}(\.\d{1,2})?$/.test(value)) throw new InputError('Amounts must be signed USD numbers with up to two decimal places, e.g. 129.00. No currency symbols or commas.');
  const negative = value.startsWith('-');
  const [whole, fraction = ''] = value.replace(/^-/, '').split('.');
  const result = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  if (result === 0) throw new InputError('Zero-value transactions and receipts are outside this prototype.');
  return negative ? -result : result;
}

export function day(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new InputError('Dates must use YYYY-MM-DD.');
  const ms = Date.parse(value + 'T00:00:00Z');
  if (!Number.isFinite(ms) || new Date(ms).toISOString().slice(0, 10) !== value) throw new InputError(`Invalid calendar date: ${value}.`);
  return ms / 86400000;
}

export function normalize(value) {
  return value.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ').split(' ').filter(x => x && !['inc','llc','ltd','corp','co'].includes(x)).join(' ');
}

export function importCSV(text, kind) {
  if (!['bank', 'receipts'].includes(kind)) throw new InputError('Unknown source type.');
  const rows = parseCSV(text);
  const needed = kind === 'bank' ? ['id','date','description','amount'] : ['id','date','vendor','amount','reference'];
  for (const key of needed) if (!(key in rows[0])) throw new InputError(`Missing required ${kind} column: ${key}.`);
  const seen = new Set();
  return rows.map((row, i) => {
    try {
      for (const key of needed) if (!row[key]) throw new InputError(`${key} cannot be empty.`);
      for (const value of Object.values(row)) if (value.length > 500) throw new InputError('Fields must be 500 characters or shorter.');
      if (!/^[A-Za-z0-9_-]{1,50}$/.test(row.id)) throw new InputError('IDs must contain 1–50 letters, numbers, underscores, or hyphens.');
      if (seen.has(row.id)) throw new InputError(`Duplicate ID: ${row.id}. Use unique source IDs.`);
      seen.add(row.id);
      const merchant = row[kind === 'bank' ? 'description' : 'vendor'];
      if (!normalize(merchant)) throw new InputError('Merchant must contain letters or numbers.');
      return { id: row.id, date: row.date, merchant, amount: cents(row.amount), day: day(row.date), reference: row.reference || '', row: i + 2 };
    } catch (error) { throw new InputError(`${kind}, data row ${i + 1}: ${error.message}`); }
  });
}

function similarity(a, b) {
  const left = new Set(normalize(a).split(' ')), right = new Set(normalize(b).split(' '));
  return [...left].filter(x => right.has(x)).length / new Set([...left, ...right]).size;
}

function fingerprint(row) { return [row.date, normalize(row.merchant), row.amount].join('|'); }

export function analyze(bank, receipts, windowDays = 3) {
  if (!Number.isInteger(windowDays) || windowDays < 0 || windowDays > 7) throw new InputError('Date tolerance must be a whole number from 0 to 7 days.');
  const counts = new Map();
  bank.forEach(row => counts.set(fingerprint(row), (counts.get(fingerprint(row)) || 0) + 1));
  const preliminary = bank.map(tx => ({ ...tx, candidates: receipts.filter(r => r.amount === tx.amount && Math.abs(r.day - tx.day) <= windowDays && similarity(tx.merchant, r.merchant) >= 0.5)
    .map(r => ({ ...r, exact: normalize(r.merchant) === normalize(tx.merchant), daysApart: Math.abs(r.day - tx.day) }))
    .sort((a,b) => Number(b.exact) - Number(a.exact) || a.daysApart - b.daysApart || a.id.localeCompare(b.id)) }));
  const uses = new Map();
  preliminary.forEach(t => t.candidates.forEach(r => uses.set(r.id, (uses.get(r.id) || 0) + 1)));
  return preliminary.map(tx => {
    const duplicate = counts.get(fingerprint(tx)) > 1;
    const conflict = tx.candidates.some(r => uses.get(r.id) > 1);
    const exact = tx.candidates.length === 1 && tx.candidates[0].exact;
    let status, reason, code;
    if (duplicate) { status = 'review'; code = 'DUPLICATE_BANK'; reason = 'Same merchant, date, and amount appear more than once in the bank file. Confirm these are distinct charges.'; }
    else if (conflict) { status = 'review'; code = 'SHARED_RECEIPT'; reason = 'A candidate receipt also matches another bank transaction. One receipt cannot support two charges.'; }
    else if (exact) { status = 'ready'; code = 'EXACT_MATCH'; reason = 'One receipt matches the normalized merchant and exact signed amount within the date tolerance.'; }
    else if (tx.candidates.length > 1) { status = 'review'; code = 'MULTIPLE_RECEIPTS'; reason = 'Multiple receipts meet the matching rules. A reviewer must choose the correct evidence.'; }
    else if (tx.candidates.length === 1) { status = 'review'; code = 'PARTIAL_VENDOR'; reason = 'Amount and date match, but merchant names overlap only partially. Confirm the vendor.'; }
    else { status = 'missing'; code = 'NO_MATCH'; reason = 'No receipt meets all rules: exact signed amount, merchant overlap, and date tolerance. Request evidence or explain an exclusion.'; }
    return { ...tx, status, reason, code, duplicate, conflict, matchedId: status === 'ready' ? tx.candidates[0].id : null };
  });
}

export function applyDecisions(analysis, decisions = {}) {
  const ids = new Set(analysis.map(t => t.id));
  for (const id of Object.keys(decisions)) if (!ids.has(id)) throw new InputError(`Unknown transaction decision: ${id}.`);
  const chosen = new Map();
  const rows = analysis.map(tx => {
    const d = decisions[tx.id];
    if (!d) return { ...tx, decision: null };
    if (!['approve','exclude','request'].includes(d.action)) throw new InputError('Invalid reviewer action.');
    if (typeof d.note !== 'string' || d.note.trim().length < 5 || d.note.length > 1000) throw new InputError('Add a reviewer note of 5–1000 characters.');
    if (d.action === 'approve') {
      if (!tx.candidates.some(r => r.id === d.receiptId)) throw new InputError(`Receipt is not a valid candidate for ${tx.id}.`);
      chosen.set(tx.id, d.receiptId);
      return { ...tx, status: 'approved', matchedId: d.receiptId, decision: d };
    }
    return { ...tx, status: d.action === 'exclude' ? 'excluded' : 'requested', matchedId: null, decision: d };
  });
  const allocated = new Set();
  for (const tx of rows) {
    const receiptId = chosen.get(tx.id) || tx.matchedId;
    if (!receiptId) continue;
    if (allocated.has(receiptId)) throw new InputError(`Receipt ${receiptId} is already allocated. Undo the other decision before assigning it again.`);
    allocated.add(receiptId);
  }
  return rows;
}

export function summarize(rows) {
  const resolved = rows.filter(t => ['ready','approved','excluded'].includes(t.status));
  const outstanding = rows.filter(t => !['ready','approved','excluded'].includes(t.status));
  return { total: rows.length, resolved: resolved.length, outstanding: outstanding.length,
    exposure: outstanding.reduce((sum,t) => sum + Math.abs(t.amount), 0),
    ready: rows.filter(t => ['ready','approved'].includes(t.status)).length,
    review: rows.filter(t => t.status === 'review').length,
    missing: rows.filter(t => ['missing','requested'].includes(t.status)).length,
    excluded: rows.filter(t => t.status === 'excluded').length };
}

export function money(value) { return new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format(value / 100); }

// Prefix spreadsheet formulas before RFC 4180 escaping; source text remains intact in JSON.
export function safeCell(value) {
  let s = String(value ?? '');
  if (/^[\s]*[=+\-@]/.test(s)) s = "'" + s;
  return '"' + s.replaceAll('"', '""') + '"';
}

export function reviewCSV(rows) {
  const header = ['transaction_id','date','merchant','amount_usd','status','receipt_id','evidence_reference','rule','rule_version','reason','reviewer_note','decision_at'];
  return [header, ...rows.map(t => [t.id,t.date,t.merchant,(t.amount/100).toFixed(2),t.status,t.matchedId || '',t.candidates.find(r => r.id === t.matchedId)?.reference || '',t.code,RULE_VERSION,t.reason,t.decision?.note || '',t.decision?.at || ''])].map(row => row.map(safeCell).join(',')).join('\r\n');
}

export function clientRequest(rows, client = 'Cedar & Finch Studio') {
  const open = rows.filter(t => !['ready','approved','excluded'].includes(t.status));
  return `Subject: Month-end evidence request — ${client}\n\nHi ${client} team,\n\n${open.length ? 'Please help us clarify the following transactions so we can complete the evidence review:' : 'There are no outstanding evidence requests for the imported transactions.'}\n\n` + open.map((t,i) => `${i+1}. ${t.date} · ${t.merchant} · ${money(t.amount)} [${t.id}]\n   ${t.code === 'DUPLICATE_BANK' ? 'Please confirm whether these repeated charges are distinct and provide a receipt for each.' : t.candidates.length ? 'Please confirm the correct receipt and explain the merchant or duplicate-charge ambiguity.' : 'Please provide a receipt or invoice and the business purpose.'}${t.decision?.note ? '\n   Reviewer note: ' + t.decision.note : ''}`).join('\n\n') + '\n\nThank you.\n\nDraft for human review. No message has been sent.\n';
}
