"""Set PLAYWRIGHT_BROWSERS_PATH when running as a frozen executable."""

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    browser_path = Path(sys.executable).resolve().parent / "ms-playwright"
    if browser_path.is_dir():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_path)
