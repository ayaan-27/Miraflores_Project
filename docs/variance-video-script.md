# Four-minute application walkthrough

Use this as a speaking guide. Read only the paragraphs marked **Say**; the click instructions are silent cues. The time ranges include brief pauses for clicking and showing results. Speak at a comfortable pace, around 135–145 words per minute. Rehearse once with a timer rather than rushing to match every timestamp.

Before recording, open the app and click **Reset sample**. Keep the browser on Software. Have your reviewer name and the two short notes at the end of this document ready to paste.

## 0:00–0:35 — What I built and why

**Show:** The initial Software account screen.

**Say:**

Hi, I'm Ayaan. I built Month-End Review to help an accountant work through an expense movement during the month-end close.

I've worked on systems that retrieve information from databases and supporting documents. That made me interested in what happens after you've found the number. Someone still has to explain it, check the evidence, and decide what to do. That's the part I wanted to make easier here.

## 0:35–1:05 — Start with a real decision

**Click:** **Investigate**. Point to the balances, the additional posting, and the unresolved service-period check.

**Say:**

Here, software expense has gone from two thousand dollars to twenty-six thousand. The app identifies an additional twenty-four-thousand-dollar renewal that explains the increase.

My first design decision was to keep the workflow focused: find the movement, check the evidence, calculate a treatment, and ask for a review. The interesting part is deciding whether we have enough support to move between those steps.

## 1:05–1:40 — Explain why the workflow pauses

**Show:** Approval is disabled. Enter your name and the evidence-request note, then click **Request evidence**.

**Say:**

The invoice supports the amount, but it doesn't establish when the service is delivered. Without those dates, we can't support a deferral calculation, so approval stays disabled.

I'll request the agreement. The case now waits for that specific record and keeps my request in its history. This is a draft request; nothing is emailed. I wanted missing evidence to be part of the workflow, with a clear way to continue when it arrives.

## 1:40–2:15 — Show the difficult case and recovery

**Click:** **Try mismatched agreement**, pause on the error, then **Use sample agreement**. Scroll to the proposed treatment.

**Say:**

I'll try the wrong agreement first. The app rejects it, and the pending case stays intact. A file arriving doesn't mean it answers the request.

Now I'll add the matching agreement. The checks compare the record with the expected invoice, vendor, entity, amount, and currency. It resumes the same case and recalculates the treatment. These are supplied structured sample records; I'm not claiming that the prototype authenticates documents.

## 2:15–3:05 — Explain the calculation and review

**Show:** The $22,000 proposal and $4,000 adjusted expense. Briefly expand **Allocation schedule**. Enter your name and the approval note, then click **Approve workpaper** and **Download PDF**.

**Say:**

The agreement covers twelve months starting in October. Under the sample policy, two thousand dollars belongs to each month, leaving twenty-two thousand for later periods.

The proposed entry debits prepaid services and credits software expense by twenty-two thousand. October expense becomes four thousand: the original recurring two thousand, plus this renewal's two-thousand-dollar share.

The new evidence requires a fresh review decision. I'll approve the workpaper, then download it. The PDF brings together the findings, evidence references, calculation, and decisions. There's also a journal CSV and a JSON review record. Approval never posts an entry to an accounting system.

## 3:05–3:25 — Show another valid outcome

**Click:** **Payroll**, then **Investigate**.

**Say:**

Payroll shows a different outcome. The eighteen-thousand-dollar increase is supported by an approved bonus earned in October. The app explains the movement and proposes no adjustment. I included this case because a large change alone shouldn't trigger a correcting entry.

## 3:25–4:00 — What I'd validate next

**Show:** The explained payroll case. Finish speaking without further clicks.

**Say:**

I kept the prototype runnable in a browser, with explicit rules and synthetic data. The main thing I wanted to demonstrate is the complete evidence-and-review loop.

Next, I'd watch reviewers work through redacted close examples and compare this with their spreadsheet process. I'd measure total review time and incorrect recommendations before expanding it. AI helped with implementation and drafting; those example checks are a starting point, not proof of production accuracy.

## Notes to paste — do not read aloud

Evidence request: Please provide the authorized agreement and service dates for this renewal.

Approval: Checked the agreement, allocation schedule, and balanced proposed journal. Approve workpaper only.

## Recording reminders — do not read aloud

- Use **Back** to return to the account overview while keeping a saved review, then **Resume review** to continue. Use **Reset sample** for a fresh take; refreshing preserves saved progress.
- Let the rejection message and proposed journal remain visible briefly. You do not need to read every check or source field.
- Download the PDF without opening another window during the recording; opening it is optional if you have time.
- The exact duration depends on your delivery and clicks. If a rehearsal runs long, omit the sentence beginning “There's also a journal CSV” and shorten the final paragraph before speaking faster.
