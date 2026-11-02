# Your 5–10-minute walkthrough

Use this as an outline for your own recording. Read the source and adapt the wording so you can explain each choice. This is not a video deliverable.

For a complete ready-to-speak version with screen actions and follow-up answers, see [video-script.md](video-script.md).

**0:00–1:00 — Problem and choice.** Briefly compare evidence review with cross-database analytics and safe evaluation data. Explain what your resume actually supports and what is still an accounting hypothesis. State that the prototype is an independent project for evaluation, not a GreenGrowth integration.

**1:00–2:00 — Orientation.** Open the deployed site, reset demo, and show the labels: synthetic data, local browser processing, 12 bank rows, 10 receipt records. The baseline is 6 matched and 6 open, with $593.50 of absolute open transaction value. Explain that matched metadata is not a verified document.

**2:00–3:15 — Useful core workflow.** Select Blue Bottle Coffee (B004). Show the date, cents-exact amount, partial merchant name, source row, and R004 metadata reference. Explain that a real reviewer inspects the underlying receipt separately. Add a note and confirm. Show 7 accounted for, 5 open, $545.00 unresolved.

**3:15–4:30 — Hard case.** Select Staples B005, confirm R005 with a note, then select B006 and try the same receipt. Show the rejection. Explain why amount-only matching or greedy first-match assignment would be unsafe. Undo the B005 decision if you want to restore the scenario.

**4:30–5:30 — Real output.** Select City Parking (B009), add a note, and mark requested. It stays open. Create the request, edit it, and download the draft. Export the CSV and JSON review pack; show an actual downloaded row with a source reference and reviewer note. Do not call it a final audit or a completed bank reconciliation.

**5:30–6:15 — Invalid input.** Import `invalid-bank.csv` with `receipts.csv`. Show the duplicate-ID error and confirm your prior decisions remain. Mention that impossible dates and malformed amounts have independent tests; this file stops at its first error.

**6:15–7:30 — Implementation and tradeoffs.** Show `src/engine.js`, particularly `analyze` and `applyDecisions`. Explain integer cents, UTC days, token overlap, deterministic matching, and why AI was not needed at runtime. Show `npm test` and the 13 passing tests. Mention that browser checks were also run.

**7:30–8:30 — What you would learn next.** Propose real reviewer interviews and a spreadsheet comparison. Give the provisional 25% reviewer-time threshold as a hypothesis, not an achieved saving. State what would make you stop. Explain deferred OCR, persistence, integrations, and access controls. Disclose AI assistance and that no employer code or data was reused.

Before recording, download the sample files from the import dialog. Rehearse once and verify the public link in a private/incognito window. Use only synthetic data on screen. You can keep this to five minutes by shortening orientation and source walkthrough; keep the normal and difficult cases.
