"""Start a clearly labeled UI test server, without model weights or live inference."""
from pathlib import Path
import tempfile

import uvicorn

from agent_workspace.api import create_app
from backend_tests.fakes import FixtureModel

if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="ledgerlens-browser-tests-") as temporary:
        uvicorn.run(
            create_app(model=FixtureModel(), data_dir=Path(temporary)),
            host="127.0.0.1",
            port=8003,
            log_level="warning",
        )
