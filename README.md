# LedgerLens — Invoice Exception Investigator

Prepared by Ayaan Khan for the MiraFlores case study, with GreenGrowth CPAs as the intended audience. An independent prototype using synthetic documents and business records.

**[Open the public prototype](https://ayaan-27.github.io/Miraflores_Project/)** · **[Written submission (Word)](docs/agent-submission.docx)** · **[PDF](docs/agent-submission.pdf)** · **[Video narration](docs/agent-video-script.md)**

## Review the prototype without installing anything

Open the public link in a modern desktop browser. No account, API key, or local server is needed.

1. Start **An invoice ahead of delivery**. The actual PDF bills $10,000 for 100 lamps; receiving evidence supports 80. Inspect the **$2,000** unsupported amount, source citations, and execution trace.
2. Enter a reviewer name and note. **Recommend release** is blocked. Select **Request more evidence** and inspect the editable request draft.
3. Download the additional sample receiving report from the case, then upload it using **Add evidence & resume**. It supports 20 more lamps. The same case advances to **Round 2**, reruns its checks, and retains your earlier decision.
4. Inspect the zero unsupported amount, record a release recommendation, and download the PDF workpaper and JSON review pack. No payment or message is sent.
5. Try the bank-change, duplicate, and clean cases. Import `agent_samples/invalid-invoice.pdf` to see an invalid upload rejected without replacing the current case.

## What runs in each version

| Capability | Public browser prototype | Local agentic implementation |
| --- | --- | --- |
| Read actual PDF text | PDF.js | pypdf |
| Extract fields and quotes | Explicit labeled-field rules; one-line-item sample format | Ollama model with schema validation and bounded repair |
| Investigate evidence | Fixed five-query checklist against synthetic records | LangGraph model-driven selection of scoped read-only LangChain tools |
| Financial controls | Actual integer-cent calculations | Actual Decimal calculations |
| Review narrative | Templates derived from control results | Model-drafted verifier memo; recommendation and citations checked |
| Human decisions and evidence reply | Actual review, PDF reply, rechecks, and retained history | LangGraph interrupts, Command resumption, and same-thread re-investigation |
| Persistence | IndexedDB in the reviewer's browser | SQLite and LangGraph checkpoints on the local server |
| Model inference | None; visibly disclosed in the interface and exports | Actual local Ollama inference; no model API key |

The public version demonstrates the product workflow. **It does not execute LangGraph or live model reasoning.** The local version implements and validates those capabilities. Neither version connects to real accounting systems. All supplier records, policies, and source documents are synthetic. Bank verification compares four-digit suffixes only.

## Run the full LangGraph + Ollama version

Use Python 3.12. Install and start [Ollama](https://ollama.com/download), then download the model:

```bash
ollama pull qwen2.5:3b
```

Clone this repository or extract the source ZIP, then run from its folder:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-agent-ollama.txt
python -m uvicorn agent_workspace.api:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. On Windows use `python` and activate with `.venv\Scripts\Activate.ps1`. Keep Ollama running; on Linux you may need `ollama serve` in another terminal. Allow about 2 GB for the model and use a machine with at least 8 GB RAM. CPU inference can take minutes; supported local GPUs can be used by Ollama. The model is configurable with `OLLAMA_MODEL`; financial controls and human gates remain in code.

[Detailed setup, configuration, architecture, and limits](docs/agent-upgrade.md). An optional native llama-cpp adapter is also retained. Ollama supplies inference, not public hosting; reviewers can use the public workflow demo without running it themselves.

## Run the public browser version locally

Use Node.js 24 and Python 3:

```bash
npm ci
npm test
npm run build
npm start
```

Open http://127.0.0.1:4173. Deploy only `dist/`; it contains the public demo and synthetic samples. It excludes the resume, case-study brief, Python data directories, and submission files. GitHub Pages publishes this build on main updates. The earlier receipt-matching prototype is retained at `/legacy/`; its [documentation](docs/legacy-v1.md) describes v1 only.

## Evidence and boundaries

- **25 Python tests pass** for framework execution, financial controls, checkpoint/review behavior, API validation, and Ollama protocol errors. Model doubles and mocked HTTP transports are explicit.
- **Real Ollama integration passed:** [validation run](https://github.com/ayaan-27/Miraflores_Project/actions/runs/41745682334). Actual local Qwen inference, five tools per round, the $2,000 hold, the receiving PDF reply, and both review gates completed in 876.9 seconds on the CPU runner, excluding setup. Reviewer actions were automated test inputs.
- The earlier native adapter also [passed real inference](https://github.com/ayaan-27/Miraflores_Project/actions/runs/41565144512). These small synthetic checks do not establish accuracy on unseen invoices.
- Node tests check the public financial controls, all four cases, rejected approvals, duplicate/wrong evidence, and exact amounts. Browser acceptance exercises actual PDFs, the evidence loop, reload/history, invalid input, and PDF/JSON exports. The browser test identifies which mode it is testing.

Python checks: `pip install -r requirements-agent-dev.txt`, then `python -m pytest -q`. Browser checks: serve the built public site and run `LEDGERLENS_AGENT_TEST_URL=http://127.0.0.1:4173 LEDGERLENS_AGENT_TEST_MODE=guided_demo python tests/agent_browser_smoke.py` with Playwright and Chromium installed.

Use synthetic documents only. Neither version implements authenticated identities, verified document authenticity, production access controls, OCR, immutable audit storage, or financial-system writes. Browser storage can be cleared; export before sharing a review. An exported reviewer name is not a verified identity. Public mode supports the supplied labeled, single-line-item PDF format; the local model supports a broader typed extraction schema but still requires evaluation.

## AI and third-party components

An AI coding assistant helped with scope, code, tests, and written drafts. No employer code or client data was used. Python dependencies are pinned in the requirements files; browser dependencies are pinned in `package-lock.json`. LangGraph/LangChain, FastAPI, pypdf, PDF.js (Apache 2.0), jsPDF (MIT), and Qwen/Ollama are external components. Model weights are downloaded separately and are not included in the source bundle. Consult the respective projects' licenses and model cards.
