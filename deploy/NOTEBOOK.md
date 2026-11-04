# Run the public demo from a notebook

1. [Open in Colab](https://colab.research.google.com/github/ayaan-27/Miraflores_Project/blob/main/notebooks/Month_end_review.ipynb).
2. Select **Runtime → Run all** with the standard CPU runtime.
3. Open the public `https://…trycloudflare.com` link printed by the cell. Share that link while the notebook runs.

The one cell installs the pinned application into an isolated Python environment, starts Streamlit, and opens an account-free Cloudflare Quick Tunnel. The app runs its actual LangGraph/model workflow. It does not substitute model responses or change the interface. First setup and model loading can take a few minutes.

The public link stops when the cell/runtime stops. This is suitable for an interactive demonstration; it is not an always-on deployment. Interrupt the cell to stop the app and its tunnel. Streamlit Community Cloud is an optional alternative if a persistent app URL is needed.

The launcher uses a checksum-verified, pinned snapshot of the already-validated app and a checksum-verified official cloudflared binary. It preserves Streamlit's normal CORS and XSRF settings. It requires ordinary outbound network access from the notebook runtime. This managed Codex workspace has no public-port forwarding and does not permit tunnel connections, so the public launcher is intended to run in Colab rather than inside this restricted workspace.

The Google account needed to execute Colab is separate from hosting/deployment accounts; no Streamlit/Cloudflare signup or model API key is used. The application and notebook should receive sample data only.

Validation: [fresh-install and real public-tunnel browser check](https://github.com/ayaan-27/Miraflores_Project/actions/runs/41901554396) passed on Linux Python 3.12. This session cannot operate a personal Colab runtime; Run all executes the launcher in the runtime you open.
