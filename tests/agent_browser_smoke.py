"""Browser acceptance against an explicitly labeled model test double.

Run `python -m backend_tests.serve_fixture` on port 8003.
This validates real UI/API/tools/checkpoints, not live language-model quality.
"""

import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
URL = os.environ.get("LEDGERLENS_AGENT_TEST_URL", "http://127.0.0.1:8003")
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"]
    )
    page = browser.new_page(
        viewport={"width": 1536, "height": 1100}, accept_downloads=True
    )
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(URL, wait_until="networkidle")
    expect(page.locator(".case-card")).to_have_count(4)
    expect(page.locator("#global-notice")).to_contain_text("TEST HARNESS CONNECTED")
    page.locator("#start-run").click()
    expect(page.locator("#review-form")).to_be_visible(timeout=30000)
    expect(page.locator(".metrics")).to_contain_text("$2,000.00")
    expect(page.get_by_role("button", name="Recommend release")).to_be_disabled()
    expect(page.locator(".control")).to_have_count(6)
    page.locator('[data-tab="sources"]').click()
    expect(page.locator(".extracted-fields")).to_contain_text("INV-2048")
    page.locator('[data-field="total"]').click()
    expect(page.locator("#source-body")).to_contain_text("Invoice total: 10000.00")
    page.get_by_role("button", name="Close source", exact=True).click()
    page.locator('[data-tab="trace"]').click()
    expect(page.locator(".trace-entry")).not_to_have_count(0)
    page.locator('[data-tab="findings"]').click()
    page.locator("#reviewer-name").fill("Ayaan Khan")
    page.locator("#review-note").fill(
        "Please provide evidence for the remaining 20 units."
    )
    page.get_by_role("button", name="Request more evidence").click()
    expect(page.locator("#evidence-form")).to_be_visible(timeout=15000)
    page.locator("#open-request").click()
    expect(page.locator("#request-text")).to_have_value(
        "Please provide the remaining receiving evidence."
    )
    page.get_by_role("button", name="Close request", exact=True).click()
    page.locator("#evidence-file").set_input_files(
        str(ROOT / "agent_samples/remaining-delivery.pdf")
    )
    page.get_by_role("button", name="Add evidence & resume").click()
    expect(page.locator("#case-header")).to_contain_text("ROUND 2", timeout=15000)
    expect(page.locator("#review-form")).to_be_visible(timeout=15000)
    expect(page.locator(".metrics")).to_contain_text("$0.00")
    expect(page.get_by_role("button", name="Recommend release")).to_be_enabled()
    expect(page.locator(".history-card")).to_have_count(1)
    page.reload(wait_until="networkidle")
    # Re-open the same persisted run through the server-backed history.
    page.locator("#history-nav").click()
    page.locator("[data-run]").first.click()
    expect(page.locator("#review-form")).to_be_visible(timeout=15000)
    expect(page.locator("#case-header")).to_contain_text("ROUND 2")
    page.locator("#reviewer-name").fill("Ayaan Khan")
    page.locator("#review-note").fill(
        "Checked the additional report against the approved order."
    )
    page.get_by_role("button", name="Recommend release").click()
    expect(page.locator("#case-content")).to_contain_text(
        "Release recommended after human review", timeout=15000
    )
    with page.expect_download() as info:
        page.locator("#download-pack").click()
    pack = json.loads(Path(info.value.path()).read_text())
    assert pack["completion"]["result"] == "release_recommended"
    assert len(pack["review_history"]) == 2
    assert pack["mode"] == "test_double"
    assert len([e for e in pack["events"] if e["kind"] == "tool"]) == 10
    with page.expect_download() as pdf_info:
        page.get_by_role("link", name="Workpaper PDF").click()
    assert Path(pdf_info.value.path()).read_bytes().startswith(b"%PDF-")
    assert not errors, errors
    (ROOT / "artifacts").mkdir(exist_ok=True)
    page.evaluate("window.scrollTo(0,0)")
    page.screenshot(path=str(ROOT / "artifacts/agent-test-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(ROOT / "artifacts/agent-test-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
        "Mobile overflow"
    )
    print(
        "PASS: UI, actual tools, source dialog, trace, hold, evidence request, PDF reply, persisted resume, human approval, and exported pack. Model responses were explicit test doubles; live inference was not tested by this script."
    )
    browser.close()
