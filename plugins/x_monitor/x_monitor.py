"""
X (Twitter) 监控核心模块
负责轮询博主新推文并推送到 QQ 群/好友
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set

import aiohttp
from nonebot.log import logger
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from shared.config.service import get_config_service
from shared.db.models import XTarget
from shared.monitor.background_task import spawn_background_task
from shared.monitor.check_cycle import CheckCycleLogger
from shared.monitor.concurrency import run_with_concurrency
from shared.monitor.poll_schedule import compute_dynamic_poll_schedule
from utils.x_api import TweetItem, XApiClient, XUser, create_session
from utils.x_api.models import tweet_id_as_int

from .check_logic import (
    collect_new_tweets,
    compute_first_baseline_last_id,
    should_fill_display_name,
    should_initialize_after_first_poll,
)
from .config import Config
from .delivery_retry import failed_target_ids
from .poll_scheduler import register_poll_job, remove_poll_job
from .sender import XSender
from .state_store import XMonitorStateStore

x_monitor_instance: Optional["XMonitor"] = None
_config_reload_registered = False
_lifecycle_lock = asyncio.Lock()


async def sync_from_config_reload(snapshot) -> None:
    """Start, stop, or hot-reload X monitor to match config snapshot."""
    has_targets = bool(snapshot.x_monitor_mapping)

    if x_monitor_instance is None:
        if has_targets:
            await start_x_monitor()
        return

    if not has_targets:
        await x_monitor_instance.reload_config()
        await stop_x_monitor()
        return

    await x_monitor_instance.reload_config()


async def _on_config_reload(snapshot):
    await sync_from_config_reload(snapshot)


def _ensure_config_reload_registered() -> None:
    global _config_reload_registered
    if not _config_reload_registered:
        get_config_service().register_reload_callback(_on_config_reload)
        _config_reload_registered = True


class XMonitor:
    """X 博主推文监控核心类。"""

    def __init__(self, config: Config):
        self.config = config
        self.last_tweet_ids: Dict[str, str] = {}
        self.initialized_usernames: Dict[str, bool] = {}
        self._user_ids: Dict[str, str] = {}
        self._check_generation: Dict[str, int] = {}
        self.is_running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.client: Optional[XApiClient] = None
        self.sender: Optional[XSender] = None
        self._stagger_index = 0
        self._cycle_logger = CheckCycleLogger("X 监控")
        self.last_check_at: Optional[str] = None
        self.checks_total = 0
        self.new_tweets_total = 0
        self._delivery_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._delivery_tasks: Set[asyncio.Task] = set()
        # username -> (tweet_id, failed_groups, failed_users)；部分失败时只重试失败目标
        self._pending_tweet_delivery: Dict[str, tuple[str, List[str], List[str]]] = {}
        self._state_store = XMonitorStateStore()

    def _touch_last_check_at(self) -> None:
        self.last_check_at = datetime.now().isoformat(timespec="seconds")

    def _username_list(self) -> List[str]:
        return list(self.config.x_monitor_mapping.keys())

    def _is_active_username(self, username: str) -> bool:
        return username in self.config.x_monitor_mapping

    def _bump_check_generation(self, username: str) -> None:
        self._check_generation[username] = self._check_generation.get(username, 0) + 1

    def _check_still_valid(self, username: str, check_generation: int) -> bool:
        return self._is_active_username(username) and (
            self._check_generation.get(username, 0) == check_generation
        )

    def _remove_username(self, username: str) -> None:
        self._bump_check_generation(username)
        self.last_tweet_ids.pop(username, None)
        self.initialized_usernames.pop(username, None)
        self._user_ids.pop(username, None)
        self._delivery_locks.pop(username, None)
        self._pending_tweet_delivery.pop(username, None)

    def _spawn_delivery_task(self, coro, *, name: str = "X 投递") -> None:
        spawn_background_task(name, coro, tasks=self._delivery_tasks)

    async def _drain_pending_deliveries(self) -> None:
        while self._delivery_tasks:
            tasks = list(self._delivery_tasks)
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _delete_persisted_state(self, username: str) -> None:
        await self._state_store.delete(username)

    def _schedule_poll_job(self) -> None:
        usernames = self._username_list()
        if not usernames:
            return

        schedule = compute_dynamic_poll_schedule(
            len(usernames),
            self.config.monitor_interval,
            use_stagger=self.config.use_stagger_poll,
        )
        register_poll_job(
            use_stagger_poll=self.config.use_stagger_poll,
            username_count=len(usernames),
            monitor_interval=self.config.monitor_interval,
            stagger_callback=self._check_next_user,
            batch_callback=self._check_all_users,
            schedule=schedule,
        )

    async def _rebuild_session(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = create_session(self.config.x_proxy)
        self.client = XApiClient(self.session, self.config.x_api_bearer)

    async def init_resources(self):
        await self._rebuild_session()
        self.sender = XSender(templates=self.config.message_templates)
        self._user_ids.update(
            {
                username: uid
                for username, uid in self.config.x_user_ids.items()
                if username and uid
            }
        )

        if not self.config.x_api_bearer:
            logger.warning("X 监控: 未配置 Bearer Token，无法拉取推文")

        proxy = self.config.x_proxy
        if proxy.enabled and not proxy.is_configured:
            logger.warning("X 监控: 代理已启用但未正确配置 host/port")
        elif proxy.is_configured:
            logger.info(
                "X 监控: 已启用 {} 代理 {}:{}",
                proxy.scheme,
                proxy.host,
                proxy.port,
            )

        await self._load_persisted_states()

    async def _load_persisted_states(self):
        usernames = list(self.config.x_monitor_mapping.keys())
        await self._state_store.load(
            usernames=usernames,
            last_tweet_ids=self.last_tweet_ids,
            initialized_usernames=self.initialized_usernames,
            pending_tweet_delivery=self._pending_tweet_delivery,
        )

    async def _persist_state(
        self, username: str, *, check_generation: Optional[int] = None
    ):
        if not self._is_active_username(username):
            return
        if check_generation is not None and not self._check_still_valid(
            username, check_generation
        ):
            return
        await self._state_store.persist(
            username,
            last_tweet_ids=self.last_tweet_ids,
            initialized_usernames=self.initialized_usernames,
            pending_tweet_delivery=self._pending_tweet_delivery,
        )

    async def reload_config(self):
        old_interval = self.config.monitor_interval
        old_use_stagger = self.config.use_stagger_poll
        old_bearer = self.config.x_api_bearer
        old_proxy = self.config.x_proxy
        old_usernames = set(self.config.x_monitor_mapping.keys())
        self.config = Config.from_service()
        new_usernames_set = set(self.config.x_monitor_mapping.keys())

        removed = old_usernames - new_usernames_set
        for username in removed:
            self._remove_username(username)
            await self._delete_persisted_state(username)
        if removed:
            logger.info(
                "X 监控已移除 {} 个不再配置的博主: {}",
                len(removed),
                ", ".join(sorted(removed)),
            )

        readded = new_usernames_set - old_usernames
        for username in readded:
            self._bump_check_generation(username)
            self.last_tweet_ids[username] = "0"
            self.initialized_usernames[username] = False
            self._user_ids.pop(username, None)
            await self._delete_persisted_state(username)
        if readded:
            logger.info(
                "X 监控已重新启用 {} 个博主，已重置监控状态: {}",
                len(readded),
                ", ".join(sorted(readded)),
            )

        session_changed = (
            old_bearer != self.config.x_api_bearer or old_proxy != self.config.x_proxy
        )
        if session_changed:
            await self._rebuild_session()
            self._user_ids.clear()

        # 同步 DB 缓存的 user_id（热重载后优先用库内资料，避免重复 User: Read）
        for username, uid in self.config.x_user_ids.items():
            if username and uid:
                self._user_ids[username] = uid
        for username in list(self._user_ids):
            if username not in self.config.x_monitor_mapping:
                self._user_ids.pop(username, None)

        new_usernames: list[str] = list(readded)
        for username in self.config.x_monitor_mapping.keys():
            if username not in self.last_tweet_ids:
                self.last_tweet_ids[username] = "0"
                self.initialized_usernames[username] = False
                if username not in new_usernames:
                    new_usernames.append(username)

        if self.is_running:
            for username in new_usernames:
                try:
                    await self._check_user_tweets(username)
                except Exception:
                    logger.opt(exception=True).error(
                        "初始化 X 博主 {} 监控失败", username
                    )

        if self.is_running and (
            old_interval != self.config.monitor_interval
            or old_use_stagger != self.config.use_stagger_poll
            or old_usernames != new_usernames_set
        ):
            if (
                old_usernames != new_usernames_set
                or old_use_stagger != self.config.use_stagger_poll
            ):
                self._stagger_index = 0
                self._cycle_logger.reset()
            self._schedule_poll_job()

        if self.sender:
            self.sender.templates = self.config.message_templates

        logger.info(
            "X 监控配置已热重载: {} 个博主, 间隔 {}秒, 模式={}",
            len(self.config.x_monitor_mapping),
            self.config.monitor_interval,
            "分散检查" if self.config.use_stagger_poll else "批量检查",
        )

    async def start_monitoring(self):
        self.is_running = True
        await self.init_resources()
        logger.info(
            "X 监控已启动，{}模式，目标周期: {}秒",
            "分散检查" if self.config.use_stagger_poll else "批量检查",
            self.config.monitor_interval,
        )
        self._schedule_poll_job()
        logger.info("X 监控定时任务已添加到调度器")

    async def _cleanup_resources(self):
        try:
            if self.session and not self.session.closed:
                await self.session.close()
        except Exception:
            logger.opt(exception=True).warning("清理 X 监控资源时出错")
        self.session = None
        self.client = None

    async def stop_monitoring(self):
        logger.info("正在停止 X 监控...")
        self.is_running = False
        remove_poll_job()
        await self._drain_pending_deliveries()
        await self._cleanup_resources()
        logger.info("X 监控已完全停止")

    async def _check_next_user(self):
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return

        usernames = self._username_list()
        if not usernames:
            return

        if self._stagger_index >= len(usernames):
            self._stagger_index = 0

        username = usernames[self._stagger_index]
        self._stagger_index = (self._stagger_index + 1) % len(usernames)
        cycle_completed = self._stagger_index == 0

        try:
            ok = await self._check_user_tweets(username)
            if ok is False:
                self._cycle_logger.record_failure(username)
            else:
                self._cycle_logger.record_success()
                self._touch_last_check_at()
        except Exception as e:
            self._cycle_logger.record_error(username, e)

        if cycle_completed:
            self._cycle_logger.emit_summary()
            self._touch_last_check_at()

    async def _check_all_users(self):
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return

        usernames = self._username_list()
        if not usernames:
            return

        try:
            results = await run_with_concurrency(usernames, self._check_user_tweets)
            for username, ok in zip(usernames, results):
                if isinstance(ok, BaseException):
                    self._cycle_logger.record_error(username, ok)
                elif ok is False:
                    self._cycle_logger.record_failure(username)
                else:
                    self._cycle_logger.record_success()

            self._cycle_logger.emit_summary()
            self._touch_last_check_at()
        except Exception:
            logger.opt(exception=True).error("X 监控检查出错")

    async def run_manual_check(
        self, usernames: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """检查指定或全部 X 博主的推文（手动触发时使用）。"""
        if not self.is_running:
            logger.debug("监控已停止，跳过本次检查")
            return {"checked": [], "failed": []}

        username_list = usernames if usernames is not None else self._username_list()
        cycle = CheckCycleLogger("X 监控（手动）")
        checked: List[str] = []
        failed: List[str] = []

        try:
            results = await run_with_concurrency(username_list, self._check_user_tweets)
            for username, ok in zip(username_list, results):
                if isinstance(ok, BaseException):
                    cycle.record_error(username, ok)
                    failed.append(username)
                elif ok is False:
                    cycle.record_failure(username)
                    failed.append(username)
                else:
                    cycle.record_success()
                    checked.append(username)

            cycle.emit_summary(log_success_at_info=True)
            self._touch_last_check_at()
        except Exception:
            logger.opt(exception=True).error("X 监控检查出错")

        return {"checked": checked, "failed": failed}

    async def _persist_user_profile(self, username: str, user: XUser) -> None:
        """Write resolved X user id / display name back to XTarget."""
        key = (username or "").strip().lstrip("@").strip().lower()
        if not key or not user.id:
            return
        display = (user.name or user.username or key).strip() or key
        self._user_ids[key] = user.id
        self.config.x_user_ids[key] = user.id
        kept_name = display
        try:
            async with get_session() as session:
                async with session.begin():
                    row = await session.scalar(
                        select(XTarget).where(XTarget.username == key)
                    )
                    if row is None:
                        return
                    row.user_id = user.id
                    current_name = (row.name or "").strip()
                    if should_fill_display_name(current_name) and display:
                        row.name = display
                        current_name = display
                    kept_name = current_name or display
        except Exception:
            logger.opt(exception=True).warning(
                "持久化 X 用户资料失败: username={}", key
            )
            return
        self.config.x_display_names[key] = kept_name

    async def _resolve_user(
        self, username: str, *, force_refresh: bool = False
    ) -> Optional[XUser]:
        if not self.client:
            return None
        key = (username or "").strip().lstrip("@").strip().lower()
        if not key:
            return None

        if not force_refresh:
            cached_id = self._user_ids.get(key) or self.config.x_user_ids.get(key)
            if cached_id:
                name = self.config.x_display_names.get(key) or key
                return XUser(id=cached_id, username=key, name=name)

        user = await self.client.get_user_by_username(key)
        if user:
            await self._persist_user_profile(key, user)
            return user

        cached_id = self._user_ids.get(key) or self.config.x_user_ids.get(key)
        if cached_id:
            name = self.config.x_display_names.get(key) or key
            return XUser(id=cached_id, username=key, name=name)
        return None

    async def _check_user_tweets(self, username: str) -> bool:
        if not self._is_active_username(username):
            return True

        self.checks_total += 1
        check_generation = self._check_generation.get(username, 0)
        logger.debug("检查 X 博主 {} 的推文", username)

        if not self.client:
            return False

        user = await self._resolve_user(username)
        if not user:
            logger.debug("获取 X 博主 {} 用户信息失败", username)
            return False

        if not self._check_still_valid(username, check_generation):
            return True

        last_tweet_id = self.last_tweet_ids.get(username, "0")
        initialized = self.initialized_usernames.get(username, False)
        # 已建基准后用 since_id 只拉增量；零游标也翻页，避免只拿最新 5 条漏帖
        since_id = None
        if initialized and tweet_id_as_int(last_tweet_id):
            since_id = last_tweet_id

        tweets = await self.client.fetch_user_tweets(
            user.id,
            username=username,
            name=user.name or username,
            since_id=since_id,
            paginate=initialized,
        )
        if tweets is None:
            logger.debug("获取 X 博主 {} 推文失败", username)
            return False

        if not self._check_still_valid(username, check_generation):
            return True

        new_tweets = collect_new_tweets(tweets, last_tweet_id)

        if not self.initialized_usernames.get(username, False):
            if not self._check_still_valid(username, check_generation):
                return True
            baseline = compute_first_baseline_last_id(tweets)
            if not should_initialize_after_first_poll(baseline):
                # 无推文时不标记已初始化，避免下一轮零游标翻页把历史帖当新帖群发
                logger.info(
                    "X 博主 {} 首次监控，当前无推文，等待首条后再建基准", username
                )
                return True
            if not self._check_still_valid(username, check_generation):
                return True
            logger.info("X 博主 {} 首次监控，已记录最新推文 ID: {}", username, baseline)
            self.last_tweet_ids[username] = baseline
            self.initialized_usernames[username] = True
            await self._persist_state(username, check_generation=check_generation)
            return True

        if new_tweets:
            if not self._check_still_valid(username, check_generation):
                return True
            ordered = sorted(new_tweets, key=lambda t: tweet_id_as_int(t.id))
            self._spawn_delivery_task(
                self._deliver_new_tweets(username, ordered, check_generation)
            )

        return True

    async def _deliver_new_tweets(
        self,
        username: str,
        tweets: List[TweetItem],
        check_generation: int,
    ) -> None:
        async with self._delivery_locks[username]:
            delivered_ids: List[str] = []
            for tweet in tweets:
                if tweet_id_as_int(tweet.id) <= tweet_id_as_int(
                    self.last_tweet_ids.get(username, "0")
                ):
                    continue
                if not self._check_still_valid(username, check_generation):
                    break
                delivered = await self._send_tweet_notification(
                    username, tweet, check_generation=check_generation
                )
                if not delivered:
                    logger.warning(
                        "X 博主 {} 推文 {} 通知投递失败，保留游标待重试",
                        username,
                        tweet.id,
                    )
                    break
                delivered_ids.append(tweet.id)

            if delivered_ids:
                self.new_tweets_total += len(delivered_ids)

            if delivered_ids and self._check_still_valid(username, check_generation):
                self.last_tweet_ids[username] = str(
                    max(delivered_ids, key=tweet_id_as_int)
                )
                await self._persist_state(username, check_generation=check_generation)

    async def _send_tweet_notification(
        self,
        username: str,
        tweet: TweetItem,
        *,
        check_generation: Optional[int] = None,
    ) -> bool:
        if check_generation is not None and not self._check_still_valid(
            username, check_generation
        ):
            return False

        logger.info("发现新推文: {} (@{})", tweet.name or username, username)
        if not self.sender:
            return False

        message = self.sender.build_tweet_message(tweet)
        configured_groups = self.config.x_monitor_mapping.get(username, [])
        configured_users = self.config.x_monitor_user_mapping.get(username, [])
        pending = self._pending_tweet_delivery.get(username)
        if pending and pending[0] == tweet.id:
            configured_group_set = set(configured_groups)
            configured_user_set = set(configured_users)
            group_ids = [g for g in pending[1] if g in configured_group_set]
            user_ids = [u for u in pending[2] if u in configured_user_set]
            if not group_ids and not user_ids:
                # 失败目标已从配置移除，无需再投递
                self._pending_tweet_delivery.pop(username, None)
                await self._persist_state(username, check_generation=check_generation)
                return True
        else:
            if pending:
                self._pending_tweet_delivery.pop(username, None)
            group_ids = list(configured_groups)
            user_ids = list(configured_users)

        if not group_ids and not user_ids:
            logger.warning("X 博主 {} 没有配置推送目标", username)
            return False

        if check_generation is not None and not self._check_still_valid(
            username, check_generation
        ):
            return False

        at_all_enabled = self.config.x_at_all.get(username, False)
        delivery = await self.sender.send_message(
            message,
            group_ids,
            user_ids,
            at_all_enabled=at_all_enabled,
        )
        if delivery.all_succeeded:
            self._pending_tweet_delivery.pop(username, None)
            logger.info(
                "X 推文通知已推送: username={} tweet_id={} groups={} users={}",
                username,
                tweet.id,
                len(group_ids),
                len(user_ids),
            )
            return True

        failed_groups, failed_users = failed_target_ids(delivery)
        self._pending_tweet_delivery[username] = (
            tweet.id,
            failed_groups,
            failed_users,
        )
        await self._persist_state(username, check_generation=check_generation)
        failed_targets = [
            f"{target.target_type}:{target.target_id}"
            for target in delivery.targets
            if not target.success
        ]
        logger.warning(
            "X 推文通知投递未全部成功: username={} tweet_id={} failed={}",
            username,
            tweet.id,
            failed_targets,
        )
        return False


async def start_x_monitor():
    """启动 X 监控。"""
    global x_monitor_instance

    async with _lifecycle_lock:
        _ensure_config_reload_registered()

        if x_monitor_instance is not None:
            if x_monitor_instance.is_running:
                logger.warning("X 监控已在运行中")
                return
            x_monitor_instance = None

        config = Config.from_service()
        if not config.x_monitor_mapping:
            logger.warning("未配置任何 X 监控目标，跳过启动")
            return

        group_count = sum(len(groups) for groups in config.x_monitor_mapping.values())
        user_count = sum(len(users) for users in config.x_monitor_user_mapping.values())
        logger.info(
            "准备启动 X 监控: {} 个博主, {} 个群推送目标, {} 个好友推送目标, 间隔 {}秒",
            len(config.x_monitor_mapping),
            group_count,
            user_count,
            config.monitor_interval,
        )

        try:
            x_monitor_instance = XMonitor(config)
            await x_monitor_instance.start_monitoring()
            logger.info("X 监控已启动")
        except Exception:
            logger.opt(exception=True).error("启动 X 监控失败")
            x_monitor_instance = None


async def stop_x_monitor():
    """停止 X 监控。"""
    global x_monitor_instance

    async with _lifecycle_lock:
        if not x_monitor_instance:
            return

        logger.info("正在停止 X 监控...")
        try:
            await x_monitor_instance.stop_monitoring()
            x_monitor_instance = None
            logger.info("X 监控已完全停止")
        except Exception:
            logger.opt(exception=True).error("停止 X 监控时出错")
            x_monitor_instance = None
