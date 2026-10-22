"""Run Playwright's downloader with the same Node trust policy as the app."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.security.playwright import node_environment  # noqa: E402

if __name__ == "__main__":
    subprocess.run(
        [sys.executable, "-m", "playwright", *sys.argv[1:]],
        env=node_environment(),
        check=True,
    )
