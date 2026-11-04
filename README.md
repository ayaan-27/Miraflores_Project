# Month-end review

In this repository, use `submission/OPEN_THIS.html`. In the submitted ZIP, open **OPEN_THIS.html** in Chrome, Edge, Firefox, or Safari on a desktop computer. Extract the ZIP first. There is no installation, login, API key, model download, or server. The file contains its scripts, styles, and sample data. Keep a local copy if a website is unavailable.

Public copy: https://ayaan-27.github.io/Miraflores_Project/
Source: https://github.com/ayaan-27/Miraflores_Project

## Try the workflow

1. Select Software and click **Investigate**. Approval is blocked because the service agreement is missing.
2. Enter your reviewer name and a meaningful note. Click **Request evidence**.
3. Click **Try mismatched agreement** to see rejection. Then click **Use sample agreement**, or upload `software-agreement.json`.
4. Review the $22,000 proposed deferral, $4,000 adjusted October expense, sources, and allocation. Enter a new decision note and **Approve workpaper**.
5. Download the PDF, proposed-journal CSV, and review JSON. No journal is posted.
6. Select Payroll and investigate: the supported bonus requires no adjustment. Professional fees requires `consulting-agreement.json` and also produces no adjustment.

Import `invalid-ledger.csv` to see a duplicate ID rejected without replacing the current case. **Reset sample** clears all decisions. Review data stays in this browser's local storage when available; storage is device/browser specific, editable, and not an authenticated audit log. Export JSON to retain a copy. Private-browser or restricted file storage may not persist on reload.

## Notebook

`Month_end_review.ipynb` embeds the implementation and all inputs, including executed outputs. Open it in any Python 3.10+ Jupyter environment and Run All. It uses only the Python standard library, with no downloads or remote calls. It writes `review-outputs/` with review JSON, journal CSV, and an HTML workpaper. Its reviewer actions are explicitly an automated walkthrough; the browser app accepts actual user decisions. Read the saved outputs even without running it.

## Source and build

`engine.js` contains the browser accounting controls and review state transitions; `app.js` the interface and PDF export; `template.html` the page; `data.json` the synthetic fixtures. `workflow.py` independently implements the cases in Python using in-memory SQLite. Sample evidence is structured JSON derived from synthetic records, with supplied quotes and page references; the app does not extract or authenticate PDFs. All client names, transactions, agreements and policies are synthetic.

The review is rules-based. No LLM, agent framework, email service, or accounting-system integration runs in this release. Materiality is illustrative ($5,000 and 20%); policy is supplied, not universal accounting guidance. Multiple drivers, partial months and prior-period effects are held for manual review. Names and authorization fields are not identity verification.

From the full repository, use Node 24, run `npm ci` and `npm run build` to regenerate the HTML. Run `npm test`, `python scripts/build_submission_notebook.py`, and `python tests/submission_browser.py` (Playwright + Chromium, optional development tools). The notebook and distributed HTML themselves require none of those build tools.

## Earlier experiments

The repository retains previous Streamlit/LangGraph and invoice-review experiments for source history. They are optional and are not required by the final standalone submission. The final deliverables and current public homepage use the workflow in `submission/`.
