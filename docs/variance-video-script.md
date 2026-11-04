# Month-end review — video narration

Target: 7–9 minutes. Bracketed directions are screen actions, not spoken words. Record the actual Streamlit app, not `variance_tests/serve_fixture.py`. Use only statements about your experience and review that you can stand behind.

## Before recording

- Open the deployed Streamlit application or run `streamlit_app.py` locally. Use **Import ledger → Reset sample** for a fresh workspace.
- Have `variance_samples/software-contract.pdf`, `wrong-contract.pdf`, and `invalid-ledger.csv` available. The app can also load its sample agreement directly.
- Rehearse the Software case once so the model download is complete. Real inference can take time on CPU. If you shorten a wait in the edit, add a visible “Inference wait shortened” caption; keep the actual actions and results.
- Keep the source README and validation evidence available in another tab. All transactions, documents, and the company are synthetic.

## 0:00–0:50 — Introduce the problem

[Show the initial account view.]

“Hi, I'm Ayaan. I built a month-end variance investigator for this case study.

The problem I chose is the work between noticing an account movement and writing a defensible explanation for it. Retrieving a balance is one step. A reviewer still needs to find the transaction, locate its support, understand the accounting treatment, and decide whether an action is justified.

I haven't observed GreenGrowth's internal close process. This is a hypothesis to test using a narrow workflow and synthetic records.”

## 0:50–1:50 — Explain your thought process

