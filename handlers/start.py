import os
import logging
from datetime import datetime
from telegram import Update, InputMediaPhoto
from telegram.helpers import escape_markdown
from telegram.ext import ContextTypes

from keyboards.builders import main_menu_kb, masters_gallery_kb
from data.masters import MASTERS
from config import ADMIN_TELEGRAM_IDS
from services import database as db

log = logging.getLogger(__name__)

# Absolute path to persona_bot/ directory — works regardless of cwd
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WELCOME_TEXT = (
    "Привет! Добро пожаловать в салон красоты *Персона* ✨\n\n"
    "Мы находимся по адресу:\n"
    "г. Красногорск, ул. Павшинская, д. 2\n"
    "Работаем ежедневно с 10:00 до 22:00\n\n"
    "Чем могу помочь?"
)

SERVICES_TEXT = (
    "💅 *Услуги и цены*\n\n"
    "*Волосы:*\n"
    "• Стрижка — от 1 600 ₽\n"
    "• Окрашивание — от 4 800 ₽\n"
    "• Детская стрижка — от 1 200 ₽\n"
    "• Тонирование, уход, плетение кос\n\n"
    "*Ногти:*\n"
    "• Маникюр с гель-лаком — от 3 100 ₽\n"
    "• Мужской маникюр — от 2 200 ₽\n"
    "• Педикюр с гель-лаком — от 3 800 ₽\n\n"
    "*Косметология:*\n"
    "• Пилинг RENOPHASE — от 3 800 ₽\n"
    "• Экзосомная терапия Mediderma\n"
    "• Диодная лазерная эпиляция\n"
    "• Брови — от 600 ₽"
)

CONTACTS_TEXT = (
    "📍 <b>Контакты</b>\n\n"
    "Адрес: г. Красногорск, ул. Павшинская, д. 2\n"
    "Режим работы: ежедневно 10:00–22:00\n\n"
    "📞 <a href=\"tel:+74951207667\">+7 (495) 120-76-67</a>\n"
    "Email: info@persona-krasnogorsk.ru\n\n"
    "Есть парковка у салона 🚗"
)


def _years(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return "лет"
    r = n % 10
    if r == 1:
        return "год"
    if 2 <= r <= 4:
        return "года"
    return "лет"


def _master_caption(master: dict) -> str:
    exp = master["experience"]
    category_label = {
        "hair": "Волосы",
        "nails": "Ногтевой сервис",
        "cosmetology": "Косметология",
        "massage": "Массаж",
    }
    cats = " · ".join(category_label.get(c, c) for c in master["categories"])
    return (
        f"👤 *{escape_markdown(master['name'], version=1)}*\n"
        f"_{cats}_\n\n"
        f"{master['bio']}\n\n"
        f"Опыт: {exp} {_years(exp)}"
    )


def _resolve_photo(master: dict):
    """Return photo_id (str), absolute local path (str), or None."""
    if master.get("photo_id"):
        return master["photo_id"]
    url = master.get("photo_url")
    if not url:
        return None
    if url.startswith("http"):
        return url
    # Relative path stored in masters.py — resolve against persona_bot/
    abs_path = os.path.join(_BASE_DIR, url)
    if os.path.isfile(abs_path):
        return abs_path
    log.warning("Photo not found: %s (resolved: %s)", url, abs_path)
    return None


async def _show_master_page(query, idx: int) -> None:
    master = MASTERS[idx]
    total = len(MASTERS)
    caption = _master_caption(master)
    kb = masters_gallery_kb(idx, total)

    photo = _resolve_photo(master)

    def _is_local(p) -> bool:
        return p and not p.startswith("http") and not master.get("photo_id")

    # Current message is already a photo → edit media in place
    if query.message.photo and photo:
        try:
            if _is_local(photo):
                with open(photo, "rb") as f:
                    media = InputMediaPhoto(media=f, caption=caption, parse_mode="Markdown")
                    msg = await query.edit_message_media(media=media, reply_markup=kb)
            else:
                media = InputMediaPhoto(media=photo, caption=caption, parse_mode="Markdown")
                msg = await query.edit_message_media(media=media, reply_markup=kb)
            if not master.get("photo_id") and msg.photo:
                master["photo_id"] = msg.photo[-1].file_id
            return
        except Exception as e:
            log.warning("edit_message_media failed: %s", e)

    # Current message is text → send new photo, remove buttons from old message
    if photo:
        try:
            if _is_local(photo):
                with open(photo, "rb") as f:
                    msg = await query.message.reply_photo(
                        photo=f, caption=caption, parse_mode="Markdown", reply_markup=kb
                    )
            else:
                msg = await query.message.reply_photo(
                    photo=photo, caption=caption, parse_mode="Markdown", reply_markup=kb
                )
            if not master.get("photo_id") and msg.photo:
                master["photo_id"] = msg.photo[-1].file_id
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            return
        except Exception as e:
            log.warning("reply_photo failed: %s", e)

    # No photo — show text only
    if query.message.photo:
        await query.edit_message_caption(caption=caption, parse_mode="Markdown", reply_markup=kb)
    else:
        await query.edit_message_text(caption, parse_mode="Markdown", reply_markup=kb)


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка работоспособности бота — только для администраторов."""
    if update.effective_user.id not in ADMIN_TELEGRAM_IDS:
        return  # молча игнорируем
    db_ok = await db.ping()
    mode = "mock 🧪" if YCLIENTS_MOCK else "prod ✅"
    await update.message.reply_text(
        f"✅ Бот работает\n"
        f"Режим: {mode}\n"
        f"БД: {'OK ✅' if db_ok else 'ERROR ❌'}\n"
        f"{datetime.now():%H:%M %d.%m.%Y}"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>Справка по боту «Персона»</b>\n\n"
        "• /start — главное меню\n"
        "• /mybookings — мои предстоящие записи\n"
        "• /cancel — отменить текущее действие\n"
        "• /help — эта справка\n\n"
        "Для записи нажмите «📅 Записаться» в главном меню.\n"
        "По вопросам: 📞 <a href=\"tel:+74951207667\">+7 (495) 120-76-67</a>",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


_LOGO_PATH = os.path.join(_BASE_DIR, "data", "photos", "logo.jpg")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if os.path.isfile(_LOGO_PATH):
        with open(_LOGO_PATH, "rb") as f:
            await update.message.reply_photo(
                photo=f,
                caption=WELCOME_TEXT,
                parse_mode="Markdown",
                reply_markup=main_menu_kb(),
            )
    else:
        await update.message.reply_text(
            WELCOME_TEXT,
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "info_masters":
        await _show_master_page(query, 0)

    elif data.startswith("masters_page_"):
        idx = int(data.replace("masters_page_", ""))
        await _show_master_page(query, idx)

    elif data == "masters_noop":
        pass  # клик по счётчику "1/13" — ничего не делаем

    elif data == "info_services":
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]])
        await query.message.reply_text(SERVICES_TEXT, parse_mode="Markdown", reply_markup=back_kb)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

    elif data == "info_contacts":
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")]])
        await query.message.reply_text(CONTACTS_TEXT, parse_mode="HTML", reply_markup=back_kb)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

    elif data == "back_main":
        if query.message.photo:
            await query.message.reply_text(
                WELCOME_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb()
            )
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            await query.edit_message_text(WELCOME_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb())
