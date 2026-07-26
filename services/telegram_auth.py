"""
Проверка Telegram.WebApp.initData на бэкенде Mini App.

Без этой проверки любой мог бы прислать чужой telegram user_id в запросе
к /api/booking и получить запись/уведомления от имени другого человека.
Алгоритм — официальная HMAC-схема Telegram для Mini Apps.
"""
import hashlib
import hmac
import json
import logging
import time
import urllib.parse

from config import TELEGRAM_BOT_TOKEN

log = logging.getLogger(__name__)

MAX_INIT_DATA_AGE = 86400  # 24 часа — не принимаем протухший/перехваченный initData


def validate_init_data(init_data: str, max_age: int = MAX_INIT_DATA_AGE) -> dict | None:
    """Возвращает провалидированный dict пользователя Telegram или None."""
    if not init_data:
        return None
    try:
        pairs = dict(urllib.parse.parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))

    secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        log.warning("Telegram initData: несовпадение хэша (возможна подделка запроса)")
        return None

    auth_date = pairs.get("auth_date")
    if not auth_date:
        return None
    try:
        if time.time() - int(auth_date) > max_age:
            log.warning("Telegram initData: истёк срок действия (auth_date)")
            return None
    except ValueError:
        return None

    user_json = pairs.get("user")
    if not user_json:
        return None
    try:
        return json.loads(user_json)
    except (json.JSONDecodeError, TypeError):
        return None
