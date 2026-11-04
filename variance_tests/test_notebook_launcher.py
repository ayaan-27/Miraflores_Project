import importlib.util
import json
from pathlib import Path
import sys

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/notebook_demo.py"
spec = importlib.util.spec_from_file_location("notebook_demo", PATH)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_public_url_parser_rejects_the_tunnel_api_endpoint():
    assert launcher.PUBLIC_URL.search('Post "https://api.trycloudflare.com/tunnel" failed') is None
    assert launcher.PUBLIC_URL.search('Visit https://plain-silver-demo-stream.trycloudflare.com').group() == 'https://plain-silver-demo-stream.trycloudflare.com'


def test_verified_download_refuses_changed_artifact(monkeypatch):
    from io import BytesIO
    monkeypatch.setattr(launcher, "urlopen", lambda *a, **k: BytesIO(b"changed"))
    with pytest.raises(RuntimeError, match="checksum"):
        launcher.verified_download("https://example.test/artifact", "0" * 64)


def test_does_not_try_tunneling_from_restricted_managed_workspace(monkeypatch, tmp_path):
    policy = tmp_path / "network-policy.json"
    policy.write_text(json.dumps({"tcp_network_access": {"domains": [], "ip_ranges": []}}))
    original = launcher.Path
    monkeypatch.setattr(launcher, "Path", lambda path: policy if str(path) == "/etc/codex/network-policy.json" else original(path))
    with pytest.raises(RuntimeError, match="does not permit"):
        launcher.require_tunnel_access()


def test_notebook_cell_is_valid_python_and_contains_the_correct_script_hash():
    import hashlib
    p = PATH.parents[1] / "notebooks/Month_end_review.ipynb"
    notebook = json.loads(p.read_text())
    cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    assert len(cells) == 1
    code = "".join(cells[0]["source"])
    compile(code, "notebook cell", "exec")
    assert hashlib.sha256(PATH.read_bytes()).hexdigest() in code
