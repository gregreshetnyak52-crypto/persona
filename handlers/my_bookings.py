import logging
from telegram import Update
from telegram.helpers import escape_markdown
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
)

from keyboards.builders import (
    my_bookings_kb,
    cancel_booking_kb,
    main_menu_kb,
    reschedule_dates_kb,
    reschedule_times_kb,
    reschedule_confirm_kb,
    reschedule_no_dates_kb,
)
from services.database import (
    get_user_upcoming_bookings,
    cancel_booking_by_id,
    update_booking_datetime,
)
from services import yclients
from config import ADMIN_TELEGRAM_IDS, BUSINESS_ADDRESS, BUSINESS_PHONE_LINK

log = logging.getLogger(__name__)

VIEW_BOOKING, RESCHEDULE_DATE, RESCHEDULE_TIME, RESCHEDULE_CONFIRM = range(4)


async def show_my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    bookings = await get_user_upcoming_bookings(user_id)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        # Если сообщение — фото (логотип), нельзя edit_message_text
        if query.message.photo:
            async def edit(text, **kwargs):
                await query.message.reply_text(text, **kwargs)
                try:
                    await query.edit_message_reply_markup(reply_markup=None)
                except Exception:
                    pass
        else:
            edit = query.edit_message_text
    else:
        edit = update.message.reply_text

    if not bookings:
        await edit(
            "У вас нет предстоящих записей.\n\nЗапишитесь через кнопку «📅 Записаться».",
            reply_markup=main_menu_kb(),
        )
        return ConversationHandler.END

    await edit(
        f"📋 *Ваши записи* ({len(bookings)}):\n\nВыберите запись для подробностей или отмены:",
        parse_mode="Markdown",
        reply_markup=my_bookings_kb(bookings),
    )
    return VIEW_BOOKING


async def _render_booking_detail(query, user_id: int, booking_id: int) -> int:
    bookings = await get_user_upcoming_bookings(user_id)
    booking = next((b for b in bookings if b["id"] == booking_id), None)

    if not booking:
        await query.edit_message_text("Запись не найдена.", reply_markup=main_menu_kb())
        return ConversationHandler.END

    dt = booking.get("appointment_datetime", "")
    date_str = dt[:10] if dt else "?"
    time_str = dt[11:16] if len(dt) >= 16 else "?"

    text = (
        f"📋 *Ваша запись:*\n\n"
        f"📅 {date_str} в {time_str}\n"
        f"👤 Мастер: {escape_markdown(booking.get('master_name', '?'), version=1)}\n"
        f"💅 Услуга: {escape_markdown(booking.get('service_name', '?'), version=1)}\n\n"
        f"📍 {BUSINESS_ADDRESS}"
    )
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=cancel_booking_kb(booking_id),
    )
    return VIEW_BOOKING


async def view_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    booking_id = int(query.data.replace("mybk_view_", ""))
    return await _render_booking_detail(query, update.effective_user.id, booking_id)


