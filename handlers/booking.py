"""
Основной ConversationHandler для записи клиента.

Состояния:
  SELECT_CATEGORY → SELECT_SERVICE → MASTER_OR_RECOMMEND
    → [RECOMMEND_Q1 → RECOMMEND_Q2] → SELECT_MASTER → MASTER_PROFILE
    → SELECT_DATE → SELECT_TIME → ENTER_NAME → ENTER_PHONE → CONFIRM
"""
import logging
from telegram import Update
from telegram.helpers import escape_markdown
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from keyboards.builders import (
    categories_kb,
    services_kb,
    master_or_recommend_kb,
    masters_kb,
    master_profile_kb,
    dates_kb,
    no_dates_kb,
    times_kb,
    confirm_kb,
    main_menu_kb,
)
from handlers.recommendation import (
    show_recommend_q1,
    handle_recommend_q1,
    handle_recommend_q2,
)
from data.masters import MASTERS
from services import yclients
from services.database import log_booking
from config import ADMIN_TELEGRAM_IDS, BUSINESS_PHONE_LINK

log = logging.getLogger(__name__)

# ── Состояния ─────────────────────────────────────────────────────────────────
(
    SELECT_CATEGORY,
    SELECT_SERVICE,
    MASTER_OR_RECOMMEND,
    RECOMMEND_Q1,
    RECOMMEND_Q2,
    SELECT_MASTER,
    MASTER_PROFILE,
    SELECT_DATE,
    SELECT_TIME,
    ENTER_NAME,
    ENTER_PHONE,
    CONFIRM,
) = range(12)

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "hair": ["стрижк", "окрашив", "уход", "тонирован", "плетен", "кос", "укладк", "перманент"],
    "nails": ["маникюр", "педикюр", "наращив", "ногт"],
    "cosmetology": ["пилинг", "косметолог", "чистк", "лазер", "бров", "эпиляц", "экзосом", "renophase", "mediderma"],
    "massage": ["массаж"],
}


def _filter_services_by_category(services: list[dict], category: str) -> list[dict]:
    keywords = CATEGORY_KEYWORDS.get(category, [])
    result = [
        s for s in services
        if any(kw in s.get("title", "").lower() for kw in keywords)
    ]
    return result if result else services[:15]


