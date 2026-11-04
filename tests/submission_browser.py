"""Exercise the exact standalone HTML, including file:// in CI. Never uses a tunnel."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
url=os.environ.get('SUBMISSION_TEST_URL',(ROOT/'submission/OPEN_THIS.html').as_uri())
artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
with sync_playwright() as p:
    launch={'headless':True}
    if os.environ.get('CHROMIUM_PATH'):launch.update(executable_path=os.environ['CHROMIUM_PATH'],args=['--no-sandbox'])
    b=p.chromium.launch(**launch);context=b.new_context(accept_downloads=True)
    page=context.new_page();errors=[];network=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:network.append(r.url))
    page.goto(url);page.evaluate('localStorage.clear()');page.reload()
    expect(page.locator('#investigate')).to_be_visible();page.locator('#investigate').click()
    expect(page.locator('#approve')).to_be_disabled()
    page.locator('#reviewer').fill('Test reviewer');page.locator('#note').fill('Please supply service period support.');page.locator('#request_evidence').click()
    # Navigation must preserve an in-progress evidence request, including on reload.
    page.locator('#back').click()
    expect(page.locator('#investigate')).to_have_text('Resume review')
    expect(page.locator('#evidence-upload')).to_have_count(0)
    page.reload();expect(page.locator('#investigate')).to_have_text('Resume review')
    page.locator('#investigate').click()
    expect(page.locator('#content')).to_contain_text('Round 1 · awaiting evidence')
    expect(page.locator('#content')).to_contain_text('Please supply service period support.')
    page.locator('#invalid-evidence').click();expect(page.locator('#message')).to_contain_text('waiting for AGR-SW-2026')
    # A JSON upload exercises the real input path.
    page.locator('#evidence-upload').set_input_files(str(ROOT/'submission/software-agreement.json'))
    expect(page.locator('#content')).to_contain_text('$22,000.00');expect(page.locator('#content')).to_contain_text('$4,000.00')
    expect(page.locator('#approve')).to_be_enabled()
    page.locator('#reviewer').fill('Test reviewer');page.locator('#note').fill('Checked agreement, allocation and proposed journal.');page.locator('#approve').click()
    expect(page.locator('#content')).to_contain_text('Workpaper approved')
    page.reload();expect(page.locator('#content')).to_contain_text('Workpaper approved')
    for button,suffix in [('export-json','.json'),('export-csv','.csv'),('export-pdf','.pdf')]:
        with page.expect_download() as event:page.locator('#'+button).click()
        dl=event.value;dest=artifacts/('submission-'+dl.suggested_filename);dl.save_as(dest)
        assert dest.suffix==suffix and dest.stat().st_size>100
        if suffix=='.json':
            saved=json.loads(dest.read_text());assert saved['analysis']['adjustment_cents']==2200000 and len(saved['history'])==2
        if suffix=='.pdf':assert dest.read_bytes().startswith(b'%PDF')
    page.locator('#ledger-upload').set_input_files(str(ROOT/'submission/invalid-ledger.csv'))
    expect(page.locator('#message')).to_contain_text('duplicate');expect(page.locator('#content')).to_contain_text('Workpaper approved')
    page.screenshot(path=str(artifacts/'submission-desktop.png'),full_page=True)
    page.locator('[data-account="6200"]').click();page.locator('#investigate').click();expect(page.locator('#content')).to_contain_text('Movement explained')
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(artifacts/'submission-mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile horizontal overflow'
    assert not errors,errors
    # No external requests, fonts, model calls or assets are needed.
    if url.startswith('file:'):assert not [u for u in network if u.startswith(('http:','https:'))],network
    else:
        from urllib.parse import urlparse
        origin=urlparse(url).netloc
        assert not [u for u in network if u.startswith(('http:','https:')) and urlparse(u).netloc!=origin],network
    b.close()
print('Browser passed: evidence pause/resume, approval gates, persistence, atomic invalid CSV, PDF/CSV/JSON, mobile; no external asset requests.')
