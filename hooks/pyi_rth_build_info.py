"""Load bundled build metadata into environment variables."""

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    info_file = Path(sys.executable).resolve().parent / "build-info.env"
    if info_file.is_file():
        for line in info_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip()
