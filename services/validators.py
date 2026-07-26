"""
Валидация клиентских данных при записи — общая для текстового флоу
(handlers/booking.py) и JSON API Mini App (web/api.py).
"""
import re

NAME_RE = re.compile(r'^[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z\s\-]{1,49}$')


def is_valid_name(name: str) -> bool:
    return bool(NAME_RE.match(name.strip()))


def normalize_ru_phone(raw: str) -> str | None:
    """Возвращает нормализованный номер (11 цифр, начинается с '7') или None."""
    phone = "".join(c for c in raw if c.isdigit())
    if len(phone) == 10:
        phone = "7" + phone
    if len(phone) != 11 or phone[0] not in ("7", "8"):
        return None
    if phone[0] == "8":
        phone = "7" + phone[1:]
    return phone
