"""Preserve the native process status and report the last observable phase to CI."""

from pathlib import Path
import json
import os
import subprocess
import sys

output = Path("artifacts/live-agent")
output.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, PYTHONFAULTHANDLER="1", PYTHONUNBUFFERED="1")
last_phase = "starting the local model"
tail = []
with (output / "execution.log").open("w") as log:
    process = subprocess.Popen(
        [sys.executable, "scripts/live_agent_smoke.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    for line in process.stdout:
        print(line, end="", flush=True)
        log.write(line)
        log.flush()
        tail.append(line.rstrip())
        tail = tail[-30:]
        try:
            event = json.loads(line)
            if isinstance(event, dict) and "title" in event:
                last_phase = event["title"]
        except ValueError:
            pass
    status = process.wait()
if status:
    detail = f"Exit {status}; last observable phase: {last_phase}. "
    detail += " | ".join(tail[-6:])[:1200]
    detail = detail.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print("::error title=Local-model execution diagnostic::" + detail, flush=True)
    raise SystemExit(status if status > 0 else 128 - status)
