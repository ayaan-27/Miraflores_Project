# LedgerLens v2 — Agentic Invoice Investigator

This development branch adds a four-stage **LangGraph** invoice-investigation workflow using a **local open-weight model**, with no model API key. The existing published GitHub Pages prototype remains v1 while v2 is validated and hosted.

The recommended setup uses **Ollama** with `qwen2.5:3b`. The model is replaceable; the product value is the evidence investigation, independently computed controls, human review, and resumption of the same case when new evidence arrives.

1. Read a real invoice PDF and validate extracted fields against exact source quotes.
2. Let the investigator choose read-only tools for orders, receiving, vendor records, payment history, and policy.
3. Recompute financial controls and reject unsupported verifier findings.
4. Pause for human review, request missing evidence, and resume the same persisted case when a new document arrives.

**Main demonstration:** a $10,000 invoice is held because receiving evidence supports only 80 of 100 units. Add the receiving report for the remaining 20 units, rerun the investigation, and record the reviewer decision. The output includes a PDF workpaper, an evidence-request draft, and the full JSON review record.

**[Agent setup, architecture, boundaries, and hosting instructions](docs/agent-upgrade.md)**

**[Run v2 locally with Ollama](docs/agent-upgrade.md#run-with-ollama-recommended)**. No API key or Hugging Face hosting plan is required. LangGraph, tools, financial controls, and human review are independent of the inference provider.

Framework/tools/control/API tests and browser acceptance pass with explicit test doubles. The complete **real-model integration also passed** on the pinned CPU stack: actual PDF extraction, five tool calls per round, the initial hold, a new receiving PDF, resumption of the same case, and both review gates. [Validation evidence](https://github.com/ayaan-27/Miraflores_Project/actions/runs/41565144512). Automated reviewer inputs in that test are labeled as such. Public hosting remains pending; GitHub Pages cannot run this Python/model backend.

The v1 submission documents below are retained until the v2 release gates pass; they do not describe v2.

---

## Legacy v1 documentation

# LedgerLens

**Evidence before confidence.** A working month-end evidence review prototype prepared by Ayaan Khan for the MiraFlores case study, with GreenGrowth CPAs as the intended evaluation audience. This is an independent candidate project, not a GreenGrowth product or an integration with its systems.

LedgerLens turns bank transactions and receipt metadata into an explained exception queue, reviewer decisions, a downloadable review register, and an editable client request. Matching actually runs in the browser. There is no LLM, paid service, API key, backend, or mocked matching response.

**[Open the live prototype](https://ayaan-27.github.io/Miraflores_Project/)** · **[Written submission (Word)](docs/written-submission.docx)** · **[PDF](docs/written-submission.pdf)** · **[Source code](https://github.com/ayaan-27/Miraflores_Project)**

Recording your walkthrough? Use the [ready-to-speak video script](docs/video-script.md), including timed narration, screen actions, and follow-up answers.

## Run locally

Requirements: **Node.js 20+** (tested with 24.19.0), **Python 3.10+** (tested with 3.12.14), and a modern browser with ES modules and native HTML dialogs. No packages need installing and no lockfile is needed; there are zero npm dependencies.

```bash
git clone https://github.com/ayaan-27/Miraflores_Project.git
cd Miraflores_Project
npm test
npm start
```

Open `http://localhost:4173` in your own browser. Keep the server running. Do not open `index.html` using a `file://` URL: fetching the sample CSVs requires HTTP. If 4173 is occupied, run `python3 -m http.server 4174` and use that port.

Build a deployable static site:

```bash
npm run build
python3 -m http.server 4173 --directory dist
```

Serve only `dist/` when hosting publicly. It includes the site and synthetic samples; it excludes the resume, case-study PDF, development tests, and submission documents. All asset URLs are relative, so hosting under a repository subpath works.

## A five-minute demonstration

1. The page loads the **synthetic** Cedar & Finch Studio sample automatically: **12 transactions, 10 receipt records, 6 matched, 4 needing review, 2 missing evidence; $593.50 of absolute unresolved transaction value.** The amount is neither an expense total nor a claimed loss.
2. Select **Blue Bottle Coffee / B004 / $48.50**. It matches the amount and date of **R004**, but “Blue Bottle” only partially overlaps the bank name. Inspect the explanation and metadata reference, enter `Confirmed the merchant against the original receipt.`, then click **Confirm receipt**. There are now **7 accounted for, 5 open, $545.00 unresolved**. The original matching reason is retained.
3. Inspect **Staples B005 and B006**. One receipt, **R005**, is eligible for both charges. Confirm it for B005 with a note. Attempt to confirm the same receipt for B006: the app rejects the second allocation. It does not silently reuse a receipt. Undo the first decision if you need to assign it differently.
4. Select **City Parking / B009**, add a request note, and click **Mark requested**. The item remains outstanding. **Create client request** produces a draft with this transaction and your note; matched, confirmed, and excluded items are omitted. Edit and download it. No message is sent.
5. **Export review pack** downloads the CSV register and full JSON snapshot. Decisions are in memory until reload, so export before leaving. Snapshot re-import is not implemented.

## Invalid-input demonstration

Choose **Import CSVs**. Select `samples/invalid-bank.csv` and `samples/receipts.csv`. Click **Validate & review**. Expected result: **`bank, data row 2: Duplicate ID: B001. Use unique source IDs.`** The import is rejected atomically; the current dataset and decisions remain intact. This sample also has an impossible date and malformed amount, but validation stops at the first error. Separate automated tests cover each error.

To import successfully, use `samples/bank.csv` and `samples/receipts.csv`. A successful import starts a new review and clears prior decisions. Reset demo also clears the review, with confirmation if there are imported data or decisions.

## CSV contract

Bank:

```csv
id,date,description,amount
B001,2026-09-02,Figma Inc,15.00
```

Receipt index (not PDF files):

```csv
id,date,vendor,amount,reference
R001,2026-09-02,Figma,15.00,figma-september-invoice.pdf
```

Expected output for these two rows: **Matched**, receipt **R001**, reason **EXACT_MATCH**. `Inc` is removed during vendor normalization. This verifies a metadata relationship, not document contents or business purpose.

- Headers are case-insensitive. All required fields must be nonempty. Extra columns are permitted but are not used or retained in the normalized snapshot.
- IDs must be unique within each source and use 1–50 letters, numbers, `_`, or `-`.
- Dates are valid `YYYY-MM-DD` calendar dates. Matching uses UTC days, avoiding local timezone drift.
- USD only. **Positive amounts are expenses; negative amounts are refunds in both files.** Convert credit/debit conventions before importing. Up to two decimals, no currency symbols, thousands separators, exponent notation, or zero amounts. All comparisons use integer cents.
- Maximum 500,000 bytes and 1,000 data rows per file; maximum 500 characters per input field. UTF-8 BOM, CRLF, escaped quotes, commas inside quoted fields, and multiline quoted values are supported.
- `reference` is an inert label. LedgerLens does not open arbitrary links, read receipts, perform OCR, or verify document authenticity.
- Import both files together. An empty receipt file is rejected in this version. To inspect missing-evidence behavior, import unrelated receipt records or use the supplied demo. Month labels are illustrative: imported files can span multiple dates and are not filtered to September.

## How matching works

`src/engine.js` has no UI or network dependencies. It validates CSVs, normalizes merchant names, generates candidates, and evaluates independent reviewer decisions.

1. A candidate must have an **exact signed amount**, a date within **±3 days by default** (configurable at import from 0 to 7 days), and normalized merchant token intersection/union of **at least 0.5**.
2. Normalization lowercases text, strips common Latin accents and punctuation, and removes the standalone company suffixes `inc`, `llc`, `ltd`, `corp`, and `co`. No fuzzy edit distance, alias service, external knowledge, or learned model is used. Non-Latin merchant support is limited.
3. Only a **single exact normalized merchant** candidate with no competing transaction is marked **Matched**. Partial merchant overlap, multiple candidates, shared receipts, and duplicate bank fingerprints require review. No qualifying candidate means missing evidence. Exact merchant name is necessary for auto matching, but is not proof of vendor identity.
4. A reviewer can confirm a candidate, exclude an item with a reason, or mark evidence requested. Notes must contain 5–1,000 characters. Receipt allocation is one-to-one. A request remains unresolved. Exclusions are shown separately in the count and remain in exports.
5. Decisions retain the original rule result. Undo recomputes the view from unchanged source metadata. Rule version **1.0.0** is exported with source IDs, row numbers, file references, notes, and decision timestamps. Decisions identify a local session, not an authenticated person.

Deliberate boundaries: no split payments, combined receipts, FX, tax categorization, bank balance reconciliation, fraud determination, ledger posting, verified audit log, or accountant sign-off. A one-dollar difference is not “close enough”; it stays unmatched.

## Tests

```bash
npm test                  # 13 Node tests; zero third-party dependencies
npm run build             # copies only required public assets into dist/
```

Optional browser regression test, in another terminal while the server runs:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install playwright==1.62.0
python3 -m playwright install chromium
CHROMIUM_PATH="$(python3 -c 'from playwright.sync_api import sync_playwright; p=sync_playwright().start(); print(p.chromium.executable_path); p.stop()')" python3 tests/browser_smoke.py
```

Alternatively point `CHROMIUM_PATH` to an existing Chromium installation. On the development machine `/usr/bin/chromium` and Python Playwright were already installed. Browser automation is an optional development dependency, not needed to use the app. `LEDGERLENS_URL` selects an alternative server URL (without a trailing slash).

The browser test exercises decisions, invalid/valid file imports, shared-receipt rejection, JSON and CSV downloads, HTML injection protection, reset, mobile overflow, and keyboard dialog dismissal. It also fails on page errors or unexpected external requests. CI runs the dependency-free engine tests and static build on main pushes and pull requests. Browser tests were run locally, not in CI.

## Privacy and limitations

No analytics, remote fonts, API calls, server storage, localStorage, or cookies. Uploaded file contents remain in page memory. Downloads are saved by your browser. The site host receives standard requests for static files and may log ordinary web request metadata. This is not a security certification. Use synthetic or redacted information for evaluation.

Imported text is escaped before rendering. CSV output prefixes formula-like cells and quotes all fields to reduce spreadsheet formula injection. JSON preserves original normalized metadata. The JSON snapshot is an editable export, not an immutable audit record or a resumable session. Sensitive data in exported files needs normal handling controls.

## Source map and submission

```text
index.html                    semantic page and dialogs
styles.css                    responsive interface, local system fonts
src/engine.js                 CSV validation, matching, decisions, exports
src/app.js                    state, import/review/export browser workflow
samples/                      synthetic happy-path and invalid CSVs
tests/engine.test.js          deterministic regression tests
tests/browser_smoke.py        real browser acceptance workflow
scripts/build.js              static production build
docs/written-submission.md    editable written submission
docs/written-submission.docx  standard Word document (Arial 11 pt)
docs/written-submission.pdf   formatted submission (four pages)
docs/walkthrough.md           optional outline for your own video
docs/video-script.md          full spoken script and screen actions
.github/workflows/            CI and GitHub Pages deployment
```

All implementation code and synthetic samples were created for this submission using an AI coding assistant; no prior application code or employer data was reused. The resume informed the problem selection only and is not included in the site or source package. See the written submission for assumptions, tradeoffs, validation, AI disclosure, and next experiments.

To regenerate the included Word and PDF files (optional, separate from running the product), install `python-docx==1.2.0` in a Python virtual environment and have LibreOffice's `soffice` command available. Run `python3 scripts/render_submission.py` from the repository root. The script creates an Arial 11 pt Word document with US Letter pages, one-inch margins, 1.15 line spacing, and simple black headings, then exports that same document to PDF. Microsoft Word uses Arial when installed; PDF export uses the system's available compatible font. These document tools are not application dependencies.

## Deploy

The app can be hosted on any static host; upload `dist/`. The included Pages workflow builds and deploys on main pushes once **GitHub repository Settings → Pages → Source → GitHub Actions** is selected. This is a one-time repository setting requiring repository administration rights. The workflow needs GitHub Pages and Actions enabled. GitHub supplies the workflow token; do not put credentials in source.

After deployment, the workflow checks the public page, stylesheet, application code, matching engine, and sample files against SHA-256 hashes of the exact build. It also checks expected sample results. For branch-based Pages, publish the contents of `dist/` (including a `.nojekyll` file) to a `gh-pages` branch and select **Deploy from a branch → gh-pages → /(root)** instead. Use one deployment method at a time. The live URL is `https://ayaan-27.github.io/Miraflores_Project/`. Deployment evidence is recorded in `docs/delivery-status.md`.
