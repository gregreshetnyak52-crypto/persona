"""
Общая логика каталога услуг и мастеров — используется и текстовым флоу записи
(handlers/booking.py, handlers/start.py), и JSON API для Mini App (web/api.py),
чтобы правила фильтрации/подписи не расходились между двумя интерфейсами.
"""
import logging
import os

from data.masters import MASTERS

log = logging.getLogger(__name__)

# Соответствие "наша категория в боте" -> реальные category_id из YClients
# (филиал #182017). Раньше категория определялась по ключевым словам в
# названии услуги — оказалось, что почти половина услуг (126 из 292) не
# содержит нужных слов в заголовке (например, "Мелирование", "Бедра",
# "Прессотерапия всего тела") и была НЕВИДИМА в боте. category_id — это то,
# как сама YClients группирует услуги, и он есть у каждой услуги всегда.
CATEGORY_IDS: dict[str, set[int]] = {
    "hair": {
        2796168,   # Стрижка
        2796163,   # Окрашивание
        2796159,   # Мелирование
        2796166,   # Окрашивание Lebel
        2796169,   # Творческая работа (двойное окрашивание)
        2796155,   # Тонирование
        2796156,   # Блондирование
        2796167,   # Сложное окрашивание Loreal
        2796177,   # Уходы для волос LEBEL
        2796172,   # Укладка
        7187920,   # Уход для волос Tokio Inkarami
        2796157,   # Кератиновое выпрямление волос
        24478647,  # Шитьё седины
        20245659,  # Уход для волос ADVANTE
        2796158,   # Лечение волос
        8412150,   # "Выход" из чёрного
        3134521,   # Химическая завивка волос
        12929647,  # Афроплетение и косы
        18299543,  # Услуги стилиста по подбору образа
    },
    "nails": {
        12153281,  # Nail топ мастер маникюр
        12154651,  # Nail топ мастер педикюр
    },
    "podology": {
        10811208,  # Подология
    },
    "cosmetology": {
        2796143,  # Уходы за лицом
        2796144,  # Пилинги
        2796138,  # Брови и ресницы
        19242420,  # Микронидлинг
        6040810,   # Безинъекционная мезотерапия Nanoasia
        2933456,   # Прокол ушей
        2796148,   # Эпиляция
    },
    "body": {
        27936312,  # Прессотерапия / EMS
    },
}

# "Услуги для мужчин" в YClients — единая категория, но фактически смешивает
# стрижки, маникюр/педикюр и чистку лица в одном пакете. Настоящего
# отдельного category_id для каждого типа внутри неё нет, поэтому здесь
# (и только здесь) разбираем по ключевым словам в названии.
_MENS_CATEGORY_ID = 2817060
_MENS_NAILS_KEYWORDS = ["маникюр", "педикюр"]
_MENS_COSMETOLOGY_KEYWORDS = ["чистка лица", "бров"]

# Соответствует кнопкам categories_kb() в keyboards/builders.py.
CATEGORIES = [
    {"id": "hair", "label": "💇 Волосы"},
    {"id": "nails", "label": "💅 Ногтевой сервис"},
    {"id": "podology", "label": "🦶 Подология"},
    {"id": "cosmetology", "label": "✨ Косметология"},
    {"id": "body", "label": "🧖 Процедуры по телу"},
]

_warned_category_ids: set[int] = set()


def _resolve_ui_category(service: dict) -> str | None:
    cat_id = service.get("category_id")

    if cat_id == _MENS_CATEGORY_ID:
        title = service.get("title", "").lower()
        if any(kw in title for kw in _MENS_NAILS_KEYWORDS):
            return "nails"
        if any(kw in title for kw in _MENS_COSMETOLOGY_KEYWORDS):
            return "cosmetology"
        return "hair"

    for ui_category, ids in CATEGORY_IDS.items():
        if cat_id in ids:
            return ui_category

    if cat_id is not None and cat_id not in _warned_category_ids:
        _warned_category_ids.add(cat_id)
        log.warning(
            "Услуга с неизвестным category_id=%s не попадёт ни в одну категорию бота: %r",
            cat_id, service.get("title"),
        )
    return None


def filter_services_by_category(services: list[dict], category: str) -> list[dict]:
    return [s for s in services if _resolve_ui_category(s) == category]


def years_word(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return "лет"
    r = n % 10
    if r == 1:
        return "год"
    if 2 <= r <= 4:
        return "года"
    return "лет"


def find_master_profile(name: str) -> dict | None:
    for m in MASTERS:
        if m["name"].lower() == name.lower():
            return m
    return None


def master_bio_text(name: str) -> str:
    m = find_master_profile(name)
    if m:
        exp = m["experience"]
        return f"_{m['bio']}_\n\nОпыт: {exp} {years_word(exp)}"
    return ""


def master_photo_web_url(photo_url: str | None) -> str | None:
    """Преобразует photo_url из data/masters.py в веб-путь для Mini App.
    http(s)-ссылки остаются как есть, локальные пути отдаются через /photos/."""
    if not photo_url:
        return None
    if photo_url.startswith("http://") or photo_url.startswith("https://"):
        return photo_url
    return f"/photos/{os.path.basename(photo_url)}"
