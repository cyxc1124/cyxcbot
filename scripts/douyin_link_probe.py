#!/usr/bin/env python3
"""Probe Douyin link-parser plugin chain without QQ messages.

镜像 ``group_guard`` / ``private_guard`` + ``plugins/douyin_link_parser``：
消息策略 → 抖音链接策略 → Cookie → 抽链 → resolve_and_download → 构建回复。
不真正调用 ``send_*_msg``，只打印将发送的 Message 与下载结果。

Examples::

    # 完整插件门闸（Cookie / 策略来自本地 DB）
    ./.venv/bin/python scripts/douyin_link_probe.py run \\
        --text '1.51 复制打开抖音，看看【蓝牙色张三的作品】… https://v.douyin.com/ZV5pSh1luFo/ 02/10' \\
        --group-id 123456789 --user-id 987654321

    # 私聊策略
    ./.venv/bin/python scripts/douyin_link_probe.py run \\
        --text 'https://v.douyin.com/ZV5pSh1luFo/' \\
        --user-id 987654321 --private

    # 跳过群/好友与抖音策略，只测下载（Cookie 可用 --cookie / DOUYIN_COOKIE / DB）
    ./.venv/bin/python scripts/douyin_link_probe.py direct \\
        --text 'https://v.douyin.com/ZV5pSh1luFo/' \\
        --keep ./tmp_douyin.mp4

    # 查看当前抖音策略与 Cookie 是否已配置
    ./.venv/bin/python scripts/douyin_link_probe.py status
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ORM_SYNC_INITIALIZED = False
_ORM_LIFESPAN_ACTIVE = False
_CONFIG_LOADED = False

_DEFAULT_SHARE_TEXT = (
    "1.51 复制打开抖音，看看【蓝牙色张三的作品】海南人=猫娘 # 猫娘 # 原创# 抽象# 搞笑#... "
    "https://v.douyin.com/ZV5pSh1luFo/ 02/10 Gic:/ R@x.FU :7pm"
)


def _ensure_sqlite_parent_dir(url: str) -> None:
    if not url.lower().startswith("sqlite") or "///" not in url:
        return
    db_part = url.split("///", 1)[1].split("?", 1)[0]
    if not db_part or db_part == ":memory:":
        return
    db_path = Path(db_part)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _configure_alembic_auto_upgrade() -> None:
    import click

    _confirm = click.confirm

    def _auto_confirm(message: str, *args, **kwargs) -> bool:
        if "迁移" in message:
            return True
        return _confirm(message, *args, **kwargs)

    click.confirm = _auto_confirm  # type: ignore[method-assign]


def _setup_runtime() -> None:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    env_path = ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path)
        except ImportError:
            pass
    if not os.getenv("SQLALCHEMY_DATABASE_URL"):
        os.environ["SQLALCHEMY_DATABASE_URL"] = "sqlite+aiosqlite:///data/cyxcbot.db"


def _init_orm_sync() -> None:
    """Sync ORM/Alembic setup; must run before ``asyncio.run()`` (see ``bot.py``)."""
    global _ORM_SYNC_INITIALIZED
    if _ORM_SYNC_INITIALIZED:
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("_init_orm_sync() must run before asyncio.run()")

    import nonebot

    from shared.db.alembic_repair import repair_alembic_version_if_needed

    url = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite:///data/cyxcbot.db")
    _ensure_sqlite_parent_dir(url)
    repair_alembic_version_if_needed(url)
    _configure_alembic_auto_upgrade()
    migrations = ROOT / "shared" / "db" / "migrations"
    nonebot.init(
        sqlalchemy_database_url=url,
        alembic_startup_check=True,
        alembic_version_locations=migrations,
    )
    nonebot.load_plugin("nonebot_plugin_orm")
    import shared.db.models  # noqa: F401

    _ORM_SYNC_INITIALIZED = True


async def _start_orm_lifespan() -> None:
    global _ORM_LIFESPAN_ACTIVE
    if _ORM_LIFESPAN_ACTIVE:
        return
    if not _ORM_SYNC_INITIALIZED:
        raise RuntimeError("call _init_orm_sync() before _start_orm_lifespan()")

    import nonebot

    # ponytail: bot.run() triggers the same private lifespan; probe has no long-lived driver.
    await nonebot.get_driver()._lifespan.startup()
    _ORM_LIFESPAN_ACTIVE = True


async def _stop_orm_lifespan() -> None:
    global _ORM_LIFESPAN_ACTIVE
    if not _ORM_LIFESPAN_ACTIVE:
        return

    import nonebot

    await nonebot.get_driver()._lifespan.shutdown()
    _ORM_LIFESPAN_ACTIVE = False


async def _load_snapshot():
    global _CONFIG_LOADED
    if not _ORM_SYNC_INITIALIZED:
        raise RuntimeError("call _init_orm_sync() before asyncio.run()")
    if not _ORM_LIFESPAN_ACTIVE:
        raise RuntimeError("call _start_orm_lifespan() before _load_snapshot()")

    from shared.config.service import get_config_service

    if not _CONFIG_LOADED:
        await get_config_service().load()
        _CONFIG_LOADED = True
    return get_config_service().get_snapshot()


def _mask_cookie(cookie: str) -> str:
    value = (cookie or "").strip()
    if not value:
        return "(empty)"
    if len(value) <= 24:
        return f"{value[:4]}…({len(value)} chars)"
    return f"{value[:12]}…{value[-8:]} ({len(value)} chars)"


def _resolve_cookie(args: argparse.Namespace, snap=None) -> str:
    """Priority: --cookie > DOUYIN_COOKIE > DB snapshot."""
    if getattr(args, "cookie", None):
        return str(args.cookie).strip()
    env_cookie = os.getenv("DOUYIN_COOKIE", "").strip()
    if env_cookie:
        return env_cookie
    if snap is not None:
        return str(getattr(snap, "douyin_cookie", "") or "").strip()
    return ""


def _print_status(snap) -> None:
    from utils.douyin_api import validate_cookie_header

    cookie = str(snap.douyin_cookie or "")
    print(f"Cookie configured: {bool(snap.douyin_cookie_set)}")
    print(f"Cookie preview: {_mask_cookie(cookie)}")
    print(f"Cookie keys valid: {validate_cookie_header(cookie)}")

    groups = snap.douyin_link_parser_group_policies
    users = snap.douyin_link_parser_user_policies
    print(f"Group policies: {len(groups)}")
    for gid, rec in sorted(groups.items()):
        print(f"  group={gid} enabled={rec.enabled}")
    print(f"User policies: {len(users)}")
    for uid, rec in sorted(users.items()):
        name = f" name={rec.name!r}" if rec.name else ""
        print(f"  user={uid} enabled={rec.enabled}{name}")


def _policy_ok(snap, *, group_id: str | None, user_id: str, private: bool) -> bool:
    from shared.config.douyin_link_parser_policy import (
        resolve_douyin_link_parser_policy,
    )
    from shared.group_policy import is_group_message_enabled_from_snapshot
    from shared.private_policy import is_private_message_enabled_from_snapshot

    if private:
        if not is_private_message_enabled_from_snapshot(user_id, snap):
            print(
                f"[BLOCK] private message policy: user={user_id} "
                "(bot would ignore at private_guard)"
            )
            return False
        print(f"[OK] private message policy: user={user_id}")
        scope = resolve_douyin_link_parser_policy(
            snap, user_id=user_id, is_private=True
        )
        if not scope.enabled:
            print(
                f"[BLOCK] douyin link policy: user={user_id} "
                "(bot would silently ignore)"
            )
            return False
        print(f"[OK] douyin link policy: user={user_id}")
        return True

    gid = group_id or ""
    if not is_group_message_enabled_from_snapshot(gid, snap):
        print(
            f"[BLOCK] group message policy: group={gid} "
            "(bot would ignore at group_guard)"
        )
        return False
    print(f"[OK] group message policy: group={gid}")
    scope = resolve_douyin_link_parser_policy(
        snap, group_id=gid, user_id=user_id, is_private=False
    )
    if not scope.enabled:
        print(f"[BLOCK] douyin link policy: group={gid} (bot would silently ignore)")
        return False
    print(f"[OK] douyin link policy: group={gid}")
    return True


def _print_message(message) -> None:
    print("[MESSAGE] would send via send_group_msg / send_private_msg:")
    for i, seg in enumerate(message):
        if seg.type == "video":
            file_val = seg.data.get("file", "")
            print(f"  [{i}] video file={file_val!r}")
        elif seg.type == "text":
            text = seg.data.get("text", str(seg))
            preview = text if len(text) <= 200 else text[:200] + "…"
            print(f"  [{i}] text={preview!r}")
        else:
            print(f"  [{i}] {seg.type}={seg.data!r}")


def _maybe_keep(file_path: Path, keep: str | None) -> None:
    if not keep:
        return
    dest = Path(keep).expanduser()
    if dest.is_dir() or str(keep).endswith(("/", "\\")):
        dest.mkdir(parents=True, exist_ok=True)
        dest = dest / file_path.name
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, dest)
    print(f"[KEEP] copied video → {dest.resolve()} ({dest.stat().st_size} bytes)")


def _cleanup_temp(file_path: Path) -> None:
    try:
        parent = file_path.parent
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        if parent.name.startswith("douyin_") and parent.exists():
            shutil.rmtree(parent, ignore_errors=True)
    except Exception as exc:
        print(f"[WARN] cleanup failed: {exc}")


async def _run_download_and_build(
    *,
    text: str,
    cookie: str,
    templates,
    keep: str | None,
) -> int:
    from plugins.douyin_link_parser.sender import build_douyin_link_message
    from utils.douyin_api import (
        DouyinResolveError,
        extract_douyin_urls,
        resolve_and_download,
        validate_cookie_header,
    )

    urls = extract_douyin_urls(text)
    if not urls:
        print(f"[BLOCK] no Douyin URL in text={text[:120]!r}")
        return 1
    print(f"[OK] extracted urls={urls}")

    print(f"[OK] cookie preview={_mask_cookie(cookie)}")
    if not cookie:
        print(
            "[WARN] Cookie empty (--cookie / DOUYIN_COOKIE / DB); "
            "will try as guest (may fail)"
        )
    elif not validate_cookie_header(cookie):
        print(
            "[WARN] Cookie missing suggested keys: ttwid, odin_tt, passport_csrf_token; "
            "will continue anyway"
        )
    else:
        print("[OK] cookie keys valid")

    result = None
    try:
        print("[STEP] resolve_and_download …")
        result = await resolve_and_download(text, cookie)
        size = result.file_path.stat().st_size if result.file_path.exists() else 0
        print(
            f"[OK] downloaded aweme_id={result.aweme_id} "
            f"author={result.author!r} title={result.title[:60]!r} "
            f"size={size} path={result.file_path}"
        )
        print(f"[OK] share_url={result.share_url}")

        reply = build_douyin_link_message(result, templates)
        _print_message(reply)
        _maybe_keep(result.file_path, keep)
        return 0
    except DouyinResolveError as exc:
        print(f"[FAIL] DouyinResolveError: {exc}")
        return 1
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        raise
    finally:
        if result is not None:
            _cleanup_temp(result.file_path)


async def _run_plugin_chain(args: argparse.Namespace) -> int:
    snap = await _load_snapshot()

    group_id = str(args.group_id).strip() if args.group_id else None
    user_id = str(args.user_id).strip()
    text = (args.text or _DEFAULT_SHARE_TEXT).strip()
    private = bool(args.private)

    print(f"[IN] scope={'private' if private else f'group={group_id}'} user={user_id}")
    print(f"[IN] text={text[:160]!r}")

    if not args.skip_policy and not _policy_ok(
        snap, group_id=group_id, user_id=user_id, private=private
    ):
        return 1
    if args.skip_policy:
        print("[OK] skip-policy: message / douyin gates bypassed")

    cookie = _resolve_cookie(args, snap)

    return await _run_download_and_build(
        text=text,
        cookie=cookie,
        templates=snap.douyin_link_message_templates,
        keep=args.keep,
    )


async def _run_direct(args: argparse.Namespace) -> int:
    """Skip DB policy gates; still prefer DB cookie unless overridden."""
    from shared.config.message_templates import DouyinLinkMessageTemplates

    text = (args.text or _DEFAULT_SHARE_TEXT).strip()
    print(f"[IN] direct mode text={text[:160]!r}")

    snap = None
    templates = DouyinLinkMessageTemplates()
    if _ORM_SYNC_INITIALIZED:
        snap = await _load_snapshot()
        templates = snap.douyin_link_message_templates

    cookie = _resolve_cookie(args, snap)
    return await _run_download_and_build(
        text=text,
        cookie=cookie,
        templates=templates,
        keep=args.keep,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show Douyin cookie + link policies from DB")

    run = sub.add_parser("run", help="Simulate douyin_link_parser plugin chain")
    run.add_argument(
        "--text",
        default=_DEFAULT_SHARE_TEXT,
        help="Simulated QQ message body (share text with v.douyin.com link)",
    )
    run.add_argument(
        "--group-id", help="Simulated group_id (required unless --private)"
    )
    run.add_argument("--user-id", required=True, help="Simulated QQ user_id")
    run.add_argument(
        "--private",
        action="store_true",
        help="Simulate private chat policy instead of group",
    )
    run.add_argument(
        "--skip-policy",
        action="store_true",
        help="Bypass group/private + douyin link policy checks",
    )
    run.add_argument(
        "--cookie",
        help="Override Cookie header (else DOUYIN_COOKIE env, else DB)",
    )
    run.add_argument(
        "--keep",
        help="Copy downloaded mp4 to this path/dir before temp cleanup",
    )

    direct = sub.add_parser(
        "direct", help="Download only (skip message/douyin policy gates)"
    )
    direct.add_argument(
        "--text",
        default=_DEFAULT_SHARE_TEXT,
        help="Share text or Douyin URL",
    )
    direct.add_argument(
        "--cookie",
        help="Cookie header (else DOUYIN_COOKIE env, else DB if available)",
    )
    direct.add_argument(
        "--keep",
        help="Copy downloaded mp4 to this path/dir before temp cleanup",
    )
    direct.add_argument(
        "--no-db",
        action="store_true",
        help="Do not init ORM/DB (requires --cookie or DOUYIN_COOKIE)",
    )

    return parser


def _validate_run_args(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    if not args.private and not args.group_id:
        parser.error("run requires --group-id unless --private is set")


async def _async_main(args: argparse.Namespace) -> int:
    needs_orm = args.cmd in {"status", "run"} or (
        args.cmd == "direct" and not args.no_db
    )
    if needs_orm:
        await _start_orm_lifespan()
    try:
        if args.cmd == "status":
            snap = await _load_snapshot()
            _print_status(snap)
            return 0
        if args.cmd == "run":
            return await _run_plugin_chain(args)
        if args.cmd == "direct":
            return await _run_direct(args)
        raise RuntimeError(f"unknown command: {args.cmd}")
    finally:
        if needs_orm:
            await _stop_orm_lifespan()


def main() -> None:
    _setup_runtime()
    parser = _build_parser()
    args = parser.parse_args()

    if args.cmd == "run":
        _validate_run_args(args, parser)

    needs_orm = args.cmd in {"status", "run"} or (
        args.cmd == "direct" and not getattr(args, "no_db", False)
    )
    if needs_orm:
        _init_orm_sync()

    raise SystemExit(asyncio.run(_async_main(args)))


if __name__ == "__main__":
    main()
