# Month-End Variance Investigator

A Streamlit application that investigates an expense movement, checks its evidence and accounting policy, and prepares a workpaper and proposed journal for human review. Built for the MiraFlores case study; GreenGrowth CPAs is the intended evaluation audience, not an integration partner.

The interface is titled **Month-end review**. It shows account balances, findings, evidence, and review actions. The default deployment runs the actual LangGraph workflow and a small local model in the same server process. No inference API key, separate Ollama server, or paid Hugging Face Space is required.

**Public deployment:** awaiting the account owner's Streamlit publishing step. [Exact deployment instructions](deploy/STREAMLIT.md). Do not send the previous GitHub Pages prototype as this application.

## Run

Use **Python 3.12**. Linux needs a C/C++ compiler and CMake (`packages.txt` supplies these on Community Cloud). The runtime is pinned; native compilation is limited to one build job.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

On Windows, use `python` and activate with `.venv\Scripts\Activate.ps1`. If you prefer using an existing Ollama installation, use the alternative below instead of building native inference.

The first investigation downloads the public Qwen2.5-0.5B-Instruct Q4 model and verifies its bytes against the SHA-256 digest supplied by the official repository. Subsequent investigations reuse it. The model is CPU-based; allow time for the first download and inference. The app does not substitute test responses when a model is unavailable. A failed investigation retains its checkpoint and can be retried.

### Optional Ollama setup

