import asyncio
import logging
import random
import time
from datetime import datetime, timezone

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import (
    BOT_HEARTBEAT_INTERVAL_SEC,
    USE_WEBHOOK,
    WEBHOOK_BASE_URL,
    WEBHOOK_SECRET,
    WEBHOOK_PATH_PREFIX,
    WEBHOOK_HOST,
    WEBHOOK_STALE_FILTER_WINDOW_SEC,
    WEBHOOK_STALE_UPDATE_MAX_AGE_SEC,
)
from logging_config import get_logger

logger = get_logger(__name__)


def telegram_delivery_failure_label(exc: Exception) -> str | None:
    text = str(exc or "").lower()
    if isinstance(exc, TelegramForbiddenError) or "bot was blocked" in text or "user is deactivated" in text:
        return "recipient_unavailable"
    if isinstance(exc, TelegramNotFound) or "chat not found" in text or "user not found" in text:
        return "recipient_not_found"
    if isinstance(exc, TelegramBadRequest) and (
        "message to delete not found" in text
        or "message is not modified" in text
        or "can't parse entities" not in text
    ):
        return "bad_request"
    if isinstance(exc, (TelegramNetworkError, TelegramServerError, TelegramRetryAfter)):
        return "telegram_transient"
    return None


def log_telegram_delivery_failure(
    log: logging.Logger,
    message: str,
    *args,
    exc: Exception,
) -> None:
    label = telegram_delivery_failure_label(exc)
    if label:
        log.warning("%s err_type=%s err=%s", message % args if args else message, label, exc)
        return
    log.exception(message, *args)


async def _bot_heartbeat_loop(
    *,
    bot: Bot,
    bot_name: str,
    expected_webhook_url: str | None = None,
    webhook_secret: str | None = None,
    allowed_updates: list[str] | None = None,
) -> None:
    interval = max(10, int(BOT_HEARTBEAT_INTERVAL_SEC))
    while True:
        try:
            await bot.get_me()
            if expected_webhook_url:
                info = await bot.get_webhook_info()
                current_url = str(getattr(info, "url", "") or "")
                if current_url != expected_webhook_url:
                    logger.warning(
                        "%s webhook mismatch detected current=%s expected=%s -> re-registering",
                        bot_name,
                        current_url,
                        expected_webhook_url,
                    )
                    await bot.set_webhook(
                        expected_webhook_url,
                        secret_token=webhook_secret or None,
                        allowed_updates=allowed_updates,
                        drop_pending_updates=False,
                    )
        except Exception as exc:
            logger.warning("%s heartbeat check failed: %s", bot_name, exc)
        await asyncio.sleep(interval)


class ResilientAiohttpSession(AiohttpSession):
    """
    Aiohttp session with bounded retries for transient Telegram transport/server errors.
    """

    def __init__(
        self,
        *,
        timeout: int | float = 45,
        max_retries: int = 2,
        base_delay_sec: float = 0.4,
        max_delay_sec: float = 4.0,
    ):
        super().__init__(timeout=timeout)
        self._max_retries = max(0, int(max_retries))
        self._base_delay_sec = max(0.05, float(base_delay_sec))
        self._max_delay_sec = max(0.2, float(max_delay_sec))

    async def make_request(self, bot: Bot, method, timeout=None):
        attempt = 0
        while True:
            try:
                return await super().make_request(bot, method, timeout=timeout)
            except TelegramRetryAfter as e:
                if attempt >= self._max_retries:
                    raise
                delay = float(getattr(e, "retry_after", 1) or 1)
                delay = max(0.1, delay)
                logger.warning(
                    "Telegram retry-after for %s attempt=%s/%s waiting=%.2fs",
                    getattr(method, "__api_method__", str(method)),
                    attempt + 1,
                    self._max_retries + 1,
                    delay,
                )
                await asyncio.sleep(delay)
            except (TelegramNetworkError, TelegramServerError) as e:
                if attempt >= self._max_retries:
                    raise
                delay = min(self._max_delay_sec, self._base_delay_sec * (2 ** attempt))
                delay += random.uniform(0, 0.15)
                logger.warning(
                    "Telegram transient error for %s attempt=%s/%s err=%s retry_in=%.2fs",
                    getattr(method, "__api_method__", str(method)),
                    attempt + 1,
                    self._max_retries + 1,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)
            attempt += 1


def create_resilient_bot(token: str, *, parse_mode: str = "HTML") -> Bot:
    # Keep aiogram session timeout as numeric seconds to avoid polling arithmetic
    # incompatibilities with aiohttp.ClientTimeout objects on some versions.
    session = ResilientAiohttpSession(timeout=45, max_retries=2, base_delay_sec=0.4, max_delay_sec=4.0)
    return Bot(token=token, default=DefaultBotProperties(parse_mode=parse_mode), session=session)


def spawn_guarded_task(coro, *, name: str):
    task = asyncio.create_task(coro, name=name)

    def _done(t: asyncio.Task):
        try:
            exc = t.exception()
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.exception("Background task inspection failed name=%s err=%s", name, e)
            return
        if exc is not None:
            logger.exception("Background task crashed name=%s err=%s", name, exc)

    task.add_done_callback(_done)
    return task


