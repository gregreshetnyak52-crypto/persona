"""
Общая логика каталога услуг и мастеров — используется и текстовым флоу записи
(handlers/booking.py, handlers/start.py), и JSON API для Mini App (web/api.py),
чтобы правила фильтрации/подписи не расходились между двумя интерфейсами.
"""
import os

from data.masters import MASTERS

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "hair": ["стрижк", "окрашив", "уход", "тонирован", "плетен", "кос", "укладк", "перманент"],
    "nails": ["маникюр", "педикюр", "наращив", "ногт"],
    "cosmetology": ["пилинг", "косметолог", "чистк", "лазер", "бров", "эпиляц", "экзосом", "renophase", "mediderma"],
    "massage": ["массаж"],
}

# Соответствует кнопкам categories_kb() в keyboards/builders.py.
CATEGORIES = [
    {"id": "hair", "label": "💇 Волосы"},
    {"id": "nails", "label": "💅 Ногтевой сервис"},
    {"id": "cosmetology", "label": "✨ Косметология"},
]


def filter_services_by_category(services: list[dict], category: str) -> list[dict]:
    keywords = CATEGORY_KEYWORDS.get(category, [])
    result = [
        s for s in services
        if any(kw in s.get("title", "").lower() for kw in keywords)
    ]
    return result if result else services[:15]


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