async def cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    booking_id = int(query.data.replace("mybk_cancel_", ""))

    user_id = update.effective_user.id
    bookings = await get_user_upcoming_bookings(user_id)
    booking = next((b for b in bookings if b["id"] == booking_id), None)

    if not booking:
        await query.edit_message_text("Запись не найдена.", reply_markup=main_menu_kb())
        return ConversationHandler.END

    await query.edit_message_text("Отменяю запись…")

    yclients_id = booking.get("yclients_record_id")
    ok = True
    if yclients_id:
        try:
            ok = await yclients.delete_record(yclients_id)
        except Exception as e:
            log.warning("delete_record error for booking %s: %s", booking_id, e)
            ok = False

    if not ok:
        await query.edit_message_text(
            f"❌ Не удалось отменить запись в системе. Позвоните нам напрямую:\n"
            f"📞 {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )
        return ConversationHandler.END

    await cancel_booking_by_id(booking_id)

    dt = booking.get("appointment_datetime", "")
    date_str = dt[:10] if dt else "?"
    time_str = dt[11:16] if len(dt) >= 16 else "?"

    # Уведомить администраторов
    admin_text = (
        f"❌ Клиент отменил запись\n\n"
        f"👤 {booking.get('client_name', '?')}\n"
        f"💼 {booking.get('service_name', '?')}\n"
        f"👩‍🎨 {booking.get('master_name', '?')}\n"
        f"📅 {date_str} в {time_str}"
    )
    for admin_id in ADMIN_TELEGRAM_IDS:
        try:
            await context.bot.send_message(admin_id, admin_text)
        except Exception:
            pass

    await query.edit_message_text(
        f"✅ Запись на {date_str} в {time_str} к {booking.get('master_name', '?')} отменена.\n\n"
        "Если хотите записаться снова — нажмите «📅 Записаться».",
        reply_markup=main_menu_kb(),
    )
    return ConversationHandler.END


# ── Перенос записи ────────────────────────────────────────────────────────────
# booking_log хранит только имена мастера/услуги (текстом), а не их YClients
# id — при переносе ищем актуальные staff_id/service_id по имени среди живых
# данных YClients, тем же способом, что и master_selected_by_name в booking.py.

async def _resolve_staff_and_service(booking: dict) -> tuple[int, int] | None:
    master_name = (booking.get("master_name") or "").lower()
    service_name = (booking.get("service_name") or "").lower()

    staff = await yclients.get_staff()
    matched_staff = next((s for s in staff if s.get("name", "").lower() == master_name), None)
    if not matched_staff:
        return None

    services = await yclients.get_services()
    matched_service = next((s for s in services if s.get("title", "").lower() == service_name), None)
    if not matched_service:
        return None

    return matched_staff["id"], matched_service["id"]


async def reschedule_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    booking_id = int(query.data.replace("mybk_reschedule_", ""))

    user_id = update.effective_user.id
    bookings = await get_user_upcoming_bookings(user_id)
    booking = next((b for b in bookings if b["id"] == booking_id), None)

    if not booking:
        await query.edit_message_text("Запись не найдена.", reply_markup=main_menu_kb())
        return ConversationHandler.END

    await query.edit_message_text("Ищу свободное время…")

    try:
        resolved = await _resolve_staff_and_service(booking)
    except Exception as e:
        log.error("reschedule_start: resolve error for booking %s: %s", booking_id, e)
        resolved = None

    if not resolved:
        await query.edit_message_text(
            f"Не удалось найти мастера или услугу для переноса — возможно, они изменились.\n"
            f"Позвоните нам напрямую: {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
            reply_markup=cancel_booking_kb(booking_id),
        )
        return VIEW_BOOKING

    staff_id, service_id = resolved
    context.user_data["resched"] = {
        "booking_id": booking_id,
        "staff_id": staff_id,
        "service_id": service_id,
        "master_name": booking.get("master_name", ""),
        "service_name": booking.get("service_name", ""),
        "client_name": booking.get("client_name", ""),
        "client_phone": booking.get("client_phone", ""),
    }

    try:
        dates = await yclients.get_available_dates(staff_id, [service_id])
    except Exception as e:
        log.error("reschedule_start: get_available_dates error: %s", e)
        dates = []

    if not dates:
        await query.edit_message_text(
            f"У мастера сейчас нет свободных дат для переноса.\nПозвоните нам: {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
            reply_markup=reschedule_no_dates_kb(),
        )
        return VIEW_BOOKING

    await query.edit_message_text(
        "На какую дату перенести запись?",
        reply_markup=reschedule_dates_kb(dates[:30]),
    )
    return RESCHEDULE_DATE


async def reschedule_date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date = query.data.replace("date_", "")
    resched = context.user_data.get("resched", {})

    try:
        times = await yclients.get_available_times(resched["staff_id"], date, [resched["service_id"]])
    except Exception as e:
        log.error("reschedule_date_selected: get_available_times error: %s", e)
        times = []

    if not times:
        await query.edit_message_text("На эту дату нет свободного времени, выберите другую.")
        return RESCHEDULE_DATE

    resched["date"] = date
    resched["times_list"] = times
    await query.edit_message_text(
        "Выберите время:",
        reply_markup=reschedule_times_kb(times),
    )
    return RESCHEDULE_TIME


async def reschedule_time_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    new_datetime = query.data.replace("time_", "")
    resched = context.user_data.get("resched", {})
    resched["new_datetime"] = new_datetime

    slot = next((s for s in resched.get("times_list", []) if s.get("datetime") == new_datetime), None)
    resched["seance_length"] = (slot or {}).get("seance_length") or 3600

    date_str = new_datetime[:10] if new_datetime else "?"
    time_str = new_datetime[11:16] if len(new_datetime) >= 16 else "?"

    await query.edit_message_text(
        f"Перенести запись к *{escape_markdown(resched.get('master_name', '?'), version=1)}*\n"
        f"на *{date_str} в {time_str}*?",
        parse_mode="Markdown",
        reply_markup=reschedule_confirm_kb(),
    )
    return RESCHEDULE_CONFIRM


async def reschedule_declined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    resched = context.user_data.pop("resched", {})
    booking_id = resched.get("booking_id")
    if booking_id is None:
        await query.edit_message_text("Запись не найдена.", reply_markup=main_menu_kb())
        return ConversationHandler.END
    return await _render_booking_detail(query, update.effective_user.id, booking_id)


async def reschedule_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    resched = context.user_data.get("resched", {})
    booking_id = resched.get("booking_id")

    user_id = update.effective_user.id
    bookings = await get_user_upcoming_bookings(user_id)
    booking = next((b for b in bookings if b["id"] == booking_id), None)
    yclients_id = booking.get("yclients_record_id") if booking else None

    if not booking or not yclients_id:
        await query.edit_message_text("Запись не найдена.", reply_markup=main_menu_kb())
        return ConversationHandler.END

    await query.edit_message_text("Переношу запись…")

    try:
        ok = await yclients.update_record(
            record_id=yclients_id,
            staff_id=resched["staff_id"],
            service_id=resched["service_id"],
            datetime_str=resched["new_datetime"],
            seance_length=resched["seance_length"],
            fullname=resched.get("client_name", ""),
            phone=resched.get("client_phone", ""),
        )
    except Exception as e:
        log.error("reschedule_confirmed: update_record error: %s", e)
        ok = False

    context.user_data.pop("resched", None)

    if not ok:
        await query.edit_message_text(
            f"❌ Не удалось перенести запись. Позвоните нам напрямую:\n📞 {BUSINESS_PHONE_LINK}",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )
        return ConversationHandler.END

    await update_booking_datetime(booking_id, resched["new_datetime"])

    date_str = resched["new_datetime"][:10]
    time_str = resched["new_datetime"][11:16]

    admin_text = (
        f"🔄 Клиент перенёс запись\n\n"
        f"👤 {booking.get('client_name', '?')}\n"
        f"💼 {booking.get('service_name', '?')}\n"
        f"👩‍🎨 {booking.get('master_name', '?')}\n"
        f"📅 Новое время: {date_str} в {time_str}"
    )
    for admin_id in ADMIN_TELEGRAM_IDS:
        try:
            await context.bot.send_message(admin_id, admin_text)
        except Exception:
            pass

    await query.edit_message_text(
        f"✅ Запись перенесена на {date_str} в {time_str}.\n\n"
        f"👤 Мастер: {escape_markdown(booking.get('master_name', '?'), version=1)}",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(),
    )
    return ConversationHandler.END


def build_my_bookings_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("mybookings", show_my_bookings),
            CallbackQueryHandler(show_my_bookings, pattern="^my_bookings$"),
        ],
        states={
            VIEW_BOOKING: [
                CallbackQueryHandler(view_booking, pattern="^mybk_view_"),
                CallbackQueryHandler(cancel_booking, pattern="^mybk_cancel_"),
                CallbackQueryHandler(reschedule_start, pattern="^mybk_reschedule_"),
                CallbackQueryHandler(show_my_bookings, pattern="^my_bookings$"),
            ],
            RESCHEDULE_DATE: [
                CallbackQueryHandler(reschedule_date_selected, pattern="^date_"),
                CallbackQueryHandler(show_my_bookings, pattern="^my_bookings$"),
            ],
            RESCHEDULE_TIME: [
                CallbackQueryHandler(reschedule_time_selected, pattern="^time_"),
                CallbackQueryHandler(show_my_bookings, pattern="^my_bookings$"),
            ],
            RESCHEDULE_CONFIRM: [
                CallbackQueryHandler(reschedule_confirmed, pattern="^reschedule_yes$"),
                CallbackQueryHandler(reschedule_declined, pattern="^reschedule_no$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", lambda u, c: ConversationHandler.END),
        ],
        per_message=False,
        allow_reentry=True,
    )