[Point to Software's September, October, and Change figures.]

“I have worked on text-to-SQL agents and document-retrieval systems. That experience motivated me to combine structured queries with supporting documents: a plausible explanation should have an inspectable route back to its evidence.

I also considered coordinating audit evidence requests and preparing safer evaluation datasets. I chose variance investigation because I could demonstrate one complete handoff from account movement to reviewed workpaper.

My starting question was: what would let someone move from ‘this changed’ to a useful next step? That led me to four stages: detect, investigate, verify, and review. Missing evidence should return to the same case, preserve the request, and cause the calculations to run again.”

## 1:50–3:10 — Start the real investigation

[Click Investigate. While the model runs, explain the architecture; when it completes, inspect Evidence and Activity.]

“Software expense increased from two thousand dollars in September to twenty-six thousand dollars in October. The account passes the sample materiality threshold.

The first stage calculates the movement from the actual CSV ledger. The second stage uses LangGraph and a local model to choose read-only evidence tools. Those tools query SQLite, compare vendors, and read the posting document, agreement, and close policy.

The model chooses among the remaining permitted tools after observing the results. Required evidence checks and an eight-decision limit constrain the investigation. It cannot issue arbitrary SQL or write to the ledger.

The model runs on the application's server without an inference API key. I chose a small model so the demo could run economically. The main design contribution is the workflow and its controls; the inference component is replaceable.”

[Open the posting PDF's Evidence expander. Show its source fields/quotes and optionally Preview.]

“The additional twenty-four-thousand-dollar posting is a workspace license renewal. This PDF reader uses labeled fields and preserves exact page quotes. General document extraction and OCR are outside this version.

The invoice description suggests an annual renewal, but it doesn't supply the service dates. The system doesn't infer those dates from that description.”

## 3:10–4:10 — Show the missing-evidence handoff

[Return to Findings. Show the missing-support finding and disabled Approve workpaper button.]

“The case stops at a useful boundary: it needs the agreement before proposing an accounting treatment. A large movement alone isn't proof of an error.

The third stage uses conventional code to check the variance bridge, posting support, policy, and dates. The model can draft an explanation, but it cannot change the calculated amounts or allowed reviewer actions.

I'll enter my name and request the missing service agreement.”

[Enter your name. Review note: `Please supply the renewal agreement and its service dates.` Click Request evidence.]

“The graph pauses at a saved checkpoint. The editable request is a draft; no email is sent. The reviewer name is entered for this demo, not authenticated.”

## 4:10–5:20 — Demonstrate an invalid reply and a valid reply

[Upload `wrong-contract.pdf`, then click Add evidence.]

“This is a real PDF, but it doesn't match the document required for this case. It is rejected before changing the evidence. The previous request remains intact.”

[Replace it with `software-contract.pdf` and click Add evidence, or use Use sample agreement.]

“Now I'll supply the correct agreement. It matches the entity, vendor, invoice, currency, and amount, and supplies the service period.

The same LangGraph thread resumes and reruns the investigation. The earlier request stays in its history. This is why I used a stateful workflow: new evidence should change an existing case through an explicit transition.”

## 5:20–6:30 — Explain and review the calculation

[Show the proposed journal and expand Allocation schedule.]

“The agreement covers twelve full calendar months, beginning in October. Under the supplied sample policy, two thousand dollars belongs to October and twenty-two thousand dollars relates to later periods.

The proposed entry debits prepaid services and credits software expense by twenty-two thousand dollars. October software expense would become four thousand dollars: the original two thousand of recurring costs, plus two thousand for the renewal.

Those are code-calculated amounts. Allocation uses integer cents, rounding preserves the contract total, and the proposed journal must balance. Partial months, prior-period effects, and inconsistent sources remain unresolved for manual review.

I'll review the support and approve the workpaper.”

[Enter a new note: `Reviewed the agreement, allocation, and balanced proposed journal.` Click Approve workpaper.]

“Approving the workpaper records the decision. The journal remains a draft; nothing is posted.”

## 6:30–7:15 — Show outputs and a legitimate variance

[Download Workpaper PDF, Journal CSV, and Review record. Open the PDF briefly. Select Payroll and Investigate. Shorten a wait only with a visible caption.]

“The output includes the workpaper, balanced draft journal, and a detailed review record with sources and decisions.

The payroll example makes a different point. Expense increases from forty thousand to fifty-eight thousand dollars. An approved October bonus memo supports that additional eighteen thousand. The movement is explained, and the system proposes no adjustment. A human still reviews the conclusion.”

## 7:15–8:30 — Explain limits and what you would learn

[Return to the completed Software case or its workpaper.]

“The prototype runs real queries, PDF reading, model inference, calculations, checkpoints, and review actions. The ledger, documents, business, and policy are synthetic. It doesn't connect to a production accounting system, verify document authenticity, or authenticate reviewers. Temporary hosting storage is not a durable audit archive.

The scope is deliberately narrow: a two-month USD expense review where one positive posting explains a material movement. More complex movements remain on hold.

I would next observe three close reviewers using consented, redacted examples. I'd compare this workflow with saved ledger filters and a spreadsheet checklist. I'd measure total review time, incorrect evidence assignments, unsupported explanations, and reopened cases.

My provisional target would be twenty-five percent less reviewer time without increasing incorrect recommendations. That's a target to test, not an achieved saving. If preparing the inputs or checking the model costs more effort than it saves, I would simplify or change direction.

I used an AI coding assistant for implementation, testing, and drafting, and checked the results with exact expected calculations, invalid inputs, workflow tests, and real-model runs. The source and README explain the dependencies, sample inputs, expected outputs, and limitations.”

## Follow-up answers

**Why not just use a spreadsheet?** “That is the baseline. The graph is useful if retaining evidence requests and resuming supported investigations saves effort. If a checklist performs equally well, I would use it.”

**What makes this agentic?** “The model chooses evidence queries from observed results within a LangGraph tool loop. The graph also has a verifier and human/evidence interrupts. Financial treatment and permissions remain conventional code.”

**Why this model?** “It makes a keyless CPU demo feasible. I would evaluate stronger models against the same extraction, query, and explanation checks before changing the provider.”

**What if the contract covers another period?** “The code recalculates supported full-month allocations. Partial months and prior-period effects are held for manual review. Start a fresh sample workspace to test different evidence without replacing an already-used source.”

**Can it post entries?** “No. It produces a balanced draft journal and records a workpaper decision. Posting and external communications are outside the prototype.”
