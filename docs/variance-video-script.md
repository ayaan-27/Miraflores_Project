# Video narration — about 4 minutes

Open OPEN_THIS.html in a desktop browser. Reset the sample before recording. Replace the reviewer name with your own. Speak naturally; these are talking points.

**0:00–0:35 — Problem and motivation**

“I built a month-end review workflow for an accounting team. I have worked on systems that retrieve information across databases and connect documents to their supporting references. That made me interested in the next step: once we find a financial movement, how do we turn it into a supported decision? I chose a narrow expense-variance case so I could demonstrate the complete loop.”

**0:35–1:05 — Scope and thought process**

“My starting point was the reviewer’s decision, rather than a chatbot. The workflow has four stages: find the movement, check evidence, calculate a treatment, and obtain a review decision. I used explicit accounting rules here so the demo runs immediately without a server or model key. All records and the policy are synthetic. I have not validated GreenGrowth’s actual process yet.”

**1:05–1:40 — Investigate software**

Show Software, then click Investigate.

“Software expense increased from $2,000 to $26,000. The review checks whether one additional posting explains that movement, whether the source agrees with it, and whether the evidence supports a treatment. It finds a $24,000 renewal. But the invoice does not establish its service dates, so the app cannot yet recommend a deferral. Approval is disabled.”

Expand Evidence used briefly to show record IDs and fields.

**1:40–2:20 — Missing evidence and the difficult case**

Enter your name and a note such as “Please provide the authorized service agreement.” Click Request evidence. Click Try mismatched agreement, then Use sample agreement (or upload software-agreement.json).

“The case now waits for its specific agreement. This request is only a draft, and nothing is sent. A wrong agreement is rejected without changing the pending case. The matching agreement resumes this same case and preserves the earlier request. These are supplied structured evidence records; this release is not extracting PDFs or verifying authenticity.”

**2:20–3:00 — Calculation and human review**

Show the journal and allocation schedule. Enter your name and note, then Approve workpaper.

“The service runs for twelve months from October. The supplied policy allocates $2,000 to each month. That produces a $22,000 proposed deferral: debit prepaid services and credit software expense. October expense becomes $4,000, including the existing recurring $2,000. Calculations use integer cents. The new evidence requires a fresh review decision. Approval records my decision, but it never posts the journal.”

Download the PDF and briefly open it. Mention CSV and JSON outputs.

**3:00–3:25 — A movement that needs no adjustment**

Select Payroll and click Investigate.

“A large movement does not always mean an error. Here, an approved bonus earned in October explains the $18,000 change. The workflow proposes no adjustment.”

**3:25–4:00 — What I learned and would validate next**

“The useful unit is a supported decision with a visible evidence trail. A spreadsheet is a credible baseline, and I would compare total reviewer effort before adding integrations or model-driven search. Next, I would observe reviewers using redacted close examples and measure time, incorrect recommendations, and reopened cases. Broader document extraction and authenticated, durable records would come after that validation. AI assisted the implementation and drafting; these synthetic examples do not establish production accuracy.”
