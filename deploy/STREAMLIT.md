# Optional persistent hosting for Month-end review

For a quick public notebook demo, use [the one-cell Colab launcher](NOTEBOOK.md). The steps below are an optional alternative for a persistent Streamlit URL.

Streamlit's [current documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud) states that Community Cloud is free. The application runs the model on that server; it does not require a paid Hugging Face Space, model API credentials, or an Ollama server on the reviewer's machine.

The source and model workflow can be prepared here, but this session has no Streamlit account authentication. The account owner needs to perform the publishing step through their normal browser login. Do not share passwords or tokens in chat.

1. Open **https://share.streamlit.io** and sign in with the GitHub account that owns `ayaan-27/Miraflores_Project`.
2. Select **Create app → Yup, I have an app**.
3. Use **Paste GitHub URL** with `https://github.com/ayaan-27/Miraflores_Project/blob/main/streamlit_app.py`. Alternatively, enter:
   - Repository: `ayaan-27/Miraflores_Project`
   - Branch: `main`
   - Main file path: `streamlit_app.py`
4. Keep **Python 3.12** in Advanced settings. No secrets are needed. A custom app subdomain is optional; the service can assign one.
5. Deploy the app and make it **public** for reviewers. Build/dependency installation can take several minutes. The locked native build uses one compilation job; the app downloads and verifies the public model on its first investigation.
6. Open the assigned `.streamlit.app` URL in a private browser window. Run Software → Investigate → Request evidence → Use sample agreement → Approve workpaper. Confirm the $22,000 proposed journal and $4,000 adjusted expense, and download the workpaper.
7. Send the actual app URL so the submission and walkthrough can use the verified link. Never describe an uncreated custom subdomain as live.

The earlier GitHub Pages URL is a different prototype. GitHub Pages cannot host this Python application. The default app executes LangGraph and actual local inference; it does not serve the previous rules-only browser adapter.

Community Cloud can sleep/restart, and resource limits still apply. The measured CI run and current Streamlit/browser checks are linked in the README; an untested host build is not a deployed-instance guarantee. Use the app logs to diagnose a build failure, and share the error text without secrets. Public review data is synthetic; exporting a workpaper is the retention path for this demo.

Official references: [deployment fields and Python version](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [Python/system dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).
