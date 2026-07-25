import math
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import WEBAPP_URL

SERVICES_PAGE_SIZE = 20

# ── Главное меню ────────────────────────────────────────────────────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Записаться", callback_data="book_start")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
        [InlineKeyboardButton("👩‍🎨 Наши мастера", callback_data="info_masters")],
        [InlineKeyboardButton("💅 Услуги и цены", callback_data="info_services")],
        [InlineKeyboardButton("📍 Контакты и звонок", callback_data="info_contacts")],
        [InlineKeyboardButton("🌐 Наш сайт", url=WEBAPP_URL)],
    ])

# ── Категории услуг ─────────────────────────────────────────────────────────

def categories_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💇 Волосы", callback_data="cat_hair")],
        [InlineKeyboardButton("💅 Ногтевой сервис", callback_data="cat_nails")],
        [InlineKeyboardButton("✨ Косметология", callback_data="cat_cosmetology")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ])

# ── Список услуг (с ценами) ───────────────────────────────────────────────────

def services_kb(services: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    # Telegram ограничивает клавиатуру 100 кнопками — у некоторых категорий
    # (например, «Волосы») реальных услуг больше, поэтому листаем страницами.
    total_pages = math.ceil(len(services) / SERVICES_PAGE_SIZE) or 1
    page = max(0, min(page, total_pages - 1))
    page_services = services[page * SERVICES_PAGE_SIZE : (page + 1) * SERVICES_PAGE_SIZE]

    rows = []
    for s in page_services:
        price = s.get("price_min") or s.get("cost")
        price_str = f"  — от {int(price):,} ₽".replace(",", " ") if price else ""
        # Telegram ограничивает текст кнопки 64 символами — у части реальных
        # услуг название длиннее, обрезаем его, а не цену.
        title = s["title"]
        max_title_len = 64 - len(price_str)
        if len(title) > max_title_len:
            title = title[: max_title_len - 1].rstrip() + "…"
        label = title + price_str
        rows.append([InlineKeyboardButton(label, callback_data=f"service_{s['id']}")])

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀", callback_data=f"services_page_{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="services_noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("▶", callback_data=f"services_page_{page + 1}"))
        rows.append(nav)

    rows.append([InlineKeyboardButton("← Назад", callback_data="back_categories")])
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

# ── Выбор мастера или рекомендация ──────────────────────────────────────────

def master_or_recommend_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Выбрать мастера самому", callback_data="master_pick")],
        [InlineKeyboardButton("🤔 Помогите выбрать", callback_data="master_recommend")],
        [InlineKeyboardButton("← Назад", callback_data="back_categories")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ])

# ── Список мастеров ──────────────────────────────────────────────────────────

def masters_kb(masters: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(m["name"], callback_data=f"master_{m['id']}")]
        for m in masters
    ]
    rows.append([InlineKeyboardButton("← Назад", callback_data="back_master_choice")])
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

# ── Карточка мастера: подтвердить выбор ──────────────────────────────────────

def master_profile_kb(master_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Записаться к {master_name.split()[0]}", callback_data="confirm_master")],
        [InlineKeyboardButton("← Выбрать другого", callback_data="master_pick")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ])

# ── Рекомендованные мастера (по именам) ─────────────────────────────────────

def recommended_masters_kb(masters: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"✅ {m['name']}", callback_data=f"rec_master_{m['name']}")]
        for m in masters
    ]
    rows.append([InlineKeyboardButton("← Выбрать самому", callback_data="master_pick")])
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

# ── Вопрос 1: что хотите (волосы) ───────────────────────────────────────────

def recommend_q1_hair_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✂️ Стрижка", callback_data="rq1_стрижка")],
        [InlineKeyboardButton("🎨 Окрашивание", callback_data="rq1_окрашивание")],
        [InlineKeyboardButton("🌀 Плетение кос", callback_data="rq1_плетение")],
        [InlineKeyboardButton("💧 Уход за волосами", callback_data="rq1_уход")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ])

