# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CyxcBot Windows distribution."""

import importlib.util

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None


def collect_package_dir(package_name: str) -> list[tuple[str, str]]:
    """Copy an installed package tree as source files.

    NoneBot PluginLoader uses SourceFileLoader and requires .py files on disk;
    modules stored only in the PYZ archive will raise FileNotFoundError at runtime.
    """
    spec = importlib.util.find_spec(package_name)
    if spec is None or not spec.submodule_search_locations:
        return []
    return [(spec.submodule_search_locations[0], package_name)]


def collect_nonebot_builtin_plugins() -> list[tuple[str, str]]:
    """Copy nonebot/plugins for load_builtin_plugins (e.g. echo)."""
    spec = importlib.util.find_spec("nonebot")
    if spec is None or not spec.submodule_search_locations:
        return []
    from pathlib import Path

    plugins_dir = Path(spec.submodule_search_locations[0]) / "plugins"
    if plugins_dir.is_dir():
        return [(str(plugins_dir), "nonebot/plugins")]
    return []

# 需完整收集子模块的包（含 __getattr__ 懒加载或动态依赖）
_collect_packages = (
    # 项目代码
    "plugins",
    "admin",
    "shared",
    "utils",
    # NoneBot 生态
    "nonebot",
    "nonebot_plugin_orm",
    "nonebot_plugin_apscheduler",
    "nonebot_plugin_localstore",
    # console 适配器链：nonechat → textual → rich / pygments / markdown_it
    "nonechat",
    "textual",
    "rich",
    "pygments",
    "markdown_it",
    "linkify_it",
    "mdurl",
    # Web Admin
    "fastapi",
    "starlette",
    "uvicorn",
    "pydantic",
    "pydantic_core",
    "anyio",
    # 数据库
    "sqlalchemy",
    "alembic",
    "mako",
    # 业务依赖
    "playwright",
    "playwright_stealth",
    "apscheduler",
    "aiohttp",
    "loguru",
    "jose",
)

hiddenimports = [
    # 显式声明的入口 / C 扩展 / 易被静态分析遗漏的模块
    "nonebot.adapters.console",
    "nonebot.adapters.onebot.v11",
    "nonebot.plugins.echo",
    "sqlalchemy.dialects.sqlite",
    "aiosqlite",
    "greenlet",
    "bcrypt",
    "brotli",
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFilter",
    "PIL.ImageFont",
    "feedparser",
    "psutil",
    "multipart",
    "python_multipart",
    "dotenv",
    "tzdata",
    "zoneinfo",
    "certifi",
    "idna",
    "yarl",
    "multidict",
    "frozenlist",
    "aiosignal",
    "propcache",
    "attrs",
    "sniffio",
    "websockets",
    "click",
    "watchfiles",
    "annotated_types",
    "typing_extensions",
    "pyee",
    "msgpack",
    "nonestorage",
    # 顶层 shared 模块（防止 collect_submodules 漏扫新文件）
    "shared.status_check_policy",
    "shared.private_policy",
    "shared.group_policy",
    "shared.dynamic_subscription",
]

for package in _collect_packages:
    hiddenimports += collect_submodules(package)

datas = [
    # 项目源码目录：插件经 SourceFileLoader 从磁盘加载，依赖模块也须在 _internal 可导入
    ("shared", "shared"),
    ("admin", "admin"),
    ("utils", "utils"),
    ("plugins", "plugins"),
    ("web/dist", "web/dist"),
    ("env.example", "."),
]

# NoneBot 通过 SourceFileLoader 加载插件，必须把包源码放进 _internal
for _plugin_pkg in (
    "nonebot_plugin_orm",
    "nonebot_plugin_apscheduler",
    "nonebot_plugin_localstore",
    # stealth.py 在 import 时从包内 js/ 目录读取脚本
    "playwright_stealth",
):
    datas += collect_package_dir(_plugin_pkg)
datas += collect_nonebot_builtin_plugins()

_data_packages = (
    "alembic",
    "nonebot",
    "nonebot_plugin_orm",
    "textual",
    "playwright",
    "certifi",
    "tzdata",
)
for package in _data_packages:
    try:
        datas += collect_data_files(package)
    except Exception:
        pass

a = Analysis(
    ["bot.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["hooks"],
    hooksconfig={},
    runtime_hooks=[
        "hooks/pyi_rth_nonebot.py",
        "hooks/pyi_rth_build_info.py",
        "hooks/pyi_rth_playwright.py",
    ],
    excludes=["pytest", "ruff", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cyxcbot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="cyxcbot",
)
