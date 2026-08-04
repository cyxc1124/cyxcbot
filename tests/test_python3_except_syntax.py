"""Guard against Python-2-style multi-exception syntax regressing.

`except A, B:` is a SyntaxError on Python 3. It previously blocked importing
`utils` (via dynamic_api) and, after #209's format pass, also broke
`utils.douyin_api.client` / `video_urls` which are pulled in by resolve.
"""

from __future__ import annotations

import py_compile
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

_CRITICAL_MODULES = (
    "utils/bilibili_api/dynamic_api.py",
    "utils/bilibili_api/live_models.py",
    "utils/douyin_api/__init__.py",
    "utils/douyin_api/client.py",
    "utils/douyin_api/video_urls.py",
    "utils/douyin_api/resolve.py",
    "shared/monitor/system_metrics.py",
    "plugins/live_monitor/__init__.py",
    "plugins/live_monitor/danmaku_client.py",
    "plugins/status_check/status_checker.py",
    "plugins/group_special_title/handler.py",
    "plugins/douyin_link_parser/__init__.py",
)

# `except A, B:` without parentheses around the type list.
_BARE_MULTI_EXCEPT = re.compile(
    r"^\s*except\s+[A-Za-z_][A-Za-z0-9_.]*\s*,",
    re.M,
)


def test_critical_modules_compile_under_python3():
    for relative in _CRITICAL_MODULES:
        path = _ROOT / relative
        assert path.is_file(), relative
        py_compile.compile(str(path), doraise=True)


def test_repo_has_no_bare_multi_except_clauses():
    offenders: list[str] = []
    skip_parts = {".venv", "node_modules", ".git", "__pycache__"}
    for path in _ROOT.rglob("*.py"):
        if skip_parts.intersection(path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if not _BARE_MULTI_EXCEPT.search(line):
                continue
            # Parenthesized forms are valid: except (A, B):
            type_part = line.split("except", 1)[1].split(":", 1)[0]
            if "(" in type_part:
                continue
            offenders.append(f"{path.relative_to(_ROOT)}:{lineno}:{line.strip()}")
    assert not offenders, "Python-2-style except clauses:\n" + "\n".join(offenders)
