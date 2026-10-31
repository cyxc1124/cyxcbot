"""Validate new input overlaps between built-in and RCON command grammars."""

from shared.config.command_aliases import (
    CommandAliasEntry,
    command_prefixes,
    match_command_arg,
    match_plain,
    parse_extract_dynamic_id,
)
from shared.config.rust_player import parse_shop_list_page, parse_shop_redeem_args
from shared.config.rust_rcon import match_rust_rcon_binding
from shared.config.rust_rcon_custom import match_rust_rcon_custom_command
from shared.group_special_title import parse_title_command


def _matches_builtin(text, cid, config, prefixes, *, group: bool) -> bool:
    if cid == "dynamic_extract":
        return parse_extract_dynamic_id(text, config, prefixes=prefixes) is not None
    if cid == "group_special_title":
        return parse_title_command(text, config, prefixes=prefixes) is not None
    if cid in ("live_status", "rust_player_bind"):
        return match_command_arg(text, cid, config, prefixes=prefixes) is not None
    if cid == "rust_player_shop_list":
        return parse_shop_list_page(text, config, prefixes=prefixes) is not None
    if cid == "rust_player_shop_redeem":
        return parse_shop_redeem_args(text, config, prefixes=prefixes) is not None
    return match_plain(text, cid, config, is_tome=group, prefixes=prefixes)


def new_rcon_command_conflict(
    config, snapshot, extra_prefixes, *, bindings=None, custom_commands=None
) -> str | None:
    """Reject inputs newly shared by actual command grammars in each chat scope."""
    old_prefixes = command_prefixes(snapshot.command_extra_prefixes)
    new_prefixes = command_prefixes(extra_prefixes)
    proposed_bindings = snapshot.rust_rcon_bindings if bindings is None else bindings
    proposed_custom = (
        snapshot.rust_rcon_custom_commands
        if custom_commands is None
        else custom_commands
    )
    enabled_bindings = [record for record in proposed_bindings if record.enabled]
    binding_ids = {record.id for record in enabled_bindings}
    old_binding_ids = {
        record.id for record in snapshot.rust_rcon_bindings if record.enabled
    }
    old_bindings = {record.id: record for record in snapshot.rust_rcon_bindings}
    old_custom = {record.id: record for record in snapshot.rust_rcon_custom_commands}
    for group in (False, True):
        records = [(record, record.alias, False) for record in enabled_bindings]
        if group:
            records.extend(
                (record, record.name, True)
                for record in proposed_custom
                if record.enabled and record.binding_id in binding_ids
            )
        command_ids = config if group else ("status", "dynamic_extract")
        for record, name, custom in records:
            old_record = (old_custom if custom else old_bindings).get(record.id)
            for cid in command_ids:
                entry = config.get(cid)
                if entry is None or not entry.enabled:
                    continue
                old_entry = snapshot.command_aliases.get(
                    cid, CommandAliasEntry(enabled=False)
                )
                configurations = ({cid: old_entry}, {cid: entry})
                for trigger in entry.triggers:
                    bases = {trigger, name, f"{name} {trigger}"}
                    if cid == "dynamic_extract":
                        bases.update(
                            {
                                trigger + "1234567890",
                                trigger + "https://t.bilibili.com/123",
                                trigger + "https://www.bilibili.com/opus/123",
                            }
                        )
                    elif cid == "rust_player_shop_list":
                        bases.add(trigger + "1")
                    elif cid in (
                        "group_special_title",
                        "live_status",
                        "rust_player_bind",
                        "rust_player_shop_redeem",
                    ):
                        bases.add(trigger + " status")
                    inputs = bases | {
                        prefix + text
                        for prefix in old_prefixes | new_prefixes
                        for text in bases
                    }
                    for text in inputs:
                        collisions = [
                            _matches_builtin(text, cid, aliases, prefixes, group=group)
                            and (
                                match_rust_rcon_custom_command(
                                    text,
                                    [candidate] if candidate is not None else [],
                                    enabled_binding_ids=eligible_binding_ids,
                                    prefixes=prefixes,
                                )
                                if custom
                                else match_rust_rcon_binding(
                                    text,
                                    [candidate] if candidate is not None else [],
                                    prefixes=prefixes,
                                )
                            )
                            is not None
                            for prefixes, aliases, candidate, eligible_binding_ids in zip(
                                (old_prefixes, new_prefixes),
                                configurations,
                                (old_record, record),
                                (old_binding_ids, binding_ids),
                            )
                        ]
                        if collisions == [False, True]:
                            kind = "自定义指令" if custom else "绑定"
                            return f"命令设置变更使触发词「{trigger}」与RCON {kind}「{name}」冲突"
    return None
