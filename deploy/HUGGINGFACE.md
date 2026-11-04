# Publish under ayaank27 without an inference API key

**Hosting correction:** Hugging Face now requires a paid plan to create a Docker Space, even when CPU Basic has no hourly hardware charge. The Docker instructions below are not a free deployment route. Do not purchase a plan for this submission.

The owner's account currently shows both Gradio and Docker as paid-only, so this publication route is blocked for that account. Use the [local Ollama setup](../docs/agent-upgrade.md#run-with-ollama-recommended) for the demonstration instead. Ollama does not by itself provide a public hosted URL.

The documented free exception is up to two **Gradio ZeroGPU** Spaces for personal accounts with a verified email that are more than 30 days old. That option needs a different inference/deployment adapter; this Docker bundle cannot be uploaded unchanged to a Gradio Space. Account eligibility and the adapted runtime must be checked before promising a free public deployment. Ordinary Gradio CPU Spaces also require a paid plan.

Sources: [Spaces overview](https://huggingface.co/docs/hub/spaces-overview#hardware-resources), [ZeroGPU hosting eligibility](https://huggingface.co/docs/hub/spaces-zerogpu#using-and-hosting-zerogpu-spaces). Local execution remains free and requires no model API key; see `docs/agent-upgrade.md`.

The owner needs to use their normal Hugging Face browser login. This cloud session is not authenticated to that account, so a username alone does not authorize a write into it. No password or token should be shared in chat.

The pinned revision passed the complete real-model integration check: https://github.com/ayaan-27/Miraflores_Project/actions/runs/41565144512

Docker reference instructions (requires an existing eligible paid hosting plan):

1. Open https://huggingface.co/new-space while signed in as **ayaank27**.
2. Create a Space named **ledgerlens-investigator**. Choose **Docker → Blank**, **Public**, and **CPU Basic** hardware. CPU Basic has no hourly hardware charge, but creating this Space requires a paid account plan.
3. Extract the prepared two-file deployment ZIP. It contains `Dockerfile` and `README.md` at its root.
4. In the Space's **Files** tab, upload those two files at the root, replacing the starter versions. Commit the files. The Space will build automatically.
5. Wait for **Running**, open its App tab, and exercise the partial-delivery case. Native dependency installation, model download, and CPU inference can each take several minutes. Share the Space URL to verify the public instance and finish the submission links.

The Dockerfile fetches the exact public GitHub source revision `4ff4d5523c901550a511d6c5ae7bccfeee8f5747` and verifies the archive's SHA-256 digest before extracting it. The app independently verifies the official model weights. The source archive hash was checked during packaging; the Docker container has not yet been built in this cloud environment.

The full source bundle remains available for local development. The two-file Space bundle uses the pinned source so you do not need to upload nested folders manually. This is a manual publication step because no Hugging Face account credential is configured in this session.
