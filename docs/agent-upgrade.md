# LedgerLens v2 — invoice exception investigator

This upgrade is being developed alongside the existing browser-only v1. The current GitHub Pages deployment remains v1 until the model-backed replacement is validated and hosted. The v2 UI and API are in `agent_workspace/`.

## The problem and the useful workflow

A reviewer receives a $10,000 invoice for 100 lamps. The approved order agrees with the invoice, but the receiving register supports only 80 lamps. Rather than simply flagging a mismatch, the investigation produces an evidence-backed hold and a specific request. The reviewer can supply a second receiving report for 20 lamps, resume the same case, rerun the investigation, and decide on a release recommendation.

The useful outcome is a documented resolution path. It is not a chatbot answer or an autonomous payment. This is an independent prototype, not a claim about GreenGrowth CPAs' current systems.

## Four stages

1. **Read and ground.** A local open-weight model extracts structured invoice fields from real PDF text. A read-only lookup anchors an extracted value to a uniquely matching labeled PDF line when one exists. It never changes the value or chooses between ambiguous matches. Each value must then pass the source-quote check. Unsupported extraction is returned with validation feedback for up to three attempts; if it still fails, the run stops. Financial and citation checks remain strict.
2. **Investigate with tools.** A LangGraph node asks the model to choose its next read-only tool based on the invoice and observations. The available tools inspect the purchase order, receiving records, vendor master, prior payments, and relevant policy. The tool is executed and its result returns to the planner. This is a bounded loop, not a fixed sequence of five canned responses.
3. **Challenge.** Mandatory evidence checks must be completed. A missing check returns the investigation to the planner. Financial controls are then recomputed from source records using decimal arithmetic. A verifier drafts a source-cited memo. Unsupported source IDs or a recommendation conflicting with the controls are rejected, with one revision attempt.
4. **Human review and resume.** LangGraph interrupts at the review gate and saves its checkpoint in SQLite. A reviewer may record a hold, request more evidence, or recommend release when all controls pass. Supplying additional receiving evidence resumes the same thread, re-enters investigation, and preserves prior decisions.

The graph has conditional branches, a tool loop, a verifier feedback loop, and an evidence-response loop. These are visible in the execution trace. The UI does not display hidden chain-of-thought; it displays task descriptions, actual tool calls/results, computed controls, and explicit decisions.

## No-key model execution

**Ollama is the recommended local inference provider.** The default model is `qwen2.5:3b`; the LangGraph workflow does not depend on that specific model. Ollama handles model installation and inference, while this application handles the document evidence, tool calls, financial controls, checkpointing, and human decisions. No model API key or paid hosting account is needed to run locally.

The local Ollama endpoint receives schema-constrained requests using the same task prompts and Pydantic result types as the native adapter. A model failure does not bypass a control or change a recommendation. The model can be replaced via configuration; every replacement still needs evaluation for extraction, tool selection, and citation quality.

Model weights are external dependencies and are not included in the source repository. The default Qwen2.5 model uses the Apache 2.0 license; consult its official model card and license before redistribution. Test doubles and actual inference validation are reported separately below.

### Run with Ollama (recommended)

