"""
Административная панель бота.

Доступ: /admin → ввод пароля → меню.
Авторизация хранится в SQLite 24 часа.

Состояния:
  ADMIN_PASSWORD_STATE — ввод пароля
  ADMIN_MENU           — основное меню + все действия
  ADMIN_SEARCH_STATE   — ожидание текста поискового запроса
"""
import logging
import math
from datetime import date, timedelta

from telegram import Update
from telegram.helpers import escape_markdown
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import ADMIN_PASSWORD, BUSINESS_PHONE_LINK
from keyboards.builders import (
    admin_menu_kb, admin_records_kb, admin_record_actions_kb,
    admin_dates_kb, admin_confirm_delete_kb,
    admin_masters_filter_kb, admin_search_results_kb,
)
from services import database as db
from services import yclients
from services.database import (
    get_booking_by_record_id, cancel_booking_by_id, get_stats,
    check_login_attempt, record_failed_login, reset_login_attempts,
    log_admin_action, clear_admin_auth, search_bookings,
)

log = logging.getLogger(__name__)

# ── Состояния ─────────────────────────────────────────────────────────────────
ADMIN_PASSWORD_STATE, ADMIN_MENU, ADMIN_SEARCH_STATE = range(3)

# Количество записей на страницу
PAGE_SIZE = 10


# ── Вход ──────────────────────────────────────────────────────────────────────

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    if await db.is_admin_authed(user_id):
        await update.message.reply_text("Добро пожаловать в панель администратора!", reply_markup=admin_menu_kb())
        return ADMIN_MENU

    allowed, remaining = await check_login_attempt(user_id)
    if not allowed:
        await update.message.reply_text("⛔ Слишком много неверных попыток. Попробуйте через 30 минут.")
        return ConversationHandler.END

    await update.message.reply_text("Введите пароль администратора:")
    return ADMIN_PASSWORD_STATE


async def admin_check_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    pwd = update.message.text.strip()

    if pwd == ADMIN_PASSWORD:
        await reset_login_attempts(user_id)
        await db.set_admin_auth(user_id)
        await log_admin_action(user_id, "login")
        await update.message.reply_text("✅ Авторизован! Панель администратора:", reply_markup=admin_menu_kb())
        return ADMIN_MENU
    else:
        locked, remaining = await record_failed_login(user_id)
        if locked:
            await update.message.reply_text("⛔ Превышен лимит попыток. Вход заблокирован на 30 минут.")
        else:
            await update.message.reply_text(f"❌ Неверный пароль. Осталось попыток: {remaining}.")
        log.warning("Неудачная попытка входа в /admin от user_id=%s", user_id)
        return ConversationHandler.END


# ── Поиск по клиенту ──────────────────────────────────────────────────────────

