"""Fetch official open weights with TLS and repository SHA-256 verification."""

from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_workspace.model import DEFAULT_MODEL_PATH, MODEL_REPO, MODEL_FILE

metadata_url = f"https://huggingface.co/api/models/{MODEL_REPO}/tree/main"
with urllib.request.urlopen(metadata_url, timeout=30) as response:
    files = json.load(response)
record = next((entry for entry in files if entry.get("path") == MODEL_FILE), None)
if record is None or not record.get("lfs", {}).get("oid"):
    raise SystemExit(
        "Official model metadata did not supply a SHA-256 digest. Download stopped."
    )
expected = record["lfs"]["oid"].removeprefix("sha256:")
expected_size = record["size"]
destination = Path(os.environ.get("LEDGERLENS_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
destination.parent.mkdir(parents=True, exist_ok=True)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


if (
    destination.exists()
    and destination.stat().st_size == expected_size
    and digest(destination) == expected
):
    print("Verified existing official model:", destination)
    raise SystemExit(0)

url = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}"
temporary_path = None
try:
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, suffix=".download", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        with urllib.request.urlopen(url, timeout=60) as response:
            total = 0
            next_notice = 128 * 1024 * 1024
            while chunk := response.read(4 * 1024 * 1024):
                temporary.write(chunk)
                total += len(chunk)
                if total > expected_size:
                    raise ValueError(
                        "Model download exceeded the official artifact size."
                    )
                if total >= next_notice:
                    print(f"Downloaded {total // (1024 * 1024)} MiB", flush=True)
                    next_notice += 128 * 1024 * 1024
    if total != expected_size or digest(temporary_path) != expected:
        raise ValueError(
            "Model checksum or size verification failed; artifact was not installed."
        )
    temporary_path.replace(destination)
    temporary_path = None
    destination.with_suffix(".verified.json").write_text(
        json.dumps(
            {
                "repository": MODEL_REPO,
                "file": MODEL_FILE,
                "sha256": expected,
                "size": expected_size,
            },
            indent=2,
        )
    )
    print("Official model verified and installed:", destination)
finally:
    if temporary_path is not None:
        temporary_path.unlink(missing_ok=True)
