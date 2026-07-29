# Telegram-бот салона красоты «Персона»

Бот для онлайн-записи к мастерам через YClients API, с интерактивным
Telegram Mini App поверх той же бизнес-логики.
[@Personakrasnogorsk_bot](https://t.me/Personakrasnogorsk_bot) · г. Красногорск, ул. Павшинская, д. 2 ·
ежедневно 10:00–22:00 · +7 (495) 120-76-67

---

## 🎯 Функциональность

### Для клиента

- **Mini App «Записаться»** — интерактивный визард прямо в Telegram: категория →
  услуга → мастер (карусель с фото и биографией) → календарь → время →
  контакты → подтверждение. Основной способ записи, когда настроен `MINI_APP_URL`.
- **Классический флоу записи** — тот же путь через инлайн-кнопки в чате
  (`handlers/booking.py`). Работает всегда и служит запасным вариантом, если
  Mini App не настроена.
- **Умный подбор мастера** — анкета из 2 вопросов, рекомендации на основе опыта и специализации
- **Галерея мастеров** — 13 профилей с фото, биографией, стажем, услугами
- **Мои записи** (`/mybookings`) — просмотр, **отмена** и **перенос** («🔄 Перенести запись») предстоящих записей, с синхронизацией в YClients
- **Автоматические напоминания** — за 24 часа до визита
- **Справка и контакты** — прайс по категориям, адрес, кликабельный телефон

**Категории услуг:** 💇 Волосы · 💅 Ногтевой сервис · 🦶 Подология · ✨ Косметология · 🧖 Процедуры по телу
(маппинг на реальные `category_id` YClients — см. `services/catalog.py`)

### Для администратора (`/admin`)

Вход по паролю, сессия 24 часа, блокировка на 30 минут после 5 неверных попыток.

- **Статистика** — записи за сегодня / 7 / 30 дней, топ-3 услуги и мастера
- **Записи на дату** — календарь и полный список на выбранный день (с пагинацией)
- **Поиск записей** — по имени клиента или мастера
- **Отмена записи** — синхронизируется с YClients, клиент получает уведомление
- **Real-time алерты** — оповещение о новой записи (в т.ч. через Mini App), отмене и переносе клиентом
- **Полный аудит** — все действия администратора логируются

### Команды

| Команда | Описание |
|---|---|
| `/start` | Главное меню (кнопка Mini App, если настроена) |
| `/mybookings` | Мои записи — просмотр, отмена, перенос |
| `/help` | Справка и контакты |
| `/cancel` | Выход из текущего диалога |
| `/admin` | Панель администратора |
| `/ping` | Статус бота *(только для администраторов)* |

---

## 🚀 Быстрый старт (локально)

### Требования

- Python 3.10+
- YClients API (Partner Token + User Token)
- Telegram Bot Token

### Установка

```bash
cd persona_bot
pip install -r requirements.txt

# Создать .env из примера
cp .env.example .env

# Заполнить обязательные переменные:
# - TELEGRAM_BOT_TOKEN
# - YCLIENTS_PARTNER_TOKEN, YCLIENTS_USER_TOKEN, YCLIENTS_COMPANY_ID
# - ADMIN_PASSWORD, ADMIN_TELEGRAM_IDS

# Запуск
python3 bot.py
```

При старте поднимается и Telegram-polling, и встроенный веб-сервер (Mini App +
JSON API) — оба в одном asyncio-процессе, отдельно ничего запускать не нужно.
База данных `bot.db` создаётся автоматически при первом запуске.

Чтобы открыть Mini App локально в браузере (без Telegram), задайте
`WEBAPP_DEV_MODE=true` — тогда бэкенд примет запись без проверки Telegram
`initData`. **Никогда не включайте это в продакшене.**

---

## ⚙️ Конфигурация

### Обязательные переменные окружения

```env
# Telegram
TELEGRAM_BOT_TOKEN=токен_от_@BotFather
ADMIN_TELEGRAM_IDS=123456789,987654321    # ID администраторов через запятую
ADMIN_PASSWORD=надёжный_пароль            # пароль для /admin

# YClients (обязательно подключен, mock-режим — только YCLIENTS_MOCK=true для локальной отладки без API)
YCLIENTS_PARTNER_TOKEN=...
YCLIENTS_USER_TOKEN=...
YCLIENTS_COMPANY_ID=182017
```

### Опциональные переменные

```env
# Telegram Mini App — HTTPS-адрес ЭТОГО ЖЕ сервиса (домен Railway).
# Пока пусто — кнопка Mini App не показывается, работает обычный текстовый флоу.
MINI_APP_URL=

# Порт встроенного веб-сервера. Railway передаёт его автоматически через PORT.
PORT=8080

# Отключает проверку initData — ТОЛЬКО для локальной разработки Mini App.
WEBAPP_DEV_MODE=false

# Ссылка на сайт салона — кнопка «Наш сайт» в главном меню
WEBAPP_URL=https://persona-krasnogorsk.ru/

# Прокси — НЕ требуется на Railway (прямое соединение с Telegram).
# Нужен только для хостинга с ограниченным доступом к Telegram API.
# PROXY_URL=socks5://user:password@host:1080
```

---

## 📡 Подключение YClients

### 1. Получить Partner Token

Отправить заявку на `api@yclients.com` (1–3 рабочих дня).

### 2. Получить User Token

```bash
curl -X POST "https://api.yclients.com/api/v1/auth" \
  -H "Authorization: Bearer PARTNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"login": "email@example.com", "password": "password"}'
```

Взять поле `user_token` из ответа.

### 3. Узнать Company ID

ID компании есть в URL кабинета: `yclients.com/company/COMPANY_ID/`

### 4. Заполнить .env

```env
YCLIENTS_PARTNER_TOKEN=значение_из_письма
YCLIENTS_USER_TOKEN=значение_из_curl
YCLIENTS_COMPANY_ID=182017
```

### 5. Категории услуг

Бот группирует услуги по реальным `category_id` YClients (не по ключевым
словам в названии — это когда-то оставляло без категории почти половину
услуг). Если YClients заведёт новую категорию услуг, её нужно добавить в
`CATEGORY_IDS` в [`services/catalog.py`](services/catalog.py), иначе услуги
из неё будут не видны в боте (в логах появится предупреждение с `category_id`).

---

## 📱 Telegram Mini App

Интерактивная альтернатива текстовому флоу записи — тот же путь
(категория → услуга → мастер → дата → время → контакты → подтверждение), но
как нативный визард внутри Telegram.

**Как это работает:**

- `bot.py` поднимает polling бота и веб-сервер (`web/server.py`) в одном
  asyncio-цикле — отдельный процесс/сервис не нужен.
- `web/server.py` отдаёт статику Mini App (`webapp/`), фото мастеров
  (`data/photos/` → `/photos/`) и JSON API (`web/api.py`).
- `web/api.py` переиспользует ту же бизнес-логику, что и текстовый флоу
  (`services/catalog.py`, `services/yclients.py`) — правила категорий и
  фильтрации не расходятся между интерфейсами.
- Frontend (`webapp/js/app.js`) — Telegram WebApp JS SDK: `MainButton` для
  перехода между шагами, `BackButton`, `HapticFeedback`.
- Аутентификация — Telegram `initData` с HMAC-SHA256 проверкой подписи
  (`services/telegram_auth.py`), сверяется на каждый `POST /api/booking`.
- Повторный сабмит записи (двойной тап, перезагрузка страницы) блокируется и
  на клиенте (`bookingInFlight` в `app.js`), и на сервере — дедупликация по
  (пользователь, мастер, услуга, дата/время) в течение 30 секунд
  (`web/api.py`), чтобы клиент не увидел подряд «успех» и «ошибку» по одной
  записи.
- Кнопка «Записаться» в главном меню становится `web_app`-кнопкой
  автоматически, как только задан `MINI_APP_URL`; без него — обычный
  `callback_data` на классический флоу.

**Включить на Railway:** после первого деплоя скопировать публичный домен
(Settings → Networking → Public Domain) в переменную `MINI_APP_URL` (со
схемой `https://` — без неё Telegram отклонит кнопку `BadRequest`, но бот
достраивает схему сам, если её забыли).

---

## 🚀 Развёртывание в Production (Railway)

**Почему Railway:** простейший деплой из GitHub, домен и `PORT` выдаются
автоматически, автообновление по `git push`, не нужен прокси (прямое
соединение с Telegram API).

### Шаг 1: Репозиторий на GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/ваш-юзер/persona_bot
git push -u origin main
```

### Шаг 2: Развернуть

1. [railway.app](https://railway.app) → Sign up → Connect GitHub → выбрать репозиторий
2. Railway определит Python по `requirements.txt` и `Procfile` (`web: python3 bot.py`)
3. Dashboard → Variables — заполнить:
   ```env
   TELEGRAM_BOT_TOKEN=...
   YCLIENTS_PARTNER_TOKEN=...
   YCLIENTS_USER_TOKEN=...
   YCLIENTS_COMPANY_ID=182017
   ADMIN_TELEGRAM_IDS=...
   ADMIN_PASSWORD=...
   ```
4. Settings → Networking → Generate Domain — получить публичный HTTPS-домен
5. Добавить этот домен в переменную `MINI_APP_URL` (см. раздел Mini App выше)
6. Deploy — бот и веб-сервер запустятся вместе

**Логи в реальном времени:** Dashboard → Deployments → View Logs
**Обновление кода:** `git push` → Railway пересобирает и передеплоивает автоматически

### Альтернатива: свой VPS (systemd)

Если нужен полный контроль вместо Railway — любой VPS с Ubuntu 22.04+:

```bash
apt-get update && apt-get install -y python3.10 python3.10-venv git
git clone https://github.com/ваш-юзер/persona_bot && cd persona_bot
python3.10 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить переменные

cat > /etc/systemd/system/persona-bot.service << EOF
[Unit]
Description=Persona Beauty Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python3 bot.py
Restart=always
RestartSec=10
EnvironmentFile=$(pwd)/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload && systemctl enable --now persona-bot
```

Если у хостинга нет прямого доступа к Telegram API (например, часть
российских хостингов) — задать `PROXY_URL=socks5://user:pass@host:port`.
Управление: `systemctl status|restart persona-bot`, `journalctl -u persona-bot -f`.
Обновление: `git pull && systemctl restart persona-bot`.

---

## 👥 Управление мастерами

Профили хранятся в `data/masters.py`. Имена **должны точно совпадать** с именами в YClients.

```python
{
    "name": "Имя Фамилия",          # точное совпадение с YClients
    "experience": 10,                # стаж в годах
    "level": "experienced",          # "any" | "experienced" | "top" (для рекомендаций)
    "categories": ["hair", "nails"], # категории услуг
    "tags": ["стрижка", "уход"],     # теги для алгоритма подбора
    "bio": "Описание мастера.",
    "photo_url": "data/photos/name.jpg",
    "photo_id": None,                # заполнится автоматически при первом показе
}
```

### Обновить фото

1. Положить новый файл в `data/photos/` с исходным именем
2. Сбросить `"photo_id": None` в `data/masters.py`
3. Перезапустить бота

Фото также отдаются веб-сервером напрямую (`/photos/<файл>`) — их использует
Mini App для карточек мастеров (`master_photo_web_url()` в `services/catalog.py`).

---

## 📦 Структура проекта

```
persona_bot/
├── bot.py                    # точка входа: polling + веб-сервер в одном asyncio-цикле,
│                              # scheduler напоминаний, error handler, ручной lifecycle PTB
├── config.py                 # конфиг из .env
├── handlers/
│   ├── start.py              # /start, меню, галерея мастеров
│   ├── booking.py            # классический флоу записи (инлайн-кнопки)
│   ├── recommendation.py     # анкета подбора и скоринг
│   ├── my_bookings.py        # просмотр, отмена и перенос записей
│   └── admin.py              # панель администратора
├── keyboards/
│   └── builders.py           # все InlineKeyboard-клавиатуры с пагинацией
├── services/
│   ├── yclients.py           # async-клиент YClients API (SSL, retry, singleton)
│   ├── database.py           # SQLite: сессии, логи, аудит, напоминания
│   ├── catalog.py            # категории/фильтрация услуг, общая для чата и Mini App
│   ├── validators.py         # валидация имени/телефона, общая для чата и Mini App
│   └── telegram_auth.py      # проверка подписи Telegram initData (HMAC-SHA256)
├── web/
│   ├── server.py             # aiohttp-приложение: статика Mini App + JSON API
│   └── api.py                # /api/categories, /services, /masters, /dates, /times, /booking
├── webapp/                   # Telegram Mini App (frontend)
│   ├── index.html
│   ├── css/style.css
│   └── js/{api.js,app.js}
├── data/
│   ├── masters.py            # 13 мастеров и алгоритм рекомендаций
│   └── photos/                # фото мастеров и logo.jpg
├── requirements.txt
├── Procfile                  # команда запуска для Railway
├── .env.example               # шаблон конфигурации
└── bot.db                    # база данных (создаётся автоматически)
```

---

## 🛠️ Технический стек

| Компонент | Версия | Назначение |
|---|---|---|
| **python-telegram-bot** | 22+ | Async Telegram Bot API, ConversationHandler FSM |
| **aiohttp** | 3.9+ | HTTP-клиент к YClients API **и** веб-сервер Mini App/JSON API |
| **certifi** | 2024.2+ | SSL-сертификаты для HTTPS |
| **aiosqlite** | 0.19+ | Async SQLite без блокировок |
| **APScheduler** | 3.10+ | Напоминания клиентам (каждый час) |
| **python-dotenv** | 1.0+ | Конфигурация через .env |
| **Telegram WebApp JS SDK** | — | Frontend Mini App (`webapp/js/app.js`) |

---

## 🔍 Особенности реализации

### Async/await везде
- Все операции YClients, БД и Telegram асинхронные
- Бот и веб-сервер Mini App работают в одном asyncio-цикле, HTTP-сессия к YClients — singleton

### Пагинация
- Услуги: постранично в классическом флоу (категория «Волосы» — самая объёмная)
- Записи админа: по 10 на день
- Все клавиатуры в пределах лимита Telegram (100 кнопок)

### Безопасность
- Markdown-экранирование: имена мастеров, названия услуг, данные клиентов
- Проверка HMAC-подписи Telegram `initData` на каждый запрос записи из Mini App
- Дедупликация повторных сабмитов записи (клиент + сервер, 30 сек)
- Валидация SQL через параметризованные запросы
- Логирование всех действий администраторов, session timeout 24 часа для `/admin`

### Обработка ошибок
- Retry-логика для YClients API (экспоненциальный backoff, отдельно — 429 rate limit)
- Graceful fallback при недоступности YClients (понятное сообщение вместо падения)
- Алерты администраторам об ошибках (дедублирование: не более раза в 5 минут на тип ошибки)

---

## 📊 Статус проекта

**Последнее обновление:** 28 июля 2026

| Параметр | Значение |
|---|---|
| **Категорий услуг** | 5 (Волосы, Ногтевой сервис, Подология, Косметология, Процедуры по телу) |
| **Мастеров** | 13 профилей |
| **Режим** | Production (только реальный YClients, mock — для локальной отладки) |
| **Способы записи** | Mini App (интерактивный визард) + классический чат-флоу |
| **Язык интерфейса** | Русский |
| **Python** | 3.10+ |
| **Инфраструктура** | Railway (прокси не требуется) |

### Развёрнуто

- ✅ Полная интеграция YClients API v2 (запись, отмена, перенос — по всем категориям, включая мужские услуги)
- ✅ Telegram Mini App — визард записи с фото мастеров и календарём
- ✅ Telegram Bot API (python-telegram-bot 22+), классический флоу как fallback
- ✅ Мои записи: отмена и перенос с синхронизацией в YClients
- ✅ SQLite с async операциями (aiosqlite)
- ✅ Markdown-экранирование спецсимволов, HMAC-проверка initData
- ✅ Дедупликация повторных сабмитов записи
- ✅ Напоминания клиентам (за 24 часа)
- ✅ Админ-панель со статистикой, поиском и аудитом

---

## 📝 Лицензия

Приватный проект для салона красоты «Персона».
