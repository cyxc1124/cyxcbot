"""Guard against Python-2-style multi-exception syntax regressing.

`except A, B:` is a SyntaxError on Python 3 and previously blocked importing
`utils` (via dynamic_api), which also broke `utils.douyin_api` plugin loads.
"""

from __future__ import annotations

import py_compile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

_CRITICAL_MODULES = (
    "utils/bilibili_api/dynamic_api.py",
    "utils/bilibili_api/live_models.py",
    "utils/douyin_api/__init__.py",
    "shared/monitor/system_metrics.py",
    "plugins/live_monitor/__init__.py",
    "plugins/live_monitor/danmaku_client.py",
    "plugins/status_check/status_checker.py",
    "plugins/group_special_title/handler.py",
    "plugins/douyin_link_parser/__init__.py",
)


def test_critical_modules_compile_under_python3():
    for relative in _CRITICAL_MODULES:
        path = _ROOT / relative
        assert path.is_file(), relative
        py_compile.compile(str(path), doraise=True)
