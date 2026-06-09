# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CyxcBot Windows distribution."""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

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
    "passlib",
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
    "passlib.handlers.bcrypt",
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
]

for package in _collect_packages:
    hiddenimports += collect_submodules(package)

datas = [
    ("shared/db/migrations", "shared/db/migrations"),
    ("web/dist", "web/dist"),
    ("env.example", "."),
]

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
        "hooks/pyi_rth_build_info.py",
        "hooks/pyi_rth_playwright.py",
    ],
    excludes=["pytest", "flake8", "tkinter"],
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