def recommend_q1_nails_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💅 Маникюр", callback_data="rq1_маникюр")],
        [InlineKeyboardButton("🦶 Педикюр", callback_data="rq1_педикюр")],
        [InlineKeyboardButton("💎 Наращивание", callback_data="rq1_наращивание")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ])

# ── Вопрос 2: предпочтение по опыту ─────────────────────────────────────────

def recommend_q2_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Любой хороший мастер", callback_data="rq2_any")],
        [InlineKeyboardButton("Опытный (10+ лет)", callback_data="rq2_experienced")],
        [InlineKeyboardButton("Только топ-мастер", callback_data="rq2_top")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ])

# ── Выбор даты ───────────────────────────────────────────────────────────────

def dates_kb(dates: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(dates), 3):
        chunk = dates[i:i+3]
        rows.append([
            InlineKeyboardButton(_format_date(d), callback_data=f"date_{d}")
            for d in chunk
        ])
    rows.append([InlineKeyboardButton("← Выбрать другого мастера", callback_data="back_master_choice")])
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def no_dates_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("← Выбрать другого мастера", callback_data="back_master_choice")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ])

def _format_date(date_str: str) -> str:
    """2026-05-20 → 20.05 Вт"""
    _days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    try:
        from datetime import date
        parts = date_str.split("-")
        d = date(int(parts[0]), int(parts[1]), int(parts[2]))
        return f"{parts[2]}.{parts[1]} {_days[d.weekday()]}"
    except Exception:
        return date_str

# ── Выбор времени ────────────────────────────────────────────────────────────

def times_kb(slots: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(slots), 4):
        chunk = slots[i:i+4]
        rows.append([
            InlineKeyboardButton(
                s.get("time", s.get("datetime", "")[11:16]),
                callback_data=f"time_{s.get('datetime', s.get('time', ''))}"
            )
            for s in chunk
        ])
    rows.append([InlineKeyboardButton("← Назад", callback_data="back_date")])
    rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

# ── Подтверждение бронирования ───────────────────────────────────────────────

def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить запись", callback_data="confirm_yes")],
        [InlineKeyboardButton("✏️ Изменить", callback_data="confirm_no")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ])

# ── Галерея мастеров ─────────────────────────────────────────────────────────

def masters_gallery_kb(idx: int, total: int) -> InlineKeyboardMarkup:
    nav = []
    if idx > 0:
        nav.append(InlineKeyboardButton("←", callback_data=f"masters_page_{idx - 1}"))
    nav.append(InlineKeyboardButton(f"{idx + 1} / {total}", callback_data="masters_noop"))
    if idx < total - 1:
        nav.append(InlineKeyboardButton("→", callback_data=f"masters_page_{idx + 1}"))
    return InlineKeyboardMarkup([
        nav,
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ])


# ── Мои записи ───────────────────────────────────────────────────────────────

def my_bookings_kb(bookings: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for b in bookings:
        dt = b.get("appointment_datetime", "")
        date_str = dt[:10] if dt else "?"
        time_str = dt[11:16] if len(dt) >= 16 else "?"
        label = f"{date_str} {time_str} — {b.get('master_name', '?')}"
        rows.append([InlineKeyboardButton(label, callback_data=f"mybk_view_{b['id']}")])
    rows.append([InlineKeyboardButton("← Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def cancel_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отменить эту запись", callback_data=f"mybk_cancel_{booking_id}")],
        [InlineKeyboardButton("← Назад к записям", callback_data="my_bookings")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_main")],
    ])


# ── Меню администратора ──────────────────────────────────────────────────────

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика",        callback_data="adm_stats")],
        [InlineKeyboardButton("📅 Записи на дату",    callback_data="adm_pick_date")],
        [InlineKeyboardButton("🔍 Поиск по клиенту",  callback_data="adm_search")],
        [InlineKeyboardButton("❌ Отменить запись",    callback_data="adm_cancel")],
        [InlineKeyboardButton("🚪 Выйти",             callback_data="adm_logout")],
    ])

