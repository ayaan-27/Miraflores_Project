# LedgerLens — ready-to-speak video script

Target: approximately 8–9 minutes including clicks and short pauses. Bracketed directions are actions, not spoken words. The personal framing below is a draft grounded in the resume and project decisions; adapt it to your own voice and retain only statements you can personally stand behind.

## Before recording

- Open https://ayaan-27.github.io/Miraflores_Project/ and reset the demo. Use synthetic data only.
- Download `samples/invalid-bank.csv` and `samples/receipts.csv` from the source repository before recording the invalid-input segment.
- Have the source repository open at `src/engine.js`. If showing tests, run `npm test` in the repository directory. Do not imply that a screenshot of a prior test is a new run.
- The demo's receipt references are synthetic labels. There are no actual receipt PDFs to open or inspect. The confirmation segment simulates a reviewer's decision.

## 0:00–0:45 — Introduction

[Show the LedgerLens home screen.]

“Hi, I'm Ayaan Khan. For this case study, I built LedgerLens, a small month-end evidence review workspace.

The problem I chose is the work between seeing a bank transaction and being able to explain what supports it. A reviewer might have a transaction export and a folder or index of receipts, but still need to work out which items are clear, which are ambiguous, and what to ask the client next.

I haven't observed GreenGrowth's internal process, so I'm treating that pain point as a hypothesis to validate. This is an independent prototype, using entirely synthetic data.”

## 0:45–2:00 — How I arrived at the problem

"My background is in applied AI and data systems. At Ricoh, I worked on a document assistant that preserved references to supporting diagrams and a text-to-SQL system spanning more than fifty relational databases. That experience motivated my interest in traceability: a useful answer needs evidence that someone can inspect.

I considered three directions: evidence review for accounting, more trustworthy answers across databases, and safer data sharing for model evaluation.

I chose evidence review because I could build and test one complete, useful workflow without pretending to understand an entire accounting practice or needing access to production systems.

I broke the problem into three questions. Is there plausible supporting evidence? Is the match unambiguous? And if it isn't, what should the reviewer do next?

That last question shaped the product. A list of uncertain matches isn't enough. The reviewer needs a recorded decision or a specific client request. I also wanted the system to be conservative: reusing one receipt for two different charges should not make both items look resolved.”

## 2:00–2:45 — Orient the viewer

[Point to the dataset label and summary cards.]

“The demo contains twelve bank transactions and ten receipt-metadata records for a fictional client, Cedar & Finch Studio.

Six transactions are matched by the rules. Four need review, and two have missing evidence. The outstanding evidence value is five hundred ninety-three dollars and fifty cents. That is the absolute value of unresolved transactions, not a claimed financial loss.

Everything runs in the browser. There is no account, API key, or runtime AI service. The receipt filenames are metadata labels, not actual documents that the application has read.”

## 2:45–3:45 — Demonstrate the core workflow

[Select Blue Bottle Coffee, B004. Point to the explanation and R004.]

“Here is a forty-eight-dollar-and-fifty-cent Blue Bottle Coffee transaction. The receipt index says Blue Bottle. The amount and date agree, but the merchant names overlap only partially, so the system asks for review rather than automatically accepting it.

The detail panel shows the original bank row, candidate receipt ID, date difference, and matching rules. In a real workflow, the reviewer would inspect the underlying receipt separately. This prototype doesn't verify the document or its business purpose.

I'll simulate that reviewer decision with a demo note and confirm receipt R004.”

[Enter `Synthetic demo: merchant variation reviewed; select R004.` Click Confirm receipt.]

“Now seven items are accounted for, five remain open, and the outstanding value is five hundred forty-five dollars. The original matching explanation is preserved alongside the reviewer's note.”

## 3:45–4:45 — Demonstrate a difficult case

[Select Staples B005. Show the shared-receipt explanation.]

“These two Staples transactions are both one hundred twenty-nine dollars, and they both have the same eligible receipt, R005. The rules leave both for review instead of assigning the first receipt they find.

For the demonstration, I'll assign R005 to B005.”

[Enter `Synthetic demo: allocate R005 to the first charge pending review.` Confirm. Select B006, enter a similar note, and attempt to confirm R005.]

