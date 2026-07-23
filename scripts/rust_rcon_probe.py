#!/usr/bin/env python3
"""Probe Rust RCON plugin chain without QQ messages.

可在生产 bot 主机上使用（排查绑定、策略、商城 giveto 等）；推荐 ``run`` 子命令，
凭据来自数据库，无需在命令行传 RCON 密码。

Mirrors ``group_guard`` / ``private_guard`` + ``plugins/rust_rcon/__init__.py``:
message policy → RCON policy → alias match → QQ whitelist → ``execute_rcon_command``.

Examples::

    ./.venv/bin/python scripts/rust_rcon_probe.py list

    ./.venv/bin/python scripts/rust_rcon_probe.py run \\
        --text "rcon1 status" --group-id 123456789 --user-id 987654321

    ./.venv/bin/python scripts/rust_rcon_probe.py run \\
        --binding-id 1 --command "giveto 76561198000000000 wood 1" \\
        --group-id 123456789 --user-id 987654321

    ./.venv/bin/python scripts/rust_rcon_probe.py direct \\
        --host 127.0.0.1 --port 28016 --password secret --command status
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ORM_SYNC_INITIALIZED = False
_ORM_LIFESPAN_ACTIVE = False
_CONFIG_LOADED = False


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
    # 与 bot.py 一致：Alembic upgrade，勿用 sync 模式（可能清空 alembic_version / 删表重建）。
    nonebot.init(
        sqlalchemy_database_url=url,
        alembic_startup_check=True,
        alembic_version_locations=migrations,
    )
    nonebot.load_plugin("nonebot_plugin_orm")
    import shared.db.models  # noqa: F401

    _ORM_SYNC_INITIALIZED = True


async def _start_orm_lifespan() -> None:
    """Run NoneBot driver startup hooks (ORM Alembic check runs in init_orm)."""
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


def _print_bindings(snap) -> None:
    bindings = snap.rust_rcon_bindings
    if not bindings:
        print("No RCON bindings configured.")
        return
    for binding in bindings:
        status = "enabled" if binding.enabled else "disabled"
        label = binding.name or binding.alias
        qq = ", ".join(binding.allowed_qq_ids) or "(none)"
        print(
            f"[{binding.id}] {label} alias={binding.alias!r} {status} "
            f"{binding.host}:{binding.port} qq={qq}"
        )


def _find_binding(snap, binding_id: int):
    for binding in snap.rust_rcon_bindings:
        if binding.id == binding_id:
            return binding
    return None


def _policy_ok(snap, *, group_id: str | None, user_id: str, private: bool) -> bool:
    from shared.config.rust_rcon_policy import is_rust_rcon_enabled
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
        if not is_rust_rcon_enabled(snap, user_id=user_id, is_private=True):
            print(f"[BLOCK] RCON policy: user={user_id} (bot would silently ignore)")
            return False
        print(f"[OK] RCON policy: user={user_id}")
        return True

    gid = group_id or ""
    if not is_group_message_enabled_from_snapshot(gid, snap):
        print(
            f"[BLOCK] group message policy: group={gid} "
            "(bot would ignore at group_guard)"
        )
        return False
    print(f"[OK] group message policy: group={gid}")
    if not is_rust_rcon_enabled(snap, group_id=gid):
        print(f"[BLOCK] RCON policy: group={gid} (bot would silently ignore)")
        return False
    print(f"[OK] RCON policy: group={gid}")
    return True


def _is_giveto_command(command: str) -> bool:
    token = command.strip().split(maxsplit=1)[0].lower() if command.strip() else ""
    return token == "giveto"


def _finish_rcon_success(command: str, response: str) -> int:
    """Return probe exit code after a successful RCON round-trip."""
    if not _is_giveto_command(command):
        return 0
    from utils.rust_rcon.give import parse_give_rejection

    rejection = parse_give_rejection(response)
    if rejection is not None:
        print(f"[GIVE REJECTED] {rejection}")
        return 1
    return 0


async def _run_plugin_chain(args: argparse.Namespace) -> int:
    snap = await _load_snapshot()

    from shared.config.rust_rcon import (
        is_qq_allowed_for_binding,
        match_rust_rcon_binding,
    )
    from utils.rust_rcon.client import RconAuthError, RconError, execute_rcon_command

    group_id = str(args.group_id).strip() if args.group_id else None
    user_id = str(args.user_id).strip()

    if not _policy_ok(
        snap, group_id=group_id, user_id=user_id, private=bool(args.private)
    ):
        return 1

    binding = None
    command = (args.command or "").strip()
    if args.binding_id is not None:
        binding = _find_binding(snap, int(args.binding_id))
        if binding is None:
            print(f"[BLOCK] binding id={args.binding_id} not found")
            return 1
        if not binding.enabled:
            print(f"[BLOCK] binding id={binding.id} is disabled")
            return 1
        print(f"[OK] binding: id={binding.id} alias={binding.alias!r}")
    else:
        text = (args.text or "").strip()
        if not text:
            print("[BLOCK] provide --text or --binding-id")
            return 2
        matched = match_rust_rcon_binding(text, snap.rust_rcon_bindings)
        if matched is None:
            print(f"[BLOCK] no binding matched text={text!r}")
            return 1
        binding, command = matched
        print(
            f"[OK] alias match: id={binding.id} alias={binding.alias!r} "
            f"command={command!r}"
        )

    if not is_qq_allowed_for_binding(binding, user_id):
        print(f"[BLOCK] user_id={user_id} not in binding whitelist")
        return 1
    print(f"[OK] QQ whitelist: user_id={user_id}")

    if not command:
        print("[BLOCK] empty RCON command (nothing after alias)")
        return 1

    print(f"[SEND] {binding.host}:{binding.port} → {command!r}")
    try:
        result = await execute_rcon_command(
            binding.host,
            binding.port,
            binding.password,
            command,
            truncate_response=not args.full_response,
        )
    except RconAuthError as exc:
        print(f"[FAIL] RconAuthError: {exc}")
        return 1
    except RconError as exc:
        print(f"[FAIL] RconError: {exc}")
        return 1
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1

    label = binding.name or binding.alias
    print(f"[RESPONSE] [{label}]")
    print(result)
    return _finish_rcon_success(command, result)


async def _run_direct(args: argparse.Namespace) -> int:
    from utils.rust_rcon.client import RconAuthError, RconError, execute_rcon_command

    command = args.command.strip()
    if not command:
        print("[BLOCK] --command is required")
        return 2

    print(
        f"[SEND] direct {args.host}:{args.port} → {command!r} "
        "(skips DB / policy / whitelist)"
    )
    try:
        result = await execute_rcon_command(
            args.host,
            int(args.port),
            args.password,
            command,
            timeout=args.timeout,
            truncate_response=not args.full_response,
        )
    except RconAuthError as exc:
        print(f"[FAIL] RconAuthError: {exc}")
        return 1
    except RconError as exc:
        print(f"[FAIL] RconError: {exc}")
        return 1

    print("[RESPONSE]")
    print(result)
    return _finish_rcon_success(command, result)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List RCON bindings from database")

    run = sub.add_parser("run", help="Simulate rust_rcon plugin chain")
    run.add_argument(
        "--text",
        help='Message body after @bot, e.g. "rcon1 status" (alias match mode)',
    )
    run.add_argument(
        "--binding-id",
        type=int,
        help="Use this binding and --command (skip alias parsing)",
    )
    run.add_argument("--command", help="RCON command to send")
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
        "--full-response",
        action="store_true",
        help="Do not truncate RCON response (useful for give errors)",
    )

    direct = sub.add_parser("direct", help="Send RCON directly (no plugin gates)")
    direct.add_argument("--host", required=True)
    direct.add_argument("--port", type=int, default=28016)
    direct.add_argument("--password", required=True)
    direct.add_argument("--command", required=True)
    direct.add_argument("--timeout", type=float, default=10.0)
    direct.add_argument("--full-response", action="store_true")

    return parser


def _validate_run_args(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    if not args.private and not args.group_id:
        parser.error("run requires --group-id unless --private is set")
    if args.binding_id is None and not args.text:
        parser.error("run requires --text or --binding-id")
    if args.binding_id is not None and not args.command:
        parser.error("run with --binding-id requires --command")


async def _async_main(args: argparse.Namespace) -> int:
    needs_orm = args.cmd in {"list", "run"}
    if needs_orm:
        await _start_orm_lifespan()
    try:
        if args.cmd == "list":
            snap = await _load_snapshot()
            _print_bindings(snap)
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
    if args.cmd in {"list", "run"}:
        _init_orm_sync()

    raise SystemExit(asyncio.run(_async_main(args)))


if __name__ == "__main__":
    main()
