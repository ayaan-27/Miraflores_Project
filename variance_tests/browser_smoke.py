"""Browser acceptance; uses the actual model when run by the deployment CI job."""
import json
import os
from pathlib import Path
import shutil
import time

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/variance-browser"
OUT.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("VARIANCE_TEST_URL", "http://127.0.0.1:8501")
SAMPLES = ROOT / "variance_samples"

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=shutil.which("chromium"), headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 1050}, accept_downloads=True)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="networkidle")
    expect(page.get_by_role("heading", name="Month-end review", exact=True)).to_be_visible(timeout=30000)
    expect(page.get_by_text("$26,000.00", exact=True)).to_be_visible(timeout=30000)
    text = page.locator("body").inner_text()
    for brand in ["LedgerLens", "GreenGrowth", "LangGraph", "Ollama", "Ayaan"]:
        assert brand not in text, brand
    page.screenshot(path=str(OUT / "initial.png"), full_page=True)
    page.get_by_role("button", name="Investigate", exact=True).click()
    expect(page.get_by_role("button", name="Request evidence", exact=True)).to_be_visible(timeout=240000)
    expect(page.get_by_role("button", name="Approve workpaper", exact=True)).to_be_disabled()
    page.get_by_label("Reviewer", exact=True).fill("Demo reviewer")
    page.get_by_label("Review note", exact=True).fill("Please supply the renewal agreement and its service dates.")
    page.get_by_role("button", name="Request evidence", exact=True).click()
    expect(page.get_by_role("heading", name="Additional evidence", exact=True)).to_be_visible(timeout=30000)
    upload = page.get_by_test_id("stFileUploader").filter(has=page.get_by_text("Supporting PDF", exact=True)).locator("input[type=file]")
    upload.set_input_files(str(SAMPLES / "wrong-contract.pdf"))
    page.get_by_role("button", name="Add evidence", exact=True).click()
    expect(page.get_by_text("This case is waiting for AGR-SW-2026.", exact=True)).to_be_visible(timeout=30000)
    upload.set_input_files(str(SAMPLES / "software-contract.pdf"))
    page.get_by_role("button", name="Add evidence", exact=True).click()
    expect(page.get_by_role("heading", name="Proposed adjustment", exact=True)).to_be_visible(timeout=240000)
    expect(page.get_by_text("Balance after the proposed adjustment: $4,000.00. Entries remain drafts.", exact=True)).to_be_visible()
    page.get_by_label("Review note", exact=True).fill("Reviewed the source agreement, allocation, and balanced proposed journal.")
    page.get_by_role("button", name="Approve workpaper", exact=True).click()
    expect(page.get_by_test_id("stAlertContentSuccess").get_by_text("Workpaper approved", exact=True)).to_be_visible(timeout=30000)
    with page.expect_download() as d:
        page.get_by_role("button", name="Review record", exact=True).click()
    record = json.loads(Path(d.value.path()).read_text())
    assert record["analysis"]["adjustment_cents"] == 2200000
    assert record["analysis"]["adjusted_cents"] == 400000
    assert len(record["history"]) == 2 and record["round"] == 2
    assert record["completion"]["journal_posted"] is False
    expected_model = "Test planner" if os.environ.get("VARIANCE_BROWSER_MODE") == "test_double" else "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
    assert record["model"] == expected_model
    (OUT / "review.json").write_text(json.dumps(record, indent=2))
    with page.expect_download() as d:
        page.get_by_role("button", name="Workpaper PDF", exact=True).click()
    pdf = Path(d.value.path()).read_bytes()
    assert pdf.startswith(b"%PDF-")
    (OUT / "workpaper.pdf").write_bytes(pdf)
    with page.expect_download() as d:
        page.get_by_role("button", name="Journal CSV", exact=True).click()
    csv_text = Path(d.value.path()).read_text()
    assert "22000.00" in csv_text and "NOT POSTED" in csv_text
    page.reload(wait_until="networkidle")
    expect(page.get_by_test_id("stAlertContentSuccess").get_by_text("Workpaper approved", exact=True)).to_be_visible(timeout=30000)
    page.get_by_role("button", name="Import ledger", exact=True).click()
    ledger_input = page.get_by_test_id("stFileUploader").filter(has=page.get_by_text("Expense ledger CSV", exact=True)).locator("input[type=file]")
    ledger_input.set_input_files(str(SAMPLES / "invalid-ledger.csv"))
    page.get_by_role("button", name="Load ledger", exact=True).click()
    expect(page.get_by_text("Row 3: duplicate or invalid transaction ID.", exact=True)).to_be_visible(timeout=30000)
    expect(page.get_by_test_id("stAlertContentSuccess").get_by_text("Workpaper approved", exact=True)).to_be_visible()
    page.keyboard.press("Escape")
    page.screenshot(path=str(OUT / "completed.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(OUT / "mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile page overflow"
    assert not errors, errors
    print("PASS: actual Streamlit workflow, rejected wrong PDF, same-case evidence loop, approval gate, retained reload, invalid CSV rejection, and PDF/CSV/JSON exports.")
    browser.close()
