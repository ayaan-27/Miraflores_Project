"""Run the tested Streamlit app with a temporary, account-free public tunnel.

Intended for a standard Linux Colab CPU runtime. The cell stays running until
interrupted. No Streamlit account, Cloudflare account, or model API key is used.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen
import venv
from zipfile import ZipFile

APP_COMMIT = "f9b329c4ff140ba762805fcd4c81ca9c8d7b93fd"
APP_SHA256 = "a6a8aeaf0e211c31a4c410fbbbd0bec85b8b0f25e837dea2066afba3b3ff504f"
APP_URL = f"https://codeload.github.com/ayaan-27/Miraflores_Project/zip/{APP_COMMIT}"
CLOUDFLARED_VERSION = "2026.10.7"
CLOUDFLARED_SHA256 = "1f99fb518b83dec2ba8d870a7cc991d82a77e6196295a3d2754ba17ab9f91872"
CLOUDFLARED_URL = f"https://github.com/cloudflare/cloudflared/releases/download/{CLOUDFLARED_VERSION}/cloudflared-linux-amd64"
PUBLIC_URL = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+)+\.trycloudflare\.com")


def verified_download(url, expected):
    with urlopen(url, timeout=90) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("Download checksum did not match. Nothing from this download was executed.")
    return data


def require_tunnel_access():
    policy_file = Path("/etc/codex/network-policy.json")
    if policy_file.exists():
        policy = json.loads(policy_file.read_text())
        grants = policy.get("tcp_network_access", {})
        if not grants.get("domains") and not grants.get("ip_ranges"):
            raise RuntimeError("This managed workspace does not permit public tunnel connections. Open the notebook in Colab and select Run all.")


def prepare(base: Path):
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise RuntimeError("Use the standard Colab CPU runtime (Linux x86-64).")
    base.mkdir(parents=True, exist_ok=True)
    checkout = base / ("source-" + APP_COMMIT[:12])
    if not (checkout / "streamlit_app.py").is_file():
        data = verified_download(APP_URL, APP_SHA256)
        checkout.mkdir(exist_ok=True)
        with ZipFile(BytesIO(data)) as archive:
            prefix = archive.namelist()[0].split("/")[0] + "/"
            for item in archive.infolist():
                relative = Path(item.filename.removeprefix(prefix))
                if not relative.parts or relative == Path("."):
                    continue
                if relative.is_absolute() or ".." in relative.parts or stat.S_ISLNK(item.external_attr >> 16):
                    raise RuntimeError("Unexpected path in the source archive.")
                target = checkout / relative
                if item.is_dir(): target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(item))
    environment = base / (f"python-{sys.version_info.major}{sys.version_info.minor}")
    python = environment / "bin/python"
    stamp = environment / ".installed"
    lock_hash = hashlib.sha256((checkout / "requirements-variance-lock.txt").read_bytes()).hexdigest()
    if not stamp.is_file() or stamp.read_text() != lock_hash:
        print("Installing the app. The first run can take a few minutes…", flush=True)
        venv.EnvBuilder(with_pip=False).create(environment)
        env = dict(os.environ, PATH=str(environment / "bin") + os.pathsep + os.environ.get("PATH", ""), CC="gcc", CXX="g++", CMAKE_BUILD_PARALLEL_LEVEL="1", CMAKE_ARGS="-DGGML_CUDA=OFF -DGGML_NATIVE=OFF")
        with (base / "setup.log").open("w") as log:
            for command in [
                [sys.executable, "-m", "pip", "--python", str(python), "install", "--disable-pip-version-check", "pip", "cmake==3.31.6"],
                [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(checkout / "requirements.txt")],
            ]:
                result = subprocess.run(command, cwd=checkout, env=env, stdout=log, stderr=subprocess.STDOUT)
                if result.returncode:
                    log.flush()
                    raise RuntimeError("App installation failed:\n" + (base / "setup.log").read_text()[-3500:])
        stamp.write_text(lock_hash)
    binary = base / "cloudflared"
    if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != CLOUDFLARED_SHA256:
        binary.write_bytes(verified_download(CLOUDFLARED_URL, CLOUDFLARED_SHA256))
        binary.chmod(0o755)
    return checkout, python, binary


def wait_for_health(url, process, timeout=45):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError("A demo process stopped. Inspect its log in the notebook's work folder.")
        try:
            with urlopen(url.rstrip("/") + "/_stcore/health", timeout=5) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.25)
    raise RuntimeError("The demo did not become reachable in time. Rerun the cell to try again.")


def start_app(base, checkout, python):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0)); port = listener.getsockname()[1]
    with (base / "streamlit.log").open("w") as log:
        app = subprocess.Popen([str(python), "-m", "streamlit", "run", "streamlit_app.py", "--server.address", "127.0.0.1", "--server.port", str(port), "--server.headless", "true"], cwd=checkout, env=dict(os.environ, VARIANCE_DATA_DIR=str(base / "data")), stdout=log, stderr=subprocess.STDOUT)
    try:
        wait_for_health(f"http://127.0.0.1:{port}", app)
    except BaseException:
        stop(app)
        raise
    return app, port


def start_tunnel(base, binary, port):
    require_tunnel_access()
    config = base / "quick-tunnel.yml"; config.write_text("{}\n")
    path = base / "tunnel.log"
    with path.open("w") as log:
        tunnel = subprocess.Popen([str(binary), "--no-autoupdate", "tunnel", "--config", str(config), "--url", f"http://127.0.0.1:{port}", "--protocol", "http2"], stdout=log, stderr=subprocess.STDOUT)
    try:
        end = time.monotonic() + 45
        while time.monotonic() < end:
            if tunnel.poll() is not None:
                raise RuntimeError("The public tunnel stopped:\n" + path.read_text()[-2500:])
            match = PUBLIC_URL.search(path.read_text())
            if match:
                url = match.group()
                wait_for_health(url, tunnel)
                return tunnel, url
            time.sleep(0.25)
        raise RuntimeError("No public tunnel URL was issued. Rerun the cell to try again.")
    except BaseException:
        stop(tunnel)
        raise


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()


def main():
    require_tunnel_access()
    base = Path(tempfile.gettempdir()) / "month-end-notebook-demo"
    app = tunnel = None
    try:
        checkout, python, binary = prepare(base)
        print("Starting the app…", flush=True)
        app, port = start_app(base, checkout, python)
        tunnel, url = start_tunnel(base, binary, port)
        print("\nOpen your demo:\n" + url + "\n\nKeep this runtime running. Interrupt this cell to stop the demo.", flush=True)
        while app.poll() is None and tunnel.poll() is None:
            time.sleep(1)
        raise RuntimeError("The demo process stopped. Rerun the cell to start a new public link.")
    except KeyboardInterrupt:
        print("Demo stopped.")
    finally:
        stop(tunnel); stop(app)


if __name__ == "__main__":
    main()
