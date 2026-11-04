# LedgerLens v2 — video narration and screen actions

Target: 7–9 minutes after editing inference waits. Bracketed directions are screen actions, not spoken words. Read this in your own voice and retain personal statements you can stand behind. This script describes the agentic invoice investigator, not the earlier receipt-matching prototype.

## Before recording

- Open https://ayaan-27.github.io/Miraflores_Project/ in a modern desktop browser. This script describes public mode honestly. Keep the source README and passing Ollama validation link available in another tab.
- Have `agent_samples/remaining-delivery.pdf` available. Use synthetic documents only.
- Public mode requires no model download. To record the full local Ollama version, follow `docs/agent-upgrade.md` and adapt the mode descriptions below. Label edits that shorten actual inference waits.
- Do not use `backend_tests.serve_fixture` for the recorded product demo: it is a test double.
- Run one rehearsal. For a fresh recording, start a new investigation; retained prior runs stay in Run history.

## 0:00–0:45 — Introduce the problem

[Show the invoice-investigation workspace and its four stages.]

“Hi, I'm Ayaan. I built LedgerLens, an invoice exception investigation prototype for this case study, with GreenGrowth CPAs as the intended audience.

This public demo runs the business workflow in the browser using template extraction and a fixed evidence checklist. The source also contains the model-driven LangGraph and Ollama implementation, which passed a separate real-inference check.

The situation I focused on is an invoice that agrees with its purchase order but is not fully supported by receiving evidence. A warning alone doesn't resolve that situation. A reviewer needs to know which records were checked, what is missing, and what evidence would let the case move forward.

I haven't observed GreenGrowth's internal workflow. This is a hypothesis to test, using synthetic records.”

## 0:45–1:45 — Explain how you thought about it

[Point to the workflow stages; briefly open Workflow & boundaries.]

“My experience working on document retrieval at Ricoh motivated my interest in connecting an answer to its supporting material. I also considered cross-database analytics and safer data sharing, which relate to other work I've done.

I chose invoice investigation because I could build a complete, narrow workflow: understand an invoice, look for evidence, challenge the conclusion, and reach a documented next step.

My starting question was: what work happens after an exception is flagged? That led me to four stages and an evidence-response loop. If someone supplies a missing document, the same case should resume, retain the previous decision, and rerun the relevant checks.

I used LangGraph for the state, conditional execution, checkpoints, and human pause. Ollama runs the model locally without an API key. I can change that model through configuration; the investigation workflow stays the same.”

## 1:45–2:45 — Start a real investigation

[Close the workflow dialog. Choose “An invoice ahead of delivery.” Inspect the sample invoice PDF, then click Start investigation.]

“This invoice is from a fictional supplier, Marigold Office. It bills ten thousand dollars for one hundred lamps.

Stage one reads text from the actual PDF. The public version extracts uniquely labeled fields and preserves exact source lines. Ambiguous or missing fields stop the case. The local model version uses schema-constrained extraction and bounded source-grounded repair.

Stage two runs read-only evidence tools for the purchase order, receiving records, vendor master, prior payments, and control policy. Public mode uses a fixed five-query checklist. In the local LangGraph version, the model chooses the next tool after seeing previous results, subject to mandatory coverage and bounded execution.

The tools execute against synthetic business records. These are implemented queries, but they are not integrations with a real accounting system.”

[Open Execution trace. Show actual queries and returned source IDs.]

## 2:45–3:45 — Explain the finding and its controls

[When the run pauses for review, show the two amount cards, receiving control, and source citations. Open the receiving source.]

“The purchase order supports one hundred lamps, but the receiving report supports only eighty. At one hundred dollars each, eight thousand dollars has receiving support and two thousand dollars is missing that support.

This is not a loss estimate or a payment instruction. It explains why this invoice is held.

Stage three recomputes financial checks in ordinary code: integer cents in the browser, and decimal arithmetic in Python. Public mode prepares a template narrative. The local version uses a model-drafted verifier memo whose recommendation and source IDs are checked. The controls govern which review actions are allowed.

The source buttons let the reviewer inspect the supporting records, and the trace shows what the system actually checked.”

## 3:45–4:45 — Show the human gate and request

