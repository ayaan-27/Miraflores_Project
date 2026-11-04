import test from 'node:test';
import assert from 'node:assert/strict';
import {DATA,Review,clone,allocation,parseLedger} from '../submission/engine.js';
test('Missing support blocks approval; wrong evidence preserves state; matching evidence resumes and calculates',()=>{
 const r=new Review();let s=r.investigate('6100');assert.equal(s.analysis.missing_document_id,'AGR-SW-2026');
 assert.throws(()=>r.decide('6100','approve','Reviewer','Approve without evidence'),/blocked/);
 r.decide('6100','request_evidence','Reviewer','Please supply service agreement');const before=clone(s);
 assert.throws(()=>r.addEvidence('6100',DATA.documents['AGR-SW-WRONG']),/waiting/);assert.deepEqual(s,before);
 const wrong=clone(DATA.documents['AGR-SW-2026']);wrong.fields.Vendor.value='Other vendor';assert.throws(()=>r.addEvidence('6100',wrong),/match/);assert.deepEqual(s,before);
 s=r.addEvidence('6100',DATA.documents['AGR-SW-2026']);assert.equal(s.analysis.adjustment_cents,2200000);assert.equal(s.analysis.adjusted_cents,400000);assert.equal(s.round,2);assert.equal(s.history.length,1);assert.equal(s.status,'awaiting_review');
 assert.equal(s.analysis.journal.reduce((n,j)=>n+j.debit_cents-j.credit_cents,0),0);r.decide('6100','approve','Reviewer','Checked service dates and draft journal');assert.equal(s.status,'approved');assert.equal(s.journal_posted,false);assert.equal(s.history.length,2);
});
test('Legitimate bonus and current-month consulting produce no adjustment',()=>{
 const r=new Review();assert.equal(r.investigate('6200').analysis.outcome,'explained');assert.equal(r.cases['6200'].analysis.journal.length,0);r.investigate('6300');r.decide('6300','request_evidence','Reviewer','Please supply consulting dates');const s=r.addEvidence('6300',DATA.documents['AGR-FEE-2026']);assert.equal(s.analysis.outcome,'explained');assert.equal(s.analysis.adjustment_cents,0);assert.throws(()=>r.investigate('6400'),/threshold/);
});
test('CSV rejects duplicate IDs and invalid dates; allocation preserves cents and holds partial months',()=>{
 const rows=DATA.ledger_csv.trim().split('\n');assert.throws(()=>parseLedger([...rows,rows[1]].join('\n')),/duplicate/);assert.throws(()=>parseLedger(DATA.ledger_csv.replace('2026-09-25','2026-09-31')),/date/);
 const s=allocation(10000,'2026-10-01','2026-12-31');assert.deepEqual(s.rows.map(r=>r.expense_cents),[3334,3333,3333]);assert.throws(()=>allocation(10000,'2026-10-02','2026-12-31'),/Partial/);
});
