"""Build and execute the standalone standard-library notebook. No remote services."""
import contextlib,io,json,os,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def markdown(s):return {'cell_type':'markdown','metadata':{},'source':s.splitlines(True)}
def code(s):return {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':s.splitlines(True)}
cells=[markdown('''# Month-end review
Run all cells in any Python 3.10+ Jupyter environment. No installation, model, API key, server, or network call is required. All inputs and implementation are embedded below. Saved outputs show an executed walkthrough.

The four stages are detect → check evidence → calculate treatment → human review. This is a rules-based workflow using synthetic ledger and structured evidence records, not document extraction or LLM inference. The automated reviewer below is explicitly a demonstration; use OPEN_THIS.html for interactive human decisions. No emails or accounting entries are sent.''')]
data=(ROOT/'submission/data.json').read_text()
cells.append(code('import json\nDATA=json.loads('+repr(data)+')\n'+(ROOT/'submission/workflow.py').read_text()))
cells.append(code('''review=Review()
print("1. Find material movements")
for a in review.workspace.accounts():
    print(a["code"],a["name"],"September",dollars(a["previous_cents"]),"October",dollars(a["current_cents"]),"review",a["material"])
state=review.investigate("6100")
print("\\n2. Check evidence:",state["analysis"]["outcome"])
for f in state["analysis"]["findings"]: print("PASS" if f["passed"] else "UNRESOLVED",f["name"],f["detail"])
assert state["analysis"]["missing_document_id"]=="AGR-SW-2026"
'''))
cells.append(code('''# A request pauses this case. Invalid evidence must not change it.
try:
    review.decide("approve","Demo reviewer","Attempt without the required support")
    raise AssertionError("Approval should be blocked")
except ValueError as e: print("Blocked:",e)
review.decide("request_evidence","Demo reviewer (automated walkthrough)","Please supply the authorized service agreement for this invoice.")
before=deepcopy(review.state)
try:
    review.add_evidence(DATA["documents"]["AGR-SW-WRONG"])
    raise AssertionError("Mismatched evidence should be rejected")
except ValueError as e: print("Rejected:",e)
assert review.state==before
print("Pending case and prior review preserved.")
'''))
cells.append(code('''state=review.add_evidence(DATA["documents"]["AGR-SW-2026"])
a=state["analysis"]
print("3. Recalculate treatment after matching evidence")
print("Annual service:",dollars(a["driver"]["amount_cents"]))
print("Proposed deferral:",dollars(a["adjustment_cents"]))
print("Adjusted October expense:",dollars(a["adjusted_cents"]))
assert a["adjustment_cents"]==2200000 and a["adjusted_cents"]==400000
assert sum(r["expense_cents"] for r in a["allocation"])==2400000
assert sum(j["debit_cents"] for j in a["journal"])==sum(j["credit_cents"] for j in a["journal"])
for j in a["journal"]: print(j["account"],j["name"],"debit",dollars(j["debit_cents"]),"credit",dollars(j["credit_cents"]))
print("4. New review required:",state["status"],"round",state["round"])
state=review.decide("approve","Demo reviewer (automated walkthrough)","Service dates and policy checked; approve workpaper only. No posting.")
assert len(state["history"])==2 and not state["journal_posted"]
print("Workpaper",state["status"],"— journal not posted")
'''))
cells.append(code('''payroll=Review(); bonus=payroll.investigate("6200")
assert bonus["analysis"]["outcome"]=="explained" and not bonus["analysis"]["journal"]
print("Payroll: approved October bonus explains USD 18,000; no adjustment.")
fees=Review(); fees.investigate("6300")
fees.decide("request_evidence","Demo reviewer","Please provide the consulting service dates.")
fee=fees.add_evidence(DATA["documents"]["AGR-FEE-2026"])
assert fee["analysis"]["outcome"]=="explained" and not fee["analysis"]["journal"]
print("Consulting: current-month service; no deferral.")
rows=DATA["ledger_csv"].splitlines(); invalid="\\n".join(rows+[rows[1]])
try:
    Review(invalid.encode()); raise AssertionError("Duplicate ID should fail")
except ValueError as e: print("Invalid ledger rejected:",e)
assert sum(r["expense_cents"] for r in schedule(10000,"2026-10-01","2026-12-31","2026-10")["rows"])==10000
print("Cent rounding preserves the full amount.")
'''))
cells.append(code('''from html import escape
out=Path("review-outputs"); out.mkdir(exist_ok=True)
(out/"review.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
with (out/"proposed-journal.csv").open("w",newline="",encoding="utf-8") as f:
    writer=csv.writer(f); writer.writerow(["account","name","debit_usd","credit_usd","status"])
    for j in state["analysis"]["journal"]: writer.writerow([j["account"],j["name"],dollars(j["debit_cents"]),dollars(j["credit_cents"]),"Proposed only; workpaper approved"])
(out/"workpaper.html").write_text('<!doctype html><meta charset="utf-8"><title>Month-end workpaper</title><h1>Month-end workpaper</h1><p>Synthetic sample. Automated walkthrough decision. No journal posted.</p><pre>'+escape(json.dumps(state,indent=2))+'</pre>',encoding="utf-8")
print("Exported review-outputs/review.json, proposed-journal.csv, workpaper.html")
'''))
namespace={}
with tempfile.TemporaryDirectory() as temp:
    previous=os.getcwd();os.chdir(temp)
    try:
        count=0
        for cell in cells:
            if cell['cell_type']!='code':continue
            count+=1;buffer=io.StringIO()
            with contextlib.redirect_stdout(buffer):exec(''.join(cell['source']),namespace)
            cell['execution_count']=count
            cell['outputs']=[{'output_type':'stream','name':'stdout','text':buffer.getvalue().splitlines(True)}] if buffer.getvalue() else []
        import shutil
        shutil.copytree('review-outputs',ROOT/'submission/example-outputs',dirs_exist_ok=True)
    finally:os.chdir(previous)
notebook={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.12'}},'nbformat':4,'nbformat_minor':5}
for cell in cells:
    import hashlib
    cell['id']=hashlib.sha256(''.join(cell['source']).encode()).hexdigest()[:10]
(ROOT/'submission/Month_end_review.ipynb').write_text(json.dumps(notebook,indent=1))
# Keep the old notebook link useful, without a bootstrap or tunnel.
(ROOT/'notebooks/Month_end_review.ipynb').write_text(json.dumps(notebook,indent=1))
print('Standalone notebook executed: expected 22,000 deferral, 4,000 adjusted expense, controls and exports passed.')
