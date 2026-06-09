"""Ensure PyInstaller bundle can resolve project packages from _MEIPASS."""

import sys

if getattr(sys, "frozen", False):
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass and meipass not in sys.path:
        sys.path.insert(0, meipass)