def admin_dates_kb() -> InlineKeyboardMarkup:
    from datetime import date, timedelta
    today = date.today()
    dates = [(today + timedelta(days=i)) for i in range(14)]
    rows = []
    for i in range(0, len(dates), 2):
        chunk = dates[i:i+2]
        rows.append([
            InlineKeyboardButton(_format_date(d.isoformat()), callback_data=f"adm_date_{d.isoformat()}")
            for d in chunk
        ])
    rows.append([InlineKeyboardButton("← Назад", callback_data="adm_back")])
    return InlineKeyboardMarkup(rows)

def admin_records_kb(
    records_page: list[dict],
    page: int = 0,
    total_pages: int = 1,
    active_master: str | None = None,
) -> InlineKeyboardMarkup:
    """Клавиатура списка записей с пагинацией и фильтром."""
    rows = []
    for r in records_page:
        dt = r.get("datetime", "")
        time_str = dt[11:16] if len(dt) >= 16 else "?"
        staff_name = (r.get("staff") or {}).get("name", "?")
        label = f"{time_str} — {staff_name}"
        rows.append([InlineKeyboardButton(label, callback_data=f"adm_rec_{r['id']}")])

    # Пагинация (только если страниц > 1)
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀", callback_data=f"adm_page_{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="adm_noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("▶", callback_data=f"adm_page_{page + 1}"))
        rows.append(nav)

    # Фильтр по мастеру
    filter_label = f"👤 Фильтр: {active_master}" if active_master else "👤 Фильтр по мастеру"
    rows.append([InlineKeyboardButton(filter_label, callback_data="adm_filter_master")])
    rows.append([InlineKeyboardButton("← Назад", callback_data="adm_back")])
    return InlineKeyboardMarkup(rows)

def admin_masters_filter_kb(masters: list[str], active: str | None = None) -> InlineKeyboardMarkup:
    """Список мастеров для фильтрации. Активный отмечен ✅."""
    rows = []
    for name in masters:
        label = f"✅ {name}" if name == active else name
        # Обрезаем имя до 40 символов для callback_data (лимит 64 байта)
        safe_name = name[:40]
        rows.append([InlineKeyboardButton(label, callback_data=f"adm_fmaster_{safe_name}")])
    rows.append([InlineKeyboardButton("🔄 Все мастера", callback_data="adm_fmaster_all")])
    rows.append([InlineKeyboardButton("← Назад к списку", callback_data="adm_back_list")])
    return InlineKeyboardMarkup(rows)

def admin_search_results_kb(bookings: list[dict]) -> InlineKeyboardMarkup:
    """Результаты поиска по клиенту."""
    rows = []
    for b in bookings:
        dt = b.get("appointment_datetime", "")
        date_str = dt[:10] if dt else "?"
        time_str = dt[11:16] if len(dt) >= 16 else "?"
        master = b.get("master_name", "?")
        label = f"{date_str} {time_str} — {master}"
        yclients_id = b.get("yclients_record_id")
        if yclients_id:
            rows.append([InlineKeyboardButton(label, callback_data=f"adm_srec_{yclients_id}")])
    rows.append([InlineKeyboardButton("🔍 Новый поиск", callback_data="adm_search")])
    rows.append([InlineKeyboardButton("← Главное меню", callback_data="adm_back")])
    return InlineKeyboardMarkup(rows)

def admin_record_actions_kb(record_id: int, back_cb: str = "adm_back_list") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отменить эту запись", callback_data=f"adm_del_{record_id}")],
        [InlineKeyboardButton("← Назад",               callback_data=back_cb)],
    ])

def admin_confirm_delete_kb(record_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, отменить",  callback_data=f"adm_confirm_del_{record_id}")],
        [InlineKeyboardButton("← Нет, назад",    callback_data="adm_back_list")],
    ])