Install [Ollama](https://ollama.com/download), start the application, and use Python 3.12. A machine with at least 8 GB RAM is recommended. CPU inference can take several minutes per case; Ollama can use a supported local GPU automatically. Node is only needed for the legacy v1 workflow.

Download the model once:

```bash
ollama pull qwen2.5:3b
```

The download is approximately 2 GB. On Linux, or if the desktop app is not serving requests, keep `ollama serve` running in a separate terminal. A message that port 11434 is already in use normally means Ollama is already running.

In the project folder:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-agent-ollama.txt
python -m uvicorn agent_workspace.api:app --host 127.0.0.1 --port 8000
```

On Windows PowerShell, create the environment with `python -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`. No C++ compiler is needed for this Ollama setup.

Open **http://127.0.0.1:8000** in your browser. Keep Ollama and the Python server running. `/api/health` checks that Ollama is reachable and the selected model is installed; it reports `mode: ollama_local` and `model_ready: true` when ready. A missing prerequisite produces setup instructions and blocks a new investigation. There is no automatic scripted response or provider fallback.

Optional environment settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `LEDGERLENS_MODEL_PROVIDER` | `ollama` | Select `ollama` or the optional `llama_cpp` adapter. |
| `OLLAMA_MODEL` | `qwen2.5:3b` | An installed Ollama model with JSON-schema output support. |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | The Ollama server reached by the Python backend. Keep it local for a local-only demo. |

The browser connects to the Python app, which calls Ollama. It does not need direct access to Ollama or a public Ollama port. The point of the demo is the investigation and resolution workflow; the model is an interchangeable inference component.

### Optional native inference adapter

The earlier **Qwen2.5-1.5B-Instruct Q8 GGUF / llama-cpp-python** adapter remains available. It requires a C/C++ compiler, unlike the recommended setup. It downloads the official artifact and verifies the SHA-256 digest supplied by its repository metadata. Use `requirements-agent.txt`, run `python scripts/download_agent_model.py`, and set `LEDGERLENS_MODEL_PROVIDER=llama_cpp` before starting the same API.

Native inference executes inside a dedicated spawned process; the Ollama adapter uses Ollama's separate model server. Both use the same graph, tools, authoritative controls, and review gates.

The model is loaded on the first invocation. Only two investigations can be queued at once. A run is limited to three invoice-extraction attempts, eight planning decisions per round, two verifier attempts, and three evidence rounds. Receiving extraction has two source-grounding attempts; an invalid reply returns to the waiting checkpoint without erasing prior controls or decisions. PDF text is limited to 12,000 characters to fit the local context budget. Checkpoints and source PDFs are stored under `.agent-data/` by default. Set `LEDGERLENS_DATA_DIR` for another location and `LEDGERLENS_MODEL_PATH` for an already downloaded model file.

## What is real, synthetic, and deferred

- **Real implementation:** PDF text reading, schema validation and quote checks, LangGraph execution, read-only tool calls, computed financial controls, verifier validation, SQLite checkpoints, human interrupts, receipt-evidence resumption, browser UI, and downloadable PDF workpapers, JSON review packs, and request drafts.
- **Synthetic:** sample companies, invoices, purchase orders, receiving reports, vendor records, payment history, and policies. The internal tools read the fixture catalog; they do not connect to an accounting product.
- **Local language model:** implemented as the production execution path. The complete live-model integration passed on the pinned runtime. See the evidence below. The test double is imported only by tests, never automatically by the production server.
- **Deferred:** OCR, foreign currencies, taxes/discount adjustments, split or combined invoices, actual payments, outbound emails, accounting integrations, authenticated user identities, immutable audit storage, and production access controls.

Bank-account comparison uses a four-digit suffix only. It is a demonstration control, not a complete beneficiary-verification system. A changed bank suffix triggers an independent verification requirement and cannot be cleared by a note or by uploading an invoice. Reviewers cannot override a failed control.

## Tests and evidence

```bash
pip install -r requirements-agent-dev.txt
python -m pytest -q
```

The backend tests use explicit model test doubles while executing the actual framework, tools, controls, SQLite checkpoints, and API. They test the hold-to-evidence-to-approval path, bank-change and duplicate holds, source-quote rejection, an unsupported memo returned for revision, attempted control overrides, persistence after reopening the databases, and invalid API inputs. The browser acceptance test is `tests/agent_browser_smoke.py`; its prerequisites are explained in its header. It exercises real PDF upload, source inspection, trace, review, reply, reload/history, and export against a labeled test server. It does not measure live-model accuracy.

The production workflow has no `FixtureModel` fallback. The Ollama protocol tests check readiness, missing models, actual request schemas, invalid output, and connection failures using an explicitly mocked HTTP transport. They are not inference tests. Actual Ollama validation is run by `.github/workflows/ollama-live.yml`; inspect that run before claiming the Ollama path passed real inference. The existing v1 submission files must not be submitted as a description of v2; use the separately labeled v2 documents.

The initial real-model CI runs downloaded and checksum-verified the official weights and executed actual inference. They caught an unsupported SKU source quote, which motivated the deterministic citation lookup and bounded extraction repair. A subsequent run exposed a native runtime crash, which motivated process isolation and phase-specific diagnostics. These failed runs are not counted as successful model validation. The pinned llama-cpp-python 0.3.16 / NumPy 2.2.6 stack subsequently passed on Ubuntu 24.04: https://github.com/ayaan-27/Miraflores_Project/actions/runs/41565144512. It executed the actual open-weight model, ten tool calls across two rounds, and both review gates in 525.7 seconds, excluding installation and model download. Review decisions in that integration test were automated inputs, not actual human sign-off.

## Public hosting

The recommended demonstration runs locally with Ollama. Ollama supplies inference; it is not a public host. A public model-backed URL still needs a running machine. Local execution and video recording do not depend on a hosting subscription.

GitHub Pages cannot run the Python graph or model. **Hugging Face now requires a paid plan to create Docker and ordinary Gradio compute Spaces**, even though CPU Basic itself has no hourly hardware charge. Earlier instructions describing a Docker Space as free were incorrect. Do not purchase a plan for this submission. The root `Dockerfile` remains a container deployment option on a suitable host; it is prepared for port 7860 and has not yet been built or deployed as a container in this environment.

Hugging Face documents a free exception for up to two Gradio ZeroGPU Spaces on personal accounts with a verified email that are more than 30 days old. Eligibility must be confirmed, and the current CPU inference adapter and Docker bundle require adaptation before that route can be used. See [current Spaces requirements](https://huggingface.co/docs/hub/spaces-overview#hardware-resources), [ZeroGPU eligibility](https://huggingface.co/docs/hub/spaces-zerogpu#using-and-hosting-zerogpu-spaces), and [deployment status](../deploy/HUGGINGFACE.md). Local execution requires no subscription or model API key.

For a Docker Space on an eligible hosting plan, use the following YAML front matter at the top of its README, followed by any desired description:

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

Copy this project's Dockerfile, both `requirements-agent.txt` and `requirements-agent-base.txt`, `agent_workspace/`, `agent_samples/`, and `scripts/download_agent_model.py` into that Space. Startup downloads and verifies the model, then starts the same API/UI. CPU Basic Spaces can sleep when inactive. Their filesystem is not durable across rebuilds or restarts; SQLite demonstrates process-restart recovery on retained storage, not guaranteed cloud persistence. Use a volume or suitable persistent store before promising durable hosted audit history.

`deploy/space-README.md` is a ready-to-use Space README with the required Docker metadata. The prepared deployment ZIP places it at the root as `README.md`, with only the files needed to build and run the server. Extract the ZIP before uploading and preserve its folder paths.

This prototype is an unauthenticated demonstration workspace: source documents and runs are readable through its API. Use synthetic documents only. No real client information should be uploaded to a public demo. This is a material release boundary, not a claim of production readiness.
