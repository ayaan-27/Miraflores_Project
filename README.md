# Month-end review

A four-step expense review: identify a material movement, check supporting evidence, calculate the treatment, and record a human decision. Missing evidence pauses the case; matching support resumes it and requires a new review.

**[Open the prototype](https://ayaan-27.github.io/Miraflores_Project/)**

For offline use, download [OPEN_THIS.html](submission/OPEN_THIS.html) and open the saved file in a desktop browser. It includes all scripts, styles, and sample data. No installation, login, API key, model download, or server is required.

## Try the workflow

1. Select **Software** and click **Investigate**. Approval is blocked because the service agreement is missing.
2. Enter your reviewer name and a meaningful note. Click **Request evidence**.
3. Click **Try mismatched agreement** to see rejection. Then **Use sample agreement**, or upload [software-agreement.json](submission/software-agreement.json).
4. Review the **$22,000 proposed deferral**, **$4,000 adjusted October expense**, evidence, and allocation. Enter a new decision note and **Approve workpaper**.
5. Download the PDF workpaper, proposed-journal CSV, and review JSON. Nothing is posted to an accounting system.
6. Investigate **Payroll**: the supported October bonus requires no adjustment. **Professional fees** needs [consulting-agreement.json](submission/consulting-agreement.json) and also produces no adjustment.

Import [invalid-ledger.csv](submission/invalid-ledger.csv) to see a duplicate transaction ID rejected without replacing the current case. [ledger.csv](submission/ledger.csv) is the valid sample. **Reset sample** clears all decisions.

Review data stays in this browser's local storage when available. Storage is device/browser specific, editable, and not an authenticated audit log. Export JSON to retain a copy. Restricted or private browser storage may not persist on reload.

## Submission documents and notebook

- Written submission: [Word](docs/variance-submission.docx), [PDF](docs/variance-submission.pdf), [editable text](docs/variance-submission.md).
- [Video narration](docs/variance-video-script.md).
- [Standalone notebook](notebooks/Month_end_review.ipynb): open in a Python 3.10+ Jupyter environment and **Run All**. It embeds all inputs and implementation, uses only the standard library, and includes executed outputs. It writes `review-outputs/` with JSON, CSV, and an HTML workpaper. Notebook reviewer actions are an automated walkthrough; the browser accepts actual user decisions.
- [Example outputs](submission/example-outputs) from the executed notebook.

## Source and setup

| Location | Purpose |
| --- | --- |
| `submission/app.js`, `template.html` | Browser interface and PDF exports |
| `submission/engine.js` | Accounting checks and review state transitions |
| `submission/workflow.py` | Independent Python implementation using in-memory SQLite |
| `submission/data.json`, CSV/JSON samples | Synthetic ledger, policy, and structured evidence |
| `scripts/` | Build, notebook execution, document rendering, and deployment verification |
| `tests/` | Accounting controls and browser acceptance checks |
| `.github/workflows/pages.yml` | Validate and publish the public app |

To rebuild the offline HTML and public site, use Node 24:

```sh
npm ci
npm test
npm run build
```

The build writes `submission/OPEN_THIS.html` and the identical `dist/index.html`. Optional preview: `npm start`, then open http://127.0.0.1:4173.

Execute and regenerate the notebook with Python 3.10+; no Python dependencies are needed:

```sh
python scripts/build_submission_notebook.py
```

Optional browser acceptance tools:

```sh
python -m pip install playwright==1.62.0
python -m playwright install chromium
python tests/submission_browser.py
```

The browser check exercises evidence upload/resumption, approval gates, persistence, invalid CSV preservation, exports, mobile layout, and absence of external asset requests. It opens the offline HTML by default. Set `SUBMISSION_TEST_URL` to test an HTTP/HTTPS copy.

To regenerate Word and PDF from the Markdown draft, install `python-docx==1.2.0` and LibreOffice, then run `python scripts/render_submission.py`. Document and browser tooling are optional; neither is needed to use the distributed app or notebook.

## Scope

This is a rules-based prototype with synthetic entities, transactions, agreements, and policy. Sample evidence is structured JSON with supplied quotes and page references; the app does not extract or authenticate PDFs. No LLM, agent framework, email service, or accounting-system integration runs here.

Materiality ($5,000 and 20%) and the accounting policy are illustrative. Multiple drivers, partial months, and prior-period effects need manual review. Reviewer names and authorization fields are not identity verification. Proposed journals require review and are never posted.

See [third-party notices](submission/THIRD-PARTY-NOTICES.md) for bundled software licenses.