“The second assignment is rejected because the receipt is already allocated. That is an enforced constraint, not just a warning label. The reviewer needs distinct evidence or an explanation. Split payments are outside this version's scope.”

## 4:45–5:45 — Show a meaningful output

[Select City Parking B009.]

“For this parking transaction, no receipt meets the matching rules. I'll record the next action.”

[Enter `Please provide the parking receipt and business purpose.` Click Mark requested.]

“Marking it requested doesn't resolve it. The evidence is still outstanding.

Now I can create a client request. The draft contains the unresolved transactions and the reviewer notes, while leaving out matched, confirmed, and excluded items. I can edit and download it. Nothing is emailed automatically.”

[Create client request, show B009 and its note, download, then close. Open Export review pack.]

“I can also export a CSV register and a JSON snapshot. These preserve source references, rules, and decisions. Decisions live in page memory, so the reviewer should download the review before reloading.”

## 5:45–6:30 — Demonstrate invalid input

[Close export. Open Import CSVs. Choose invalid-bank.csv and receipts.csv. Click Validate & review.]

“The prototype accepts real CSV imports as well as the sample. This file deliberately repeats a transaction ID. Validation rejects it with a specific error.

The existing review is unchanged. That matters because a bad upload should not erase decisions already made. Separate automated tests cover impossible calendar dates, malformed amounts, and CSV quoting as well.”

[Close import and select B004 to show the retained decision.]

## 6:30–7:30 — Explain implementation and choices

[Show src/engine.js, especially analyze and applyDecisions. Optionally show an actual npm test run.]

“The matching engine is separate from the interface. It compares signed amounts as integer cents, dates as UTC days, and normalized merchant tokens.

A candidate needs an exact amount, a date within the selected tolerance, and sufficient merchant overlap. Only a unique exact merchant match without a competing transaction is marked matched automatically.

I chose conventional rules because these comparisons should be repeatable and explainable. An LLM confidence score wouldn't improve the core financial checks. AI-assisted receipt extraction could be useful later, but it would need source references, measured error rates, and review.

Thirteen engine tests passed, along with browser acceptance checks covering imports, decisions, downloads, and failure cases. The deployment also verifies that the public assets match the tested build. These checks establish prototype behavior, not real-world matching accuracy.”

## 7:30–8:30 — Alternatives, next steps, and disclosure

“The strongest alternative is a standardized spreadsheet and client-request checklist. If that solves the problem just as well, a separate product may not be worth building.

My next step would be to interview three bookkeeping reviewers and understand where their time actually goes. With consented, redacted examples, I'd compare this workflow against a spreadsheet, measuring review time and incorrect evidence assignments.

A provisional goal is twenty-five percent less reviewer time without more incorrect matches. That is a target to test, not a result I've achieved. I'd stop or narrow the idea if existing tools already solve the problem or creating the receipt index costs more effort than the workflow saves.

The prototype doesn't include OCR, persistent accounts, accounting integrations, or autonomous posting. Those would follow evidence of demand.

I used an AI coding assistant to help develop the implementation, tests, and submission draft. No employer code or client data was reused. The source, setup instructions, samples, and expected outputs are included in the repository.

The question this prototype is designed to test is whether making exceptions explainable and actionable helps a reviewer move a close forward with less uncertainty.”

## Optional concise answers for follow-up questions

**Why isn't this an AI application?** The brief allows conventional software. Exact financial comparisons and allocation constraints benefit from explicit rules. AI is a possible later extraction component, not a requirement for the useful core workflow.

**Why CSVs rather than an accounting integration?** They let the reviewer exercise the whole loop without sharing production credentials or committing to one platform. The cost of preparing the receipt index is an important hypothesis to test.

**What makes a match trustworthy?** The prototype makes a narrow claim about metadata agreement and shows the rule and source IDs. It does not prove receipt authenticity, business purpose, tax treatment, or final accounting correctness.

**What would you change first?** First validate the real bottleneck. If index preparation dominates, investigate reviewed extraction. Before using actual client information, add the appropriate access controls, persistence, and security review.