async def admin_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Принимает текст поискового запроса, ищет в booking_log."""
    if not await db.is_admin_authed(update.effective_user.id):
        await update.message.reply_text("Сессия истекла. Введите /admin снова.")
        return ConversationHandler.END

    query_text = update.message.text.strip()
    if len(query_text) < 2:
        await update.message.reply_text(
            "Введите минимум 2 символа для поиска.\n_(для отмены — /cancel)_",
            parse_mode="Markdown",
        )
        return ADMIN_SEARCH_STATE

    results = await search_bookings(query_text)
    if not results:
        await update.message.reply_text(
            f"По запросу «{query_text}» ничего не найдено.\n\nВведите другой запрос или /cancel для выхода.",
        )
        return ADMIN_SEARCH_STATE

    lines = [f"🔍 *Результаты поиска «{escape_markdown(query_text, version=1)}»* ({len(results)} записей):\n"]
    for b in results:
        dt = b.get("appointment_datetime", "")
        date_str = dt[:10] if dt else "?"
        time_str = dt[11:16] if len(dt) >= 16 else "?"
        lines.append(
            f"• {date_str} {time_str} | {escape_markdown(b.get('master_name','?'), version=1)} | "
            f"{b.get('client_name','?')} | {escape_markdown(b.get('service_name','?'), version=1)}"
        )

    context.user_data["admin_search_results"] = results
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=admin_search_results_kb(results),
    )
    return ADMIN_MENU


# ── Основной обработчик меню ──────────────────────────────────────────────────

async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not await db.is_admin_authed(query.from_user.id):
        await query.edit_message_text("Сессия истекла. Введите /admin снова.")
        return ConversationHandler.END

    data = query.data

    # ── Нечего делать (счётчик страниц) ──────────────────────────────────────
    if data == "adm_noop":
        return ADMIN_MENU

    # ── Выход ─────────────────────────────────────────────────────────────────
    if data == "adm_logout":
        await clear_admin_auth(query.from_user.id)
        await log_admin_action(query.from_user.id, "logout")
        await query.edit_message_text("🚪 Вы вышли из панели администратора.")
        return ConversationHandler.END

    # ── Назад в главное меню ──────────────────────────────────────────────────
    if data == "adm_back":
        await query.edit_message_text("Панель администратора:", reply_markup=admin_menu_kb())
        return ADMIN_MENU

    # ── Назад к списку записей (из карточки записи / фильтра) ─────────────────
    if data == "adm_back_list":
        day = context.user_data.get("admin_date")
        page = context.user_data.get("admin_page", 0)
        if day:
            return await _render_records_page(update, context, page)
        await query.edit_message_text("Панель администратора:", reply_markup=admin_menu_kb())
        return ADMIN_MENU

    # ── Статистика ────────────────────────────────────────────────────────────
    if data == "adm_stats":
        try:
            stats = await get_stats()
        except Exception as e:
            log.error("get_stats error: %s", e)
            await query.edit_message_text("Ошибка загрузки статистики.", reply_markup=admin_menu_kb())
            return ADMIN_MENU
        lines = [
            "📊 *Статистика записей*\n",
            f"Сегодня: *{stats['today']}*",
            f"За 7 дней: *{stats['week']}*",
            f"За 30 дней: *{stats['month']}*",
        ]
        if stats["top_services"]:
            lines.append("\n💼 *Топ услуги (за всё время):*")
            for name, cnt in stats["top_services"]:
                lines.append(f"  {escape_markdown(name, version=1)} — {cnt}")
        if stats["top_masters"]:
            lines.append("\n👩‍🎨 *Топ мастера (за всё время):*")
            for name, cnt in stats["top_masters"]:
                lines.append(f"  {escape_markdown(name, version=1)} — {cnt}")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=admin_menu_kb())
        return ADMIN_MENU

    # ── Выбор даты ────────────────────────────────────────────────────────────
    if data in ("adm_pick_date", "adm_cancel"):
        await query.edit_message_text("Выберите дату:", reply_markup=admin_dates_kb())
        return ADMIN_MENU

    if data.startswith("adm_date_"):
        date_str = data.replace("adm_date_", "")
        # Сбрасываем фильтр и грузим записи заново
        context.user_data["admin_filter_master"] = None
        return await _load_records(update, context, date_str)

    # ── Пагинация ─────────────────────────────────────────────────────────────
    if data.startswith("adm_page_"):
        page = int(data.replace("adm_page_", ""))
        return await _render_records_page(update, context, page)

    # ── Фильтр по мастеру ─────────────────────────────────────────────────────
    if data == "adm_filter_master":
        records = context.user_data.get("admin_records", [])
        masters = sorted({r.get("staff", {}).get("name", "?") for r in records if r.get("staff")})
        active = context.user_data.get("admin_filter_master")
        await query.edit_message_text(
            "Выберите мастера для фильтрации:",
            reply_markup=admin_masters_filter_kb(masters, active),
        )
        return ADMIN_MENU

    if data == "adm_fmaster_all":
        context.user_data["admin_filter_master"] = None
        return await _render_records_page(update, context, 0)

    if data.startswith("adm_fmaster_"):
        master_name = data.replace("adm_fmaster_", "")
        context.user_data["admin_filter_master"] = master_name
        return await _render_records_page(update, context, 0)

    # ── Поиск по клиенту ──────────────────────────────────────────────────────
    if data == "adm_search":
        await query.edit_message_text(
            "🔍 Введите имя клиента или телефон:\n_(для отмены — /cancel)_",
            parse_mode="Markdown",
        )
        return ADMIN_SEARCH_STATE

    # ── Просмотр записи из поиска ─────────────────────────────────────────────
    if data.startswith("adm_srec_"):
        record_id = int(data.replace("adm_srec_", ""))
        context.user_data["admin_viewing_record"] = record_id
        await query.edit_message_text(
            f"Запись #{record_id}\nЧто сделать?",
            reply_markup=admin_record_actions_kb(record_id, back_cb="adm_search"),
        )
        return ADMIN_MENU

    # ── Просмотр записи из списка по дате ─────────────────────────────────────
    if data.startswith("adm_rec_"):
        record_id = int(data.replace("adm_rec_", ""))
        context.user_data["admin_viewing_record"] = record_id
        await query.edit_message_text(
            f"Запись #{record_id}\nЧто сделать?",
            reply_markup=admin_record_actions_kb(record_id, back_cb="adm_back_list"),
        )
        return ADMIN_MENU

    # ── Запрос подтверждения удаления ─────────────────────────────────────────
    if data.startswith("adm_del_"):
        record_id = int(data.replace("adm_del_", ""))
        await query.edit_message_text(
            f"Отменить запись #{record_id}?\nКлиент получит уведомление в боте.",
            reply_markup=admin_confirm_delete_kb(record_id),
        )
        return ADMIN_MENU

    # ── Подтверждённое удаление ───────────────────────────────────────────────
    if data.startswith("adm_confirm_del_"):
        record_id = int(data.replace("adm_confirm_del_", ""))
        return await _cancel_record(update, context, record_id)

    return ADMIN_MENU


# ── Загрузка записей с API (первый раз для дня) ───────────────────────────────

async def _load_records(update: Update, context: ContextTypes.DEFAULT_TYPE, day: str) -> int:
    query = update.callback_query
    await query.edit_message_text(f"Загружаю записи на {day}…")
    try:
        records = await yclients.get_records(day)
    except Exception as e:
        log.error("get_records error: %s", e)
        await query.edit_message_text("Ошибка загрузки записей.", reply_markup=admin_menu_kb())
        return ADMIN_MENU

    if not records:
        await query.edit_message_text(f"На {day} записей нет.", reply_markup=admin_menu_kb())
        return ADMIN_MENU

    context.user_data["admin_records"] = records
    context.user_data["admin_date"] = day
    context.user_data["admin_page"] = 0
    return await _render_records_page(update, context, 0)


# ── Отрисовка страницы записей (с пагинацией и фильтром) ─────────────────────

async def _render_records_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> int:
    query = update.callback_query
    day = context.user_data.get("admin_date", "?")
    all_records = context.user_data.get("admin_records", [])
    active_master = context.user_data.get("admin_filter_master")

    # Применяем фильтр по мастеру
    if active_master:
        filtered = [r for r in all_records if (r.get("staff") or {}).get("name", "") == active_master]
    else:
        filtered = all_records

    if not filtered:
        filter_note = f" (мастер: {active_master})" if active_master else ""
        await query.edit_message_text(
            f"На {day}{filter_note} записей нет.",
            reply_markup=admin_menu_kb(),
        )
        return ADMIN_MENU

    total_pages = math.ceil(len(filtered) / PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    context.user_data["admin_page"] = page

    records_page = filtered[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    # Заголовок сообщения
    filter_note = f" · {escape_markdown(active_master, version=1)}" if active_master else ""
    header = f"📋 *Записи на {day}{filter_note}* ({len(filtered)} шт.)\n\n"
    lines = [header]
    for r in records_page:
        dt = r.get("datetime", "")
        time_str = dt[11:16] if len(dt) >= 16 else "?"
        staff_name = (r.get("staff") or {}).get("name", "?")
        client_name = (r.get("client") or {}).get("name", "?")
        services = ", ".join(s.get("title", "") for s in r.get("services", []))
        lines.append(
            f"• {time_str} | {escape_markdown(staff_name, version=1)} | "
            f"{escape_markdown(client_name, version=1)} | {escape_markdown(services, version=1)}"
        )

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=admin_records_kb(records_page, page, total_pages, active_master),
    )
    return ADMIN_MENU


# ── Отмена записи ─────────────────────────────────────────────────────────────

async def _cancel_record(update: Update, context: ContextTypes.DEFAULT_TYPE, record_id: int) -> int:
    query = update.callback_query
    await query.edit_message_text(f"Отменяю запись #{record_id}…")
    try:
        ok = await yclients.delete_record(record_id)
    except Exception as e:
        log.error("delete_record error: %s", e)
        ok = False

    if ok:
        booking = await get_booking_by_record_id(record_id)
        detail = ""
        if booking:
            dt = booking.get("appointment_datetime", "")
            detail = f"{booking.get('client_name','')} / {booking.get('service_name','')} / {dt[:16]}"
            await cancel_booking_by_id(booking["id"])
            try:
                date_str = dt[:10] if dt else "?"
                time_str = dt[11:16] if len(dt) >= 16 else "?"
                await context.bot.send_message(
                    booking["user_id"],
                    f"❗️ Ваша запись на {date_str} в {time_str} к "
                    f"{escape_markdown(booking.get('master_name', '?'), version=1)} "
                    f"была отменена администратором.\n\n"
                    f"Если хотите перенести — позвоните: {BUSINESS_PHONE_LINK}",
                    parse_mode="Markdown",
                )
            except Exception as e:
                log.warning("Ошибка уведомления клиента при отмене record_id=%s: %s", record_id, e)

        admin_id = query.from_user.id
        await log_admin_action(admin_id, "cancel_record", record_id, detail)
        log.info("Администратор %s отменил запись #%s: %s", admin_id, record_id, detail)

        await query.edit_message_text(
            f"✅ Запись #{record_id} отменена.",
            reply_markup=admin_menu_kb(),
        )
    else:
        await query.edit_message_text(
            f"❌ Не удалось отменить запись #{record_id}. Проверьте в YClients.",
            reply_markup=admin_menu_kb(),
        )
    return ADMIN_MENU


async def admin_exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Выход из панели администратора.")
    return ConversationHandler.END


# ── Сборка ConversationHandler ────────────────────────────────────────────────

def build_admin_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("admin", admin_start)],
        states={
            ADMIN_PASSWORD_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_check_password),
            ],
            ADMIN_MENU: [
                CallbackQueryHandler(admin_menu_callback, pattern="^adm_"),
            ],
            ADMIN_SEARCH_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_search_handler),
                CallbackQueryHandler(admin_menu_callback, pattern="^adm_back$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_exit)],
        allow_reentry=True,
        per_message=False,
    )