def _years(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return "лет"
    r = n % 10
    if r == 1:
        return "год"
    if 2 <= r <= 4:
        return "года"
    return "лет"


def _master_profile(name: str) -> dict | None:
    for m in MASTERS:
        if m["name"].lower() == name.lower():
            return m
    return None


def _master_bio(name: str) -> str:
    m = _master_profile(name)
    if m:
        exp = m["experience"]
        return f"_{m['bio']}_\n\nОпыт: {exp} {_years(exp)}"
    return ""


# ── 1. Вход в бронирование ────────────────────────────────────────────────────

async def booking_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    if query.message.photo:
        # Стартовое сообщение — фото (логотип): нельзя edit_message_text
        await query.message.reply_text("Выберите категорию услуг:", reply_markup=categories_kb())
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        await query.edit_message_text("Выберите категорию услуг:", reply_markup=categories_kb())
    return SELECT_CATEGORY


# ── 2. Категория → список услуг с ценами ─────────────────────────────────────

async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    category = query.data.replace("cat_", "")
    context.user_data["category"] = category

    await query.edit_message_text("Загружаю услуги…")
    try:
        all_services = await yclients.get_services()
        services = _filter_services_by_category(all_services, category)
    except Exception as e:
        log.error("get_services error: %s", e)
        await query.edit_message_text(
            f"Не удалось загрузить услуги. Позвоните: {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )
        return ConversationHandler.END

    if not services:
        await query.edit_message_text(
            f"Услуги не найдены. Позвоните: {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )
        return ConversationHandler.END

    context.user_data["services_list"] = services
    await query.edit_message_text(
        "Выберите услугу:",
        reply_markup=services_kb(services),
    )
    return SELECT_SERVICE


async def services_page_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    page = int(query.data.replace("services_page_", ""))
    services = context.user_data.get("services_list", [])
    await query.edit_message_text(
        "Выберите услугу:",
        reply_markup=services_kb(services, page),
    )
    return SELECT_SERVICE


async def services_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return SELECT_SERVICE


# ── 3. Услуга → мастер или рекомендация ──────────────────────────────────────

async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    service_id = int(query.data.replace("service_", ""))
    context.user_data["service_id"] = service_id

    services = context.user_data.get("services_list", [])
    service = next((s for s in services if s["id"] == service_id), None)
    name = service["title"] if service else "Услуга"
    price = service.get("price_min") if service else None
    context.user_data["service_name"] = name

    price_str = f"\nЦена: от {int(price):,} ₽".replace(",", " ") if price else ""
    await query.edit_message_text(
        f"Услуга: *{escape_markdown(name, version=1)}*{price_str}\n\nКак будем выбирать мастера?",
        parse_mode="Markdown",
        reply_markup=master_or_recommend_kb(),
    )
    return MASTER_OR_RECOMMEND


# ── 4a. Выбрать мастера самому ────────────────────────────────────────────────

async def pick_master_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    service_id = context.user_data.get("service_id")
    await query.edit_message_text("Загружаю мастеров…")
    try:
        staff = await yclients.get_staff([service_id] if service_id else None)
    except Exception as e:
        log.error("get_staff error: %s", e)
        await query.edit_message_text(
            f"Не удалось загрузить мастеров. Позвоните: {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )
        return ConversationHandler.END

    context.user_data["staff_list"] = staff
    await query.edit_message_text(
        "Выберите мастера:",
        reply_markup=masters_kb(staff),
    )
    return SELECT_MASTER


# ── 4b. Анкета: вопрос 1 ─────────────────────────────────────────────────────

async def start_recommendation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await show_recommend_q1(update, context)
    return RECOMMEND_Q1


async def recommendation_q1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await handle_recommend_q1(update, context)
    return RECOMMEND_Q2


async def recommendation_q2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await handle_recommend_q2(update, context)
    return SELECT_MASTER


# ── 5a. Мастер выбран по ID (из списка) — показать карточку ──────────────────

async def master_selected_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    staff_id = int(query.data.replace("master_", ""))

    staff_list = context.user_data.get("staff_list", [])
    master = next((s for s in staff_list if s["id"] == staff_id), None)
    if not master:
        await query.edit_message_text("Мастер не найден, попробуйте снова.")
        return SELECT_MASTER

    context.user_data["staff_id"] = staff_id
    context.user_data["master_name"] = master["name"]
    return await _show_master_profile(update, context)


# ── 5b. Мастер выбран из рекомендаций — матчим с YClients, показываем карточку

async def master_selected_by_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    master_name = query.data.replace("rec_master_", "")

    service_id = context.user_data.get("service_id")
    await query.edit_message_text("Загружаю информацию о мастере…")
    try:
        staff = await yclients.get_staff([service_id] if service_id else None)
    except Exception as e:
        log.error("get_staff error: %s", e)
        await query.edit_message_text(
            f"Ошибка. Позвоните: {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    matched = next(
        (s for s in staff if master_name.lower() in s.get("name", "").lower()),
        None,
    )
    if matched:
        context.user_data["staff_id"] = matched["id"]
        context.user_data["master_name"] = matched["name"]
        context.user_data["staff_list"] = staff
    else:
        context.user_data["staff_list"] = staff
        await query.edit_message_text(
            f"Мастер *{escape_markdown(master_name, version=1)}* временно недоступен для онлайн-записи.\n"
            "Выберите другого:",
            parse_mode="Markdown",
            reply_markup=masters_kb(staff),
        )
        return SELECT_MASTER

    return await _show_master_profile(update, context)


# ── 5c. Карточка мастера ──────────────────────────────────────────────────────

async def _show_master_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    name = context.user_data["master_name"]
    bio = _master_bio(name)
    safe_name = escape_markdown(name, version=1)
    text = f"👤 *{safe_name}*\n\n{bio}" if bio else f"👤 *{safe_name}*"
    kb = master_profile_kb(name)

    master = _master_profile(name)
    photo_sent = False

    if master:
        photo = master.get("photo_id") or master.get("photo_url")
        if photo:
            try:
                import os
                if not master.get("photo_id") and isinstance(photo, str) and os.path.isfile(photo):
                    with open(photo, "rb") as f:
                        msg = await query.message.reply_photo(
                            photo=f,
                            caption=text,
                            parse_mode="Markdown",
                            reply_markup=kb,
                        )
                else:
                    msg = await query.message.reply_photo(
                        photo=photo,
                        caption=text,
                        parse_mode="Markdown",
                        reply_markup=kb,
                    )
                # Кешируем file_id чтобы не загружать файл повторно
                if not master.get("photo_id") and msg.photo:
                    master["photo_id"] = msg.photo[-1].file_id
                photo_sent = True
                try:
                    await query.edit_message_reply_markup(reply_markup=None)
                except Exception:
                    pass
            except Exception as e:
                log.warning("Не удалось отправить фото мастера %s: %s", name, e)

    if not photo_sent:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    return MASTER_PROFILE


# ── 5d. Клиент подтвердил выбор мастера → даты ───────────────────────────────

async def master_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await _load_dates(update, context)


# ── 6. Загрузить доступные даты ───────────────────────────────────────────────

async def _load_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    staff_id = context.user_data["staff_id"]
    service_id = context.user_data["service_id"]
    master_name = context.user_data["master_name"]

    # Фото-сообщение нельзя редактировать как текст → отправляем новое
    is_photo = bool(query.message.photo)
    if is_photo:
        await query.message.reply_text("Загружаю свободные даты…")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        await query.edit_message_text("Загружаю свободные даты…")

    try:
        dates = await yclients.get_available_dates(staff_id, [service_id])
    except Exception as e:
        log.error("get_available_dates error: %s", e)
        await query.message.reply_text(
            f"Ошибка расписания. Позвоните: {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    safe_master_name = escape_markdown(master_name, version=1)

    if not dates:
        await query.message.reply_text(
            f"У мастера *{safe_master_name}* нет свободных дат.\n\n"
            f"Выберите другого мастера или позвоните: {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
            reply_markup=no_dates_kb(),
        )
        return MASTER_PROFILE

    context.user_data["available_dates"] = dates
    await query.message.reply_text(
        f"Мастер: *{safe_master_name}*\n\nВыберите удобную дату:",
        parse_mode="Markdown",
        reply_markup=dates_kb(dates[:30]),
    )
    return SELECT_DATE


# ── 6b. Вернуться к выбору дат (кнопка ← Назад из выбора времени) ────────────

async def back_to_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Повторно показывает экран выбора даты без повторного запроса к API."""
    query = update.callback_query
    await query.answer()
    dates = context.user_data.get("available_dates", [])
    master_name = context.user_data.get("master_name", "")
    if not dates:
        # Если дат в кеше нет — перезагружаем
        return await _load_dates(update, context)
    await query.edit_message_text(
        f"Мастер: *{escape_markdown(master_name, version=1)}*\n\nВыберите удобную дату:",
        parse_mode="Markdown",
        reply_markup=dates_kb(dates[:30]),
    )
    return SELECT_DATE


# ── 7. Дата → слоты времени ──────────────────────────────────────────────────

async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date = query.data.replace("date_", "")
    context.user_data["selected_date"] = date

    staff_id = context.user_data["staff_id"]
    service_id = context.user_data["service_id"]

    await query.edit_message_text("Загружаю доступное время…")
    try:
        slots = await yclients.get_available_times(staff_id, date, [service_id])
    except Exception as e:
        log.error("get_available_times error: %s", e)
        await query.edit_message_text(
            f"Ошибка. Позвоните: {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    if not slots:
        await query.edit_message_text(
            "На эту дату нет свободного времени. Выберите другую:",
            reply_markup=dates_kb(context.user_data.get("available_dates", [])[:30]),
        )
        return SELECT_DATE

    context.user_data["slots"] = slots
    await query.edit_message_text(
        f"Дата: *{date}*\n\nВыберите время:",
        parse_mode="Markdown",
        reply_markup=times_kb(slots),
    )
    return SELECT_TIME


# ── 8. Время → ввод имени ────────────────────────────────────────────────────

async def time_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    datetime_str = query.data.replace("time_", "")
    context.user_data["appointment_datetime"] = datetime_str

    time_display = datetime_str[11:16] if len(datetime_str) >= 16 else datetime_str
    await query.edit_message_text(
        f"Время: *{time_display}*\n\nВведите ваше имя:\n_(для отмены — /cancel)_",
        parse_mode="Markdown",
    )
    return ENTER_NAME


# ── 9. Имя → ввод телефона ───────────────────────────────────────────────────

async def name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    import re
    if not re.match(r'^[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\s\-]{1,49}$', name):
        await update.message.reply_text(
            "Введите имя буквами (например: Анна или Анна Иванова).\n"
            "Для отмены — /cancel"
        )
        return ENTER_NAME
    context.user_data["client_name"] = name
    await update.message.reply_text(
        "Введите номер телефона:\n_(например: 79001234567 или +7 900 123-45-67)_\n\nДля отмены — /cancel",
        parse_mode="Markdown",
    )
    return ENTER_PHONE


# ── 10. Телефон → итоговое подтверждение ─────────────────────────────────────

async def phone_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    phone = "".join(c for c in raw if c.isdigit())
    if len(phone) == 10:
        phone = "7" + phone
    if len(phone) != 11 or phone[0] not in ("7", "8"):
        await update.message.reply_text(
            "Не удалось распознать номер. Введите российский номер, например: 79001234567\n"
            "Для отмены — /cancel"
        )
        return ENTER_PHONE
    if phone[0] == "8":
        phone = "7" + phone[1:]
    context.user_data["client_phone"] = phone

    d = context.user_data
    dt = d.get("appointment_datetime", "")
    date_display = dt[:10] if dt else "?"
    time_display = dt[11:16] if len(dt) >= 16 else "?"

    summary = (
        "📋 *Проверьте вашу запись:*\n\n"
        f"🏪 Салон Персона, Красногорск\n"
        f"💅 Услуга: {escape_markdown(d.get('service_name', '?'), version=1)}\n"
        f"👤 Мастер: {escape_markdown(d.get('master_name', '?'), version=1)}\n"
        f"📅 Дата: {date_display}\n"
        f"⏰ Время: {time_display}\n"
        f"👤 Имя: {d.get('client_name', '?')}\n"
        f"📞 Телефон: +{phone}\n\n"
        "Всё верно?"
    )
    await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=confirm_kb())
    return CONFIRM


# ── 11. Подтверждение → создать запись ───────────────────────────────────────

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        await query.edit_message_text(
            "Хорошо, начнём заново. Выберите категорию:",
            reply_markup=categories_kb(),
        )
        return SELECT_CATEGORY

    d = context.user_data
    await query.edit_message_text("Создаю запись…")

    try:
        result = await yclients.create_booking(
            fullname=d["client_name"],
            phone=d["client_phone"],
            staff_id=d["staff_id"],
            service_id=d["service_id"],
            datetime_str=d["appointment_datetime"],
        )
        success = result.get("success", False)
        record_id = None
        if success:
            records = result.get("data", [])
            if not records or not records[0].get("id"):
                log.error("create_booking: success=True но data пустой или без id: %s", result)
                success = False
            else:
                record_id = records[0]["id"]
        else:
            log.error(
                "create_booking: YClients вернул success=False. meta=%s data=%s",
                result.get("meta"), result.get("data"),
            )
    except Exception as e:
        log.error("create_booking error: %s", e)
        success = False
        record_id = None

    dt = d.get("appointment_datetime", "")
    date_display = dt[:10] if dt else "?"
    time_display = dt[11:16] if len(dt) >= 16 else "?"

    if success:
        await log_booking(
            user_id=query.from_user.id,
            yclients_record_id=record_id,
            master_name=d.get("master_name", ""),
            service_name=d.get("service_name", ""),
            appointment_datetime=d.get("appointment_datetime", ""),
            client_name=d.get("client_name", ""),
            client_phone=d.get("client_phone", ""),
        )
        await query.edit_message_text(
            f"✅ *Запись подтверждена!*\n\n"
            f"📅 {date_display} в {time_display}\n"
            f"👤 Мастер: {escape_markdown(d.get('master_name', ''), version=1)}\n"
            f"💅 Услуга: {escape_markdown(d.get('service_name', ''), version=1)}\n\n"
            f"Ждём вас! Если понадобится перенести — позвоните:\n"
            f"📞 {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )

        admin_text = (
            f"🔔 *Новая запись!*\n"
            f"👤 {d.get('client_name')} / +{d.get('client_phone')}\n"
            f"💅 {escape_markdown(d.get('service_name', ''), version=1)}\n"
            f"✂️ Мастер: {escape_markdown(d.get('master_name', ''), version=1)}\n"
            f"📅 {date_display} в {time_display}"
        )
        for admin_id in ADMIN_TELEGRAM_IDS:
            try:
                await context.bot.send_message(admin_id, admin_text, parse_mode="Markdown")
            except Exception:
                pass
    else:
        await query.edit_message_text(
            f"❌ Не удалось создать запись онлайн.\n\n"
            f"Позвоните нам напрямую:\n📞 {BUSINESS_PHONE_LINK}\n"
            f"Ежедневно 10:00–22:00",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )

    return ConversationHandler.END


# ── Отмена ────────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Возвращаемся в главное меню.", reply_markup=main_menu_kb()
        )
    else:
        await update.message.reply_text("Возвращаемся в главное меню.", reply_markup=main_menu_kb())
    return ConversationHandler.END


# ── Сборка ConversationHandler ────────────────────────────────────────────────

def build_booking_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(booking_start, pattern="^book_start$")],
        states={
            SELECT_CATEGORY: [
                CallbackQueryHandler(category_selected, pattern="^cat_"),
                CallbackQueryHandler(cancel, pattern="^back_main$"),
            ],
            SELECT_SERVICE: [
                CallbackQueryHandler(service_selected, pattern="^service_\\d+$"),
                CallbackQueryHandler(services_page_selected, pattern="^services_page_"),
                CallbackQueryHandler(services_noop, pattern="^services_noop$"),
                CallbackQueryHandler(booking_start, pattern="^back_categories$"),
            ],
            MASTER_OR_RECOMMEND: [
                CallbackQueryHandler(pick_master_list, pattern="^master_pick$"),
                CallbackQueryHandler(start_recommendation, pattern="^master_recommend$"),
                CallbackQueryHandler(booking_start, pattern="^back_categories$"),
            ],
            RECOMMEND_Q1: [
                CallbackQueryHandler(recommendation_q1, pattern="^rq1_"),
            ],
            RECOMMEND_Q2: [
                CallbackQueryHandler(recommendation_q2, pattern="^rq2_"),
            ],
            SELECT_MASTER: [
                CallbackQueryHandler(master_selected_by_id, pattern="^master_\\d+$"),
                CallbackQueryHandler(master_selected_by_name, pattern="^rec_master_"),
                CallbackQueryHandler(pick_master_list, pattern="^master_pick$"),
                CallbackQueryHandler(start_recommendation, pattern="^back_master_choice$"),
            ],
            MASTER_PROFILE: [
                CallbackQueryHandler(master_confirmed, pattern="^confirm_master$"),
                CallbackQueryHandler(pick_master_list, pattern="^master_pick$"),
                CallbackQueryHandler(pick_master_list, pattern="^back_master_choice$"),
            ],
            SELECT_DATE: [
                CallbackQueryHandler(date_selected, pattern="^date_"),
                CallbackQueryHandler(pick_master_list, pattern="^back_master_choice$"),
            ],
            SELECT_TIME: [
                CallbackQueryHandler(time_selected, pattern="^time_"),
                CallbackQueryHandler(back_to_dates, pattern="^back_date$"),
            ],
            ENTER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_entered),
            ],
            ENTER_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_entered),
            ],
            CONFIRM: [
                CallbackQueryHandler(confirm_booking, pattern="^confirm_"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^back_main$"),
        ],
        allow_reentry=True,
        per_message=False,
    )
