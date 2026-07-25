import logging
from telegram import Update
from telegram.helpers import escape_markdown
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
)

from keyboards.builders import my_bookings_kb, cancel_booking_kb, main_menu_kb
from services.database import get_user_upcoming_bookings, cancel_booking_by_id
from services import yclients
from config import ADMIN_TELEGRAM_IDS, BUSINESS_ADDRESS

log = logging.getLogger(__name__)

VIEW_BOOKING = 0


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


async def view_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    booking_id = int(query.data.replace("mybk_view_", ""))

    user_id = update.effective_user.id
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
    if yclients_id:
        try:
            await yclients.delete_record(yclients_id)
        except Exception as e:
            log.warning("delete_record error for booking %s: %s", booking_id, e)

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
                CallbackQueryHandler(show_my_bookings, pattern="^my_bookings$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", lambda u, c: ConversationHandler.END),
        ],
        per_message=False,
        allow_reentry=True,
    )
