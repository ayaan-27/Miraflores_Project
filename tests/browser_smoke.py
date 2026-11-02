"""Optional real-browser acceptance test. Run with a local server on port 4173.
Requires Python playwright and a Chromium browser; see README.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get('LEDGERLENS_URL', 'http://127.0.0.1:4173')

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width':1440,'height':1000}, accept_downloads=True)
    errors, external = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: external.append(r.url) if not r.url.startswith(BASE_URL) and not r.url.startswith('data:') else None)
    page.goto(BASE_URL, wait_until='networkidle')
    expect(page.locator('.transaction')).to_have_count(12)
    expect(page.locator('#stats')).to_contain_text('$593.50')
    page.locator('[data-id="B004"]').click()
    expect(page.locator('#detail')).to_contain_text('Partial merchant')
    page.locator('#review-note').fill('Confirmed the merchant name against the original receipt.')
    page.get_by_role('button', name='Confirm receipt').click()
    expect(page.locator('#detail .decision-note')).to_contain_text('Confirmed by reviewer')
    expect(page.locator('#stats')).to_contain_text('$545.00')

    # A request retains an unresolved item and is reflected in the generated draft.
    page.locator('[data-id="B009"]').click()
    page.locator('#review-note').fill('Please provide the parking receipt and business purpose.')
    page.get_by_role('button', name='Mark requested').click()
    expect(page.locator('#open-count')).to_have_text('5')
    page.locator('#request-open').click()
    draft=page.locator('#request-text').input_value()
    assert 'B009' in draft and 'B004' not in draft
    assert 'parking receipt and business purpose' in draft
    page.get_by_role('button',name='Close request',exact=True).click()

    # Confirm one shared receipt; the second allocation is blocked with feedback.
    for tx in ['B005','B006']:
        page.locator(f'[data-id="{tx}"]').click()
        page.locator('#review-note').fill('Checked the supplies invoice and business purpose.')
        page.get_by_role('button',name='Confirm receipt').click()
    expect(page.locator('#decision-error')).to_contain_text('already allocated')

    # Invalid input preserves all existing decisions and the dataset.
    page.locator('#import-open').click()
    page.locator('#bank-file').set_input_files(str(ROOT/'samples/invalid-bank.csv'))
    page.locator('#receipt-file').set_input_files(str(ROOT/'samples/receipts.csv'))
    page.locator('#import-submit').click()
    expect(page.locator('#import-error')).to_contain_text('Duplicate ID')
    expect(page.locator('#all-count')).to_have_text('12')
    page.get_by_role('button',name='Close import',exact=True).click()
    page.locator('[data-id="B004"]').click()
    expect(page.locator('#detail .decision-note')).to_contain_text('Confirmed by reviewer')

    # Export actual browser downloads, validate current state and provenance.
    page.locator('#export-open').click()
    with page.expect_download() as info:
        page.locator('#download-json').click()
    snapshot=json.loads(Path(info.value.path()).read_text())
    assert snapshot['summary']['outstanding']==4
    assert snapshot['decisions']['B004']['receiptId']=='R004'
    assert snapshot['results'][3]['candidates'][0]['reference']=='team-coffee-receipt.jpg'
    with page.expect_download() as info:
        page.locator('#download-csv').click()
    assert 'PARTIAL_VENDOR' in Path(info.value.path()).read_text()
    page.get_by_role('button',name='Close export',exact=True).click()

    # Successful import replaces state; malicious merchant text is rendered as text.
    page.locator('#import-open').click()
    page.locator('#workspace-name').fill('Acceptance test')
    page.locator('#bank-file').set_input_files({'name':'bank.csv','mimeType':'text/csv','buffer':b'id,date,description,amount\nX,2026-09-01,<img src=x onerror=alert(1)>,10.00'})
    page.locator('#receipt-file').set_input_files(str(ROOT/'samples/receipts.csv'))
    page.locator('#import-submit').click()
    expect(page.locator('.transaction')).to_have_count(1)
    expect(page.locator('#client-name')).to_have_text('Acceptance test')
    expect(page.locator('#detail')).to_contain_text('<img src=x onerror=alert(1)>')
    assert page.locator('#detail img').count()==0
    assert not external, external
    assert not errors, errors

    # Reset and inspect desktop/mobile layouts, including modal focus trap.
    page.once('dialog', lambda d:d.accept())
    page.locator('#reset-demo').click()
    expect(page.locator('.transaction')).to_have_count(12)
    (ROOT/'artifacts').mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT/'artifacts/desktop.png'), full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(ROOT/'artifacts/mobile.png'), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow on mobile'
    page.locator('#import-open').click()
    page.keyboard.press('Escape')
    expect(page.locator('#import-dialog')).not_to_be_visible()
    print('PASS: demo, decision, requested state, shared-receipt rejection, atomic invalid import, exports, valid import, HTML injection protection, reset, mobile layout, dialog keyboard close; no page errors or external requests.')
    browser.close()