class StaleUpdateGuardMiddleware:
    """
    During cold start, suppress stale pending updates while allowing fresh traffic through.
    """

    def __init__(self, *, max_age_sec: int, filter_window_sec: int):
        self.max_age_sec = max(1, int(max_age_sec))
        self.filter_window_sec = max(1, int(filter_window_sec))
        self.started_at_monotonic = time.monotonic()

    def _within_filter_window(self) -> bool:
        return (time.monotonic() - self.started_at_monotonic) <= self.filter_window_sec

    @staticmethod
    def _extract_update_datetime(update: Update) -> datetime | None:
        if update.message:
            return update.message.date
        if update.edited_message:
            return update.edited_message.date
        if update.channel_post:
            return update.channel_post.date
        if update.edited_channel_post:
            return update.edited_channel_post.date
        if update.callback_query and update.callback_query.message:
            return update.callback_query.message.date
        if update.poll_answer:
            return datetime.now(timezone.utc)
        return None

    @staticmethod
    async def _answer_stale_callback(update: Update, bot: Bot | None):
        try:
            cq = update.callback_query
            if not cq or bot is None:
                return
            await bot.answer_callback_query(
                callback_query_id=cq.id,
                text="Request expired, please retry.",
                show_alert=False,
            )
        except Exception:
            pass

    async def __call__(self, handler, event, data):
        if not isinstance(event, Update) or not self._within_filter_window():
            return await handler(event, data)

        event_dt = self._extract_update_datetime(event)
        if event_dt is None:
            return await handler(event, data)
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)

        age_sec = max(0.0, (datetime.now(timezone.utc) - event_dt).total_seconds())
        if age_sec <= self.max_age_sec:
            return await handler(event, data)

        await self._answer_stale_callback(event, data.get("bot"))
        logger.info(
            "Dropped stale update during startup window age=%.1fs max=%ss update_id=%s",
            age_sec,
            self.max_age_sec,
            getattr(event, "update_id", None),
        )
        return None


def _install_stale_update_guard(dp: Dispatcher):
    if getattr(dp, "_stale_guard_installed", False):
        return
    mw = StaleUpdateGuardMiddleware(
        max_age_sec=WEBHOOK_STALE_UPDATE_MAX_AGE_SEC,
        filter_window_sec=WEBHOOK_STALE_FILTER_WINDOW_SEC,
    )
    dp.update.outer_middleware(mw)
    setattr(dp, "_stale_guard_installed", True)


async def run_bot_dispatcher(
    *,
    dp: Dispatcher,
    bot: Bot,
    bot_name: str,
    webhook_port: int,
) -> None:
    _install_stale_update_guard(dp)
    allowed_updates = dp.resolve_used_update_types()
    heartbeat_task = None
    async def _run_polling(reason: str) -> None:
        nonlocal heartbeat_task
        logger.info("%s starting in polling mode reason=%s", bot_name, reason)
        heartbeat_task = spawn_guarded_task(
            _bot_heartbeat_loop(bot=bot, bot_name=bot_name),
            name=f"{bot_name}_heartbeat",
        )
        # If webhook was previously enabled for this token, polling will fail
        # with TelegramConflictError until webhook is removed.
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            logger.exception("%s delete_webhook before polling failed", bot_name)
        # aiogram 3.13 can expose aiohttp.ClientTimeout on session.timeout.
        # start_polling internally adds an int to timeout, so normalize to seconds.
        try:
            timeout_obj = getattr(bot.session, "timeout", None)
            if timeout_obj is not None and not isinstance(timeout_obj, (int, float)):
                total = getattr(timeout_obj, "total", None)
                if total is None:
                    total = 30
                bot.session.timeout = int(total)
        except Exception:
            pass
        try:
            await dp.start_polling(bot, allowed_updates=allowed_updates)
            return
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()

    if not USE_WEBHOOK:
        await _run_polling("configured")
        return

    if not WEBHOOK_BASE_URL:
        raise RuntimeError("USE_WEBHOOK=true but WEBHOOK_BASE_URL is empty")

    path = f"/{WEBHOOK_PATH_PREFIX.strip('/')}/{bot_name}"
    webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}{path}"
    secret = WEBHOOK_SECRET or None

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret).register(app, path=path)
    setup_application(app, dp, bot=bot)

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"ok": True, "bot": bot_name, "mode": "webhook"})

    app.router.add_get("/healthz", health)
    app.router.add_get(f"{path}/healthz", health)

    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, WEBHOOK_HOST, webhook_port)
        await site.start()
        logger.info("%s webhook server listening on %s:%s", bot_name, WEBHOOK_HOST, webhook_port)

        await bot.set_webhook(
            webhook_url,
            secret_token=secret,
            allowed_updates=allowed_updates,
            drop_pending_updates=False,
        )
        logger.info("%s webhook registered url=%s", bot_name, webhook_url)
        heartbeat_task = spawn_guarded_task(
            _bot_heartbeat_loop(
                bot=bot,
                bot_name=bot_name,
                expected_webhook_url=webhook_url,
                webhook_secret=secret,
                allowed_updates=allowed_updates,
            ),
            name=f"{bot_name}_heartbeat",
        )
        await asyncio.Event().wait()
    except Exception:
        logger.exception("%s webhook startup failed url=%s", bot_name, webhook_url)
        try:
            await runner.cleanup()
        except Exception:
            logger.exception("%s webhook runner cleanup before polling fallback failed", bot_name)
        await _run_polling("webhook_startup_failed")
        return
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
        # Release bound webhook port on any startup failure or shutdown path.
        try:
            await runner.cleanup()
        except Exception:
            logger.exception("%s webhook runner cleanup failed", bot_name)
