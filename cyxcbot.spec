# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CyxcBot Windows distribution."""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hiddenimports = [
    "nonebot.adapters.console",
    "nonebot.adapters.onebot.v11",
    "sqlalchemy.dialects.sqlite",
    "aiosqlite",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "passlib.handlers.bcrypt",
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "playwright",
    "playwright_stealth",
    "PIL",
    "feedparser",
    "psutil",
    "multipart",
    "jose",
]

for package in (
    "plugins",
    "admin",
    "shared",
    "utils",
    "nonebot_plugin_orm",
    "nonebot_plugin_apscheduler",
):
    hiddenimports += collect_submodules(package)

datas = [
    ("shared/db/migrations", "shared/db/migrations"),
    ("web/dist", "web/dist"),
    ("env.example", "."),
]

for package in ("alembic", "nonebot", "nonebot_plugin_orm"):
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
