import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()

YCLIENTS_MOCK = os.environ.get("YCLIENTS_MOCK", "false").lower() == "true"

if not YCLIENTS_MOCK:
    YCLIENTS_PARTNER_TOKEN = os.environ["YCLIENTS_PARTNER_TOKEN"].strip()
    YCLIENTS_USER_TOKEN = os.environ["YCLIENTS_USER_TOKEN"].strip()
    YCLIENTS_COMPANY_ID = int(os.environ["YCLIENTS_COMPANY_ID"].strip())
else:
    YCLIENTS_PARTNER_TOKEN = ""
    YCLIENTS_USER_TOKEN = ""
    YCLIENTS_COMPANY_ID = 0

_raw_ids = os.environ.get("ADMIN_TELEGRAM_IDS", "")
ADMIN_TELEGRAM_IDS = []
for _x in _raw_ids.split(","):
    _x = _x.strip()
    if _x.isdigit():
        ADMIN_TELEGRAM_IDS.append(int(_x))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD не задан в .env — запуск запрещён")

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")

BUSINESS_NAME    = "Салон красоты «Персона»"
BUSINESS_ADDRESS = "г. Красногорск, ул. Павшинская, д. 2"
BUSINESS_PHONE   = "+7 (495) 120-76-67"
BUSINESS_HOURS   = "ежедневно 10:00–22:00"

# Кликабельный номер для Markdown-сообщений
_phone_digits = "".join(c for c in BUSINESS_PHONE if c.isdigit())
BUSINESS_PHONE_LINK = f"[{BUSINESS_PHONE}](tel:+{_phone_digits})"

PROXY_URL = os.environ.get("PROXY_URL", "")  # socks5://user:pass@host:port

# Резервные прокси через запятую: socks5://host1:port,socks5://host2:port
PROXY_FALLBACKS: list[str] = [
    p.strip()
    for p in os.environ.get("PROXY_FALLBACKS", "").split(",")
    if p.strip()
]

WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://persona-krasnogorsk.ru/")
