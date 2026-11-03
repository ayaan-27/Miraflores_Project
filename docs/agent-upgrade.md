# LedgerLens v2 — invoice exception investigator

This upgrade is being developed alongside the existing browser-only v1. The current GitHub Pages deployment remains v1 until the model-backed replacement is validated and hosted. The v2 UI and API are in `agent_workspace/`.

## The problem and the useful workflow

A reviewer receives a $10,000 invoice for 100 lamps. The approved order agrees with the invoice, but the receiving register supports only 80 lamps. Rather than simply flagging a mismatch, the investigation produces an evidence-backed hold and a specific request. The reviewer can supply a second receiving report for 20 lamps, resume the same case, rerun the investigation, and decide on a release recommendation.

The useful outcome is a documented resolution path. It is not a chatbot answer or an autonomous payment. This is an independent prototype, not a claim about GreenGrowth CPAs' current systems.

## Four stages

1. **Read and ground.** A local open-weight model extracts structured invoice fields from real PDF text. Each value must be supported by an exact quote on an actual page. Invalid or unsupported extraction stops the run.
2. **Investigate with tools.** A LangGraph node asks the model to choose its next read-only tool based on the invoice and observations. The available tools inspect the purchase order, receiving records, vendor master, prior payments, and relevant policy. The tool is executed and its result returns to the planner. This is a bounded loop, not a fixed sequence of five canned responses.
3. **Challenge.** Mandatory evidence checks must be completed. A missing check returns the investigation to the planner. Financial controls are then recomputed from source records using decimal arithmetic. A verifier drafts a source-cited memo. Unsupported source IDs or a recommendation conflicting with the controls are rejected, with one revision attempt.
4. **Human review and resume.** LangGraph interrupts at the review gate and saves its checkpoint in SQLite. A reviewer may record a hold, request more evidence, or recommend release when all controls pass. Supplying additional receiving evidence resumes the same thread, re-enters investigation, and preserves prior decisions.

The graph has conditional branches, a tool loop, a verifier feedback loop, and an evidence-response loop. These are visible in the execution trace. The UI does not display hidden chain-of-thought; it displays task descriptions, actual tool calls/results, computed controls, and explicit decisions.

## No-key model execution

The runtime uses **Qwen2.5-1.5B-Instruct, Q8 GGUF**, from the official Qwen repository, through `llama-cpp-python` on CPU. No external model API or model API key is needed. The initial download is approximately 2 GB. The download helper obtains the artifact's SHA-256 digest from official repository metadata and verifies the complete download before installing it. TLS and checksum verification remain enabled.

The model weights are external dependencies, not included in the source repository. Qwen2.5-1.5B-Instruct uses the Apache 2.0 license; consult its official model card and license before redistribution. The small model's extraction quality and speed need real-model validation; unit-test doubles do not establish that quality.

### Run locally

Use Python 3.12 and a C/C++ compiler. A machine with at least 8 GB of free memory is recommended; CPU execution can take minutes per case. Node is only needed for the legacy v1 workflow.

```bash
python3 -m venv .venv
. .venv/bin/activate
# On machines with a stale compiler setting, select the installed toolchain:
CC=gcc CXX=g++ CMAKE_BUILD_PARALLEL_LEVEL=4 pip install -r requirements-agent.txt
python scripts/download_agent_model.py
uvicorn agent_workspace.api:app --host 0.0.0.0 --port 8000
```

Open the local server in your own browser. The health response at `/api/health` reports `model_ready`, execution mode, and model name. A missing model is reported explicitly; there is no silent switch to a scripted model. On Windows, use the equivalent virtual-environment activation and a supported C++ build toolchain.

The model is loaded on the first invocation. Only two investigations can be queued at once. A run is limited to eight planning decisions per round, two verifier attempts, and three evidence rounds. Checkpoints and source PDFs are stored under `.agent-data/` by default. Set `LEDGERLENS_DATA_DIR` for another location and `LEDGERLENS_MODEL_PATH` for an already downloaded model file.

## What is real, synthetic, and deferred

- **Real implementation:** PDF text reading, schema validation and quote checks, LangGraph execution, read-only tool calls, computed financial controls, verifier validation, SQLite checkpoints, human interrupts, receipt-evidence resumption, browser UI, and downloadable PDF workpapers, JSON review packs, and request drafts.
- **Synthetic:** sample companies, invoices, purchase orders, receiving reports, vendor records, payment history, and policies. The internal tools read the fixture catalog; they do not connect to an accounting product.
- **Local language model:** implemented as the production execution path. A live-model run must be separately verified once official weights are available. The test double is imported only by tests, never automatically by the production server.
- **Deferred:** OCR, foreign currencies, taxes/discount adjustments, split or combined invoices, actual payments, outbound emails, accounting integrations, authenticated user identities, immutable audit storage, and production access controls.

Bank-account comparison uses a four-digit suffix only. It is a demonstration control, not a complete beneficiary-verification system. A changed bank suffix triggers an independent verification requirement and cannot be cleared by a note or by uploading an invoice. Reviewers cannot override a failed control.

## Tests and evidence

```bash
pip install -r requirements-agent-dev.txt
python -m pytest -q
```

The backend tests use explicit model test doubles while executing the actual framework, tools, controls, SQLite checkpoints, and API. They test the hold-to-evidence-to-approval path, bank-change and duplicate holds, source-quote rejection, an unsupported memo returned for revision, attempted control overrides, persistence after reopening the databases, and invalid API inputs. The browser acceptance test is `tests/agent_browser_smoke.py`; its prerequisites are explained in its header. It exercises real PDF upload, source inspection, trace, review, reply, reload/history, and export against a labeled test server. It does not measure live-model accuracy.

The production workflow has no `FixtureModel` fallback. Live-model validation and a no-key public host are the remaining release gates. The existing submission files still describe v1 until those gates pass, so they must not be submitted as a description of v2.

## Public hosting

GitHub Pages cannot run the Python graph or model. A free **Hugging Face Docker Space** is a suitable CPU host; no model API key is required, but the owner needs a Hugging Face account. The root `Dockerfile` is prepared for port 7860. It has not yet been built or deployed as a container in this environment.

For a Space, use the following YAML front matter at the top of its README, followed by any desired description:

```yaml
---
title: LedgerLens Invoice Investigator
emoji: 🔎
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---
```

Copy this project's Dockerfile, both `requirements-agent.txt` and `requirements-agent-base.txt`, `agent_workspace/`, `agent_samples/`, and `scripts/download_agent_model.py` into that Space. Startup downloads and verifies the model, then starts the same API/UI. Free CPU Spaces can sleep when inactive. Their filesystem is not durable across rebuilds or restarts; SQLite demonstrates process-restart recovery on retained storage, not guaranteed cloud persistence. Use a volume or suitable persistent store before promising durable hosted audit history.

This prototype is an unauthenticated demonstration workspace: source documents and runs are readable through its API. Use synthetic documents only. No real client information should be uploaded to a public demo. This is a material release boundary, not a claim of production readiness.
