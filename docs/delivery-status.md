# Delivery status — published and verified

- **Working prototype:** https://ayaan-27.github.io/Miraflores_Project/
- **Source and README:** https://github.com/ayaan-27/Miraflores_Project
- **Written submission:** `written-submission.docx` (standard Word document, Arial 11 pt), with a matching four-page `written-submission.pdf` and editable `written-submission.md`.
- **Video:** not produced, as requested; `video-script.md` provides complete narration, screen actions, and follow-up answers, and `walkthrough.md` provides a short outline.

## Verification evidence

- **13 engine tests passed** locally and on GitHub's CI runner. CI: https://github.com/ayaan-27/Miraflores_Project/actions/runs/41378523953
- **Chromium acceptance workflow passed** against both the source server and the built production bundle. It exercised real imports, reviewer decisions, receipt reuse rejection, invalid-import preservation, downloads, injection protection, reset, mobile overflow, and dialog keyboard dismissal. No page errors or unexpected external requests occurred in that run.
- **Static production build passed.** Runtime app dependencies: none. No API keys, accounts, paid services, or external integrations are required to use the prototype.
- **Public Pages deployment and live-asset checks passed:** https://github.com/ayaan-27/Miraflores_Project/actions/runs/41378523946. The deployment workflow fetched the public page, CSS, application, engine, and CSV samples, verified their SHA-256 hashes against the exact build, and checked the demo's 12 transactions, 6 unresolved items, and $593.50 outstanding value.
- The original Pages-enable attempt failed because the workflow token could not administer the repository. The repository owner then enabled GitHub Actions as the Pages source. The next deployment succeeded. No extra credentials were added to the source.
- The cloud proxy still prevents a direct public-site browser check from this machine. Public verification ran on GitHub's deployment runner; local browser tests covered the exact production files. No public-site browser session from this cloud machine is claimed.

## Time and data boundaries

Approximately **25 minutes of AI-assisted implementation, writing, testing, and packaging** in this session on November 1, 2026, starting about 6:16 p.m. America/Los_Angeles. Candidate review and video recording are excluded. This is elapsed assisted work, not a claim about the candidate's independent effort.

The site and source include only synthetic data. No personal resume document, uploaded brief, secrets, employer code, or client information was published. Accounting workflow needs remain hypotheses, not claims about GreenGrowth CPAs' internal practices.

Follow-up revision: the four-page submission now includes an explicit first-person explanation of the problem-selection reasoning. The video script expands the outline into ready-to-speak content grounded in the supplied resume; personal phrasing should be adapted by the candidate. The original build-time estimate above excludes this follow-up revision.

Editorial revision: the written submission was rewritten throughout in direct first-person language, connecting work at Ricoh and Mphasis to the problem choice. It now uses standard Word formatting rather than the original branded PDF layout. The document-generation helper creates a DOCX and exports the matching PDF through LibreOffice. These revisions do not change the application or its behavior.

## Reproduction

Follow the root README. `npm test` validates the engine; `npm start` starts the source server; `npm run build` prepares `dist/`. The Pages workflow repeats tests and the build on main pushes, deploys, and validates public assets. Follow `walkthrough.md` for a normal case, a difficult matching case, and an invalid import.

Pending cloud network domain additions (`api.github.com` and `ayaan-27.github.io`) are saved in environment settings for future direct checks. They are not required for the public prototype to work. Saving the draft alone did not apply them to this instance.