Install/start [Ollama](https://ollama.com/download) and pull `qwen2.5:3b`. Install `requirements-variance-base.txt` rather than `requirements.txt`, then set `VARIANCE_PROVIDER=ollama` and run the same Streamlit command. The default endpoint is `http://127.0.0.1:11434`; `OLLAMA_MODEL` and `OLLAMA_BASE_URL` can override the model and server. On PowerShell set `$env:VARIANCE_PROVIDER="ollama"` before running Streamlit. The model changes; the graph, calculations, and human gates stay the same.

## Try the core workflow

1. Select **Software** and click **Investigate**. September expense is **$2,000**; October is **$26,000**, a **$24,000** movement. The investigator queries the SQLite ledger, reads the renewal invoice and close policy, and finds that the service agreement is missing. It cannot propose a treatment from the invoice description alone.
2. Inspect **Evidence** and **Activity**. Quotes come from actual PDF text. Queries are read-only and scoped to the account and two periods.
3. Enter a reviewer name and note; choose **Request evidence**. Approval is blocked. The editable request is a draft; no email is sent.
4. Upload `variance_samples/software-contract.pdf`, or select **Use sample agreement**, which reads that same actual PDF. It supplies a $24,000 service period from October 2026 through September 2027. The same graph thread resumes, retains the request, and reruns the investigation.
5. Inspect the **$22,000** proposed reclassification: debit prepaid services, credit software expense. The monthly allocation is $2,000, so October software expense after the proposed adjustment is **$4,000**, including the original $2,000 of recurring costs. Entries remain drafts.
6. Enter a new review note and **Approve workpaper**. Download the PDF, journal CSV, and JSON review record. Nothing is posted to an accounting system.

Other cases: **Payroll** increases from $40,000 to $58,000; an approved October bonus memo supports the $18,000 change, so no adjustment is proposed. **Professional fees** needs a missing agreement; its supplied October-only agreement supports the $8,000 additional charge without a deferral. **Travel** is below the illustrative review threshold.

## Difficult and invalid inputs

While waiting for the software agreement, upload `wrong-contract.pdf`. It is a real PDF for a different document/vendor; it is rejected and the existing case remains waiting. Then upload the correct contract and continue. `invalid-document.pdf` is deliberately plain text and is rejected before it can change evidence.

Use **Import ledger** with `invalid-ledger.csv`. Its duplicate transaction ID is rejected atomically; the current workspace is preserved. The valid `ledger.csv` starts a separate workspace. **Reset sample**, inside the same menu, starts a fresh sample review for rehearsals or different evidence.

## What is implemented

- A real **LangGraph StateGraph**, conditional tool loop, SQLite checkpoint saver, `interrupt`, and `Command` resumption. The model chooses from remaining permitted tools using their observed results. It has eight decisions per round; mandatory evidence coverage is enforced. A verifier calculates the treatment and checks a short model explanation. Review and evidence responses are graph events, not simulated progress.
- Actual parameterized **SQLite** queries over the CSV expense extract, vendor comparisons, PDF text/quote extraction, source hashes, and deterministic accounting controls. Tools execute as scoped LangChain tools; the model cannot submit arbitrary SQL or write to the ledger.
- Full-month allocation in integer cents, cent-conserving rounding, duplicate-document detection, source matching, balanced draft journals, and blocked approval when required support is unresolved.
- Streamlit file imports, source tables and PDF previews, review history, editable evidence requests, and PDF/CSV/JSON outputs.

The ledger, supplier documents, company, and close policy are synthetic. They are not connections to a real ERP, bank, payroll platform, or accounting firm. PDF fields use the supplied labeled format; general document extraction and OCR are deferred. The close is deliberately limited to the supplied expense accounts, USD, September/October 2026, and one positive posting that reconciles a material movement. Multiple drivers, duplicate postings, partial service months, and prior-period effects remain on hold for manual review.

The draft prepaid account mapping uses illustrative account 1500 (Prepaid services). The prepaid treatment follows the supplied sample accrual policy; it is not a general determination under every accounting framework. The system checks field consistency, not document authenticity. Reviewer names are entered and not authenticated. No email, journal posting, or other external financial action occurs.

## Validation

```bash
pip install pytest==8.4.2
python -m pytest -c variance_tests/pytest.ini variance_tests -q
```

The workflow/control tests and Streamlit AppTest checks use an explicit injected test planner; it is never a production fallback. They exercise the actual graph, tools, SQLite, PDFs, financial calculations, review gates, invalid replies, retry, and retained-disk restart recovery.

The complete current build passed [actual-model and Streamlit browser validation](https://github.com/ayaan-27/Miraflores_Project/actions/runs/41755341841). The model check completed the missing-contract loop, proposed $22,000, produced the $4,000 adjusted expense, and explained the bonus without an adjustment. It made 21 real model calls in 132.1 seconds excluding setup/download, with 749.6 MiB peak process RSS. A separate browser exercised `streamlit_app.py` with the actual model, wrong/correct PDF uploads, approval, retained reload, invalid CSV rejection, and all exports. The Streamlit process reached 939.0 MiB peak RSS in that run. These are small synthetic CPU checks, not production accuracy or hosted-performance claims. Current [validation workflow](https://github.com/ayaan-27/Miraflores_Project/actions/workflows/variance.yml).

For browser checks install Playwright 1.62.0 and Chromium, serve the app, and run `python variance_tests/browser_smoke.py`. The separate `variance_tests/serve_fixture.py` is only an explicit interface-test harness; do not deploy it. The JSON output identifies its test planner when used. CI uses `streamlit_app.py` with the actual model.

## Storage and configuration

`VARIANCE_DATA_DIR` sets the model/workspace location; the default is an application directory under the system temporary folder. An opaque workspace ID in the URL identifies this demonstration session. Checkpoints and uploads survive reruns/reloads while the files remain on that server. Streamlit Community Cloud can restart or sleep; temporary storage is not guaranteed to persist. Export the review before relying on it. Workspace IDs are not a substitute for authentication; use only synthetic inputs.

`VARIANCE_MODEL_PATH` can point to the expected official embedded model file. The download helper requires its checksum metadata. Python 3.12 and the locked runtime are the tested configuration. No inference credentials or Streamlit secrets are required for the default app.

## Submission and reuse

The written submission and video narration for this use case are in `docs/variance-submission.*` and `docs/variance-video-script.md`. They supersede the previous invoice prototype's submission. Earlier app folders are retained as prior work; the deploy entrypoint for this project is **streamlit_app.py**.

An AI coding assistant helped scope, implement, test, and draft the project. Local-inference and document-export patterns were adapted from the earlier prototype; no employer code or client data was used. The variance ledger, accounting controls, graph, and Streamlit interface were developed for this scope. Streamlit, LangGraph/LangChain, llama-cpp-python, pypdf, reportlab, and the Qwen model are third-party components. The default Qwen model is Apache 2.0 licensed; model weights are downloaded separately and not bundled with the source. Consult upstream licenses before redistribution.
