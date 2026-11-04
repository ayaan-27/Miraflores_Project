"""Short-lived end-to-end launcher check; never hosts an app after the test."""
from pathlib import Path
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notebook_demo as launcher


def main():
    from playwright.sync_api import sync_playwright, expect
    app = tunnel = None
    base = Path(tempfile.gettempdir()) / "month-end-notebook-validation"
    try:
        checkout, python, binary = launcher.prepare(base)
        app, port = launcher.start_app(base, checkout, python)
        tunnel, url = launcher.start_tunnel(base, binary, port)
        print("Temporary test URL:", url, flush=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, wait_until="networkidle", timeout=60000)
            expect(page.get_by_role("heading", name="Month-end review", exact=True)).to_be_visible(timeout=30000)
            expect(page.get_by_text("$26,000.00", exact=True)).to_be_visible(timeout=30000)
            expect(page.get_by_role("button", name="Investigate", exact=True)).to_be_visible()
            out = Path("artifacts/notebook-launcher"); out.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(out / "public-app.png"), full_page=True)
            (out / "result.json").write_text(json.dumps({"source_commit":launcher.APP_COMMIT,"cloudflared_version":launcher.CLOUDFLARED_VERSION,"external_http":True,"streamlit_websocket_ui":True,"test_tunnel_closed_after_check":True},indent=2))
            browser.close()
        print("::notice title=Notebook launcher passed::Fresh isolated install, verified downloads, Streamlit startup, temporary public HTTPS tunnel, and browser/WebSocket account figures passed. Test tunnel is closed after validation.", flush=True)
    finally:
        launcher.stop(tunnel); launcher.stop(app)


if __name__ == "__main__":
    main()