[Show the disabled Recommend release button. Open Evidence-request draft, read a sentence, then close it. Enter your name and a note, and click Request more evidence.]

Suggested note: `Please provide receiving evidence for the remaining 20 lamps on PO-7710.`

“Stage four pauses for a human decision. Recommending release is blocked while a required control fails. The local backend enforces the same restriction through its API.

The reviewer can record a hold or request additional evidence. Here, I want the receiving report for the remaining twenty lamps. The application prepares an editable request draft; it doesn't send an email.

I'll record that request. The public case history is saved in this browser. The local implementation uses LangGraph interrupts and SQLite checkpoints. The reviewer name is entered for this demonstration; authenticated identities are a future requirement.”

## 4:45–6:00 — Close the evidence loop

[Use Get the additional sample receiving report if needed. Upload `remaining-delivery.pdf`, click Add evidence & resume, and open Execution trace.]

“This reply records an additional twenty lamps against the same purchase order and SKU. The application extracts and validates it before accepting it as receiving evidence.

It resumes the same case and reruns the investigation. The local implementation resumes the same LangGraph thread. The previous hold and request remain in the history. This is the central behavior I wanted to demonstrate: new evidence changes a documented case, and the controls are evaluated again.

Now the unsupported value is zero and the required checks pass. The system still waits for a new human decision.”

[Show Round 2 and preserved review history. Enter your name and a note; click Recommend release.]

Suggested note: `Reviewed GRN-7731 for the additional 20 lamps and checked the updated source evidence.`

“I'll record a release recommendation after reviewing the evidence. No payment is initiated.”

## 6:00–6:45 — Show outputs and invalid input

[Download the PDF workpaper and JSON review pack. Open the PDF briefly. Import `agent_samples/invalid-invoice.pdf` and show the validation error; close the dialog and return to the completed case.]

“The output is a workpaper with findings, references, and decisions, plus a JSON review record and the editable request draft.

This deliberately invalid sample is text saved with a PDF extension. The import is rejected before an investigation starts. The existing case is preserved.

Other supplied scenarios cover changed bank details, a possible duplicate payment, and consistent evidence. Those are separate controls; a reviewer note cannot clear a failed bank or duplicate check.”

## 6:45–8:00 — Explain limits, learning, and next steps

[Return to the completed case and review history.]

“The important decisions were to keep tool access read-only, make money calculations authoritative in code, require evidence for extracted fields, and make human review part of the execution graph.

The public prototype uses real PDF processing and financial checks; the local version adds actual inference and LangGraph execution. All companies and accounting records are synthetic. It doesn't support scanned-document OCR, production accounting integrations, authenticated reviewers, or immutable audit storage. It also doesn't verify that a supplied document is authentic. The bank check compares account suffixes only.

Before expanding it, I would observe three reviewers handling real exceptions, using consented and redacted examples. I'd compare this workflow with a standardized spreadsheet and checklist. I'd measure time spent reviewing, extraction errors, incorrect evidence assignments, and repeated evidence requests.

My provisional target would be a twenty-five percent reduction in review time without increasing incorrect recommendations. That's a target to test, not a result I've achieved. If existing tools already solve the problem, or checking the model costs more time than it saves, I would simplify or change direction.

I used an AI coding assistant for implementation, testing, and drafting. No employer code or client data was reused. The source and README explain setup, synthetic inputs, test evidence, and limitations.”

## Short answers for follow-up questions

**Why agents?** “The useful behavior is a controlled loop: choose evidence queries, check the result, pause for a reviewer, accept a new document, and resume. LangGraph makes those transitions explicit. A fixed matching task would not need the same orchestration.”

**Why Ollama?** “It is a straightforward way to run inference locally without a model API key. I wanted to spend the effort on the workflow and controls. Model choice remains an evaluation decision.”

**What is automated?** “PDF field extraction, evidence-tool queries, control calculations, and drafting. The final reviewer decision is explicit, and the app performs no external financial action.”

**Is this ready for real client data?** “No. It needs reviewed extraction, authenticated access, durable and controlled storage, proper integrations, and evaluation on representative documents.”

**Why not use a spreadsheet?** “That is my baseline. If a shared checklist resolves the exceptions just as well with less effort, I would use it.”
