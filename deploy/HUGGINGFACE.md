# Publish under ayaank27 without an inference API key

The owner needs to use their normal Hugging Face browser login. This cloud session is not authenticated to that account, so a username alone does not authorize a write into it. No password or token should be shared in chat.

The pinned revision passed the complete real-model integration check: https://github.com/ayaan-27/Miraflores_Project/actions/runs/41565144512

To publish:

1. Open https://huggingface.co/new-space while signed in as **ayaank27**.
2. Create a Space named **ledgerlens-investigator**. Choose **Docker → Blank**, **Public**, and the free **CPU Basic** hardware. Do not select a paid upgrade.
3. Extract the prepared two-file deployment ZIP. It contains `Dockerfile` and `README.md` at its root.
4. In the Space's **Files** tab, upload those two files at the root, replacing the starter versions. Commit the files. The Space will build automatically.
5. Wait for **Running**, open its App tab, and exercise the partial-delivery case. Native dependency installation, model download, and CPU inference can each take several minutes. Share the Space URL to verify the public instance and finish the submission links.

The Dockerfile fetches the exact public GitHub source revision `4ff4d5523c901550a511d6c5ae7bccfeee8f5747` and verifies the archive's SHA-256 digest before extracting it. The app independently verifies the official model weights. The source archive hash was checked during packaging; the Docker container has not yet been built in this cloud environment.

The full source bundle remains available for local development. The two-file Space bundle uses the pinned source so you do not need to upload nested folders manually. This is a manual publication step because no Hugging Face account credential is configured in this session.
