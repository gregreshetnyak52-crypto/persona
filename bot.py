import logging
import asyncio
import os
import sys
import time
import traceback
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from config import TELEGRAM_BOT_TOKEN, YCLIENTS_MOCK, ADMIN_TELEGRAM_IDS, PROXY_URL, PROXY_FALLBACKS, BUSINESS_PHONE_LINK, BUSINESS_ADDRESS
from services.database import init_db, get_unreminded_bookings, mark_reminded
from services import yclients as _yclients_module
from handlers.start import start, help_command, main_menu_callback, ping_command
from handlers.booking import build_booking_handler
from handlers.admin import build_admin_handler
from handlers.my_bookings import build_my_bookings_handler


logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# Дедупликация алертов: тип ошибки → время последней отправки
_last_alert: dict[str, float] = {}


async def error_handler(update: object, context) -> None:
    log.error("Необработанное исключение: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Что-то пошло не так. Попробуйте начать заново — /start"
            )
        except Exception:
            pass

    # Алерт администраторам (только в prod, не более 1 раза в 5 мин на тип ошибки)
    if not YCLIENTS_MOCK and ADMIN_TELEGRAM_IDS:
        err_key = type(context.error).__name__
        now = time.time()
        if now - _last_alert.get(err_key, 0) > 300:
            _last_alert[err_key] = now
            alert_text = (
                f"⚠️ *Ошибка бота*\n"
                f"`{err_key}`\n"
                f"{datetime.now():%H:%M:%S %d.%m.%Y}"
            )
            for admin_id in ADMIN_TELEGRAM_IDS:
                try:
                    await context.bot.send_message(admin_id, alert_text, parse_mode="Markdown")
                except Exception:
                    pass


def _update_proxy_in_env(new_proxy: str) -> None:
    """Обновляет PROXY_URL в файле .env рядом с bot.py."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r") as f:
        lines = f.readlines()
    new_lines, found = [], False
    for line in lines:
        if line.startswith("PROXY_URL="):
            new_lines.append(f"PROXY_URL={new_proxy}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"PROXY_URL={new_proxy}\n")
    with open(env_path, "w") as f:
        f.writelines(new_lines)
    log.info("PROXY_URL обновлён в .env → %s", new_proxy.split("@")[-1])


async def proxy_watchdog(context) -> None:
    """Каждые 5 мин проверяет прокси через реальное соединение бота (get_me).
    При сбое ищет рабочий из PROXY_FALLBACKS и перезапускает процесс."""
    if not PROXY_URL:
        return  # прокси не настроен — нечего проверять

    # Проверяем через бота — если get_me() проходит, соединение живое
    try:
        await context.bot.get_me()
        return  # всё хорошо
    except Exception as e:
        log.warning("Watchdog: бот не может подключиться к Telegram (%s), ищу замену...", e)

    # Соединение упало — тестируем резервные прокси через curl (subprocess)
    import asyncio
    for fallback in PROXY_FALLBACKS:
        host_port = fallback.replace("socks5://", "")
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-sL", "--max-time", "6",
                "--proxy", f"socks5h://{host_port}",
                "https://api.telegram.org/",
                "-o", "/dev/null", "-w", "%{http_code}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            code = stdout.decode().strip()
            if code in ("200", "404"):
                log.info("Watchdog: нашёл рабочий прокси %s, перезапускаю бота...", host_port)
                _update_proxy_in_env(fallback)
                for admin_id in ADMIN_TELEGRAM_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"⚠️ Прокси сменён на `{host_port}`\nБот перезапускается...",
                            parse_mode="Markdown",
                        )
                    except Exception:
                        pass
                os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception:
            continue

    # Ни один прокси не работает
    log.critical("Watchdog: все прокси недоступны!")
    for admin_id in ADMIN_TELEGRAM_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                "🚨 *Все прокси недоступны!*\nБот не может подключиться к Telegram API.\n"
                "Нужно вручную обновить PROXY\\_URL в .env и перезапустить сервис.",
                parse_mode="Markdown",
            )
        except Exception:
            pass


async def reminder_job(context) -> None:
    bookings = await get_unreminded_bookings()
    for b in bookings:
        try:
            dt = b["appointment_datetime"]
            date_str = dt[:10] if dt else "?"
            time_str = dt[11:16] if len(dt) >= 16 else "?"
            text = (
                f"⏰ Напоминаем о вашей записи!\n\n"
                f"📅 Завтра, {date_str} в {time_str}\n"
                f"✂️ Мастер: {b['master_name']}\n"
                f"💅 Услуга: {b['service_name']}\n\n"
                f"📍 {BUSINESS_ADDRESS}\n"
                f"Если нужно перенести — позвоните: {BUSINESS_PHONE_LINK}"
            )
            await context.bot.send_message(b["user_id"], text, parse_mode="Markdown")
            await mark_reminded(b["id"])
            log.info("Напоминание отправлено для booking_id=%s", b["id"])
        except Exception as e:
            log.warning("Ошибка отправки напоминания booking_id=%s: %s", b["id"], e)


async def post_init(app) -> None:
    """Регистрируем команды бота — появляются в меню "/" у клиента."""
    from telegram import BotCommand
    await app.bot.set_my_commands([
        BotCommand("start",      "🏠 Главное меню"),
        BotCommand("mybookings", "📋 Мои записи"),
        BotCommand("help",       "❓ Справка и контакты"),
        BotCommand("cancel",     "✖️ Отменить действие"),
    ])
    log.info("Bot commands registered.")


async def post_shutdown(app) -> None:
    """Закрыть HTTP-сессию при остановке бота."""
    await _yclients_module.close_session()
    log.info("YClients HTTP session closed.")


def main() -> None:
    asyncio.run(init_db())

    builder = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN)
    if PROXY_URL:
        builder = builder.proxy(PROXY_URL).get_updates_proxy(PROXY_URL)
        log.info("Прокси активирован: %s", PROXY_URL.split("@")[-1])  # скрываем credentials
    app = builder.post_init(post_init).post_shutdown(post_shutdown).build()

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(build_booking_handler())
    app.add_handler(build_admin_handler())
    app.add_handler(build_my_bookings_handler())
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^(info_|back_main|masters_page_|masters_noop)"))

    app.job_queue.run_repeating(reminder_job, interval=3600, first=60)
    # proxy_watchdog отключён — используется собственный стабильный SOCKS5 (microsocks)

    log.info("Bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
