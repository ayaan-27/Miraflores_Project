---
title: LedgerLens Invoice Investigator
emoji: 🔎
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# LedgerLens — Invoice Exception Investigator

A four-stage LangGraph workflow powered by a local open-weight model. No inference API key is required.

1. **Read:** extract an actual invoice PDF and verify each value against a source quote.
2. **Investigate:** choose read-only tools for purchase orders, receiving, vendor details, payment history, and policy.
3. **Challenge:** recompute financial controls independently and return unsupported model findings for repair.
4. **Review:** pause for a human decision; resume the same case when additional evidence arrives.

## Try the complete workflow

Choose **An invoice ahead of delivery** and start an investigation. The synthetic invoice bills $10,000 for 100 lamps; the initial receiving evidence supports 80. The computed result is a hold with $2,000 missing receiving support.

Enter a demonstration reviewer name and note, then choose **Request more evidence**. Download the additional sample receiving report, upload that PDF in the waiting case, and resume. It supplies evidence for the remaining 20 lamps. The investigation reruns and requires a new review decision before a release recommendation.

Inspect the Evidence and Execution trace tabs. Download the PDF workpaper or full JSON review pack. No payment, email, ledger posting, or vendor update is initiated.

Other cases cover changed vendor-bank details, a plausible duplicate invoice, and a clean invoice. The uploaded samples and all internal-system records and policies are synthetic; these are not live accounting integrations.

## Runtime and scope

This Docker Space downloads the official `Qwen/Qwen2.5-1.5B-Instruct-GGUF` Q8 model and verifies its SHA-256 digest before use. The model runs on this server's CPU; no external model inference API is called. Initial startup and investigations can take several minutes on free CPU hardware. The model is Apache 2.0 licensed; see the official Qwen model repository for its terms.

This is an unauthenticated demonstration workspace. Documents, case history, and artifacts are readable through its API. Use synthetic documents only. Free-host storage can be reset by rebuilds or restarts. SQLite checkpoints demonstrate resumption on retained storage, not guaranteed cloud audit-history durability.

The application does not certify document authenticity, tax treatment, or payment correctness. Bank comparison uses account suffixes only. OCR, authenticated identities, real accounting integrations, and production access controls are outside this prototype.

Source: https://github.com/ayaan-27/Miraflores_Project/tree/feat/agentic-invoice-investigator
