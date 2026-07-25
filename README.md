# Telegram-бот салона красоты «Персона»

Интегрированный Telegram-бот для онлайн-записи к мастерам через YClients API.  
г. Красногорск, ул. Павшинская, д. 2 · ежедневно 10:00–22:00 · +7 (495) 120-76-67

---

## 🎯 Функциональность

### Для клиента

- **Запись к мастеру** — выбор категории → услуга → мастер → дата → время → контакты → подтверждение
- **Умный подбор мастера** — анкета из 2 вопросов, рекомендации на основе опыта и специализации
- **Галерея мастеров** — 13 профилей с фото, биографией, стажем, услугами
- **Мои записи** — просмотр и отмена предстоящих записей (`/mybookings`)
- **Автоматические напоминания** — за 24 часа до визита
- **Справка и контакты** — прайс по категориям, адрес, кликабельный телефон

**Категории услуг:** Волосы (109 услуг) · Ногтевой сервис (33) · Косметология (29) · Массаж (1)

### Для администратора (`/admin`)

Вход по пароль, сессия 24 часа, блокировка на 30 минут после 5 неверных попыток.

- **Статистика** — записи за сегодня / 7 / 30 дней, топ-3 услуги и мастера
- **Записи на дату** — календарь и полный список на выбранный день (с пагинацией)
- **Поиск записей** — по имени клиента или мастера
- **Отмена записи** — синхронизируется с YClients, клиент получает уведомление
- **Real-time алерты** — оповещение при новой записи и отмене клиентом
- **Полный аудит** — все действия администратора логируются

### Команды

| Команда | Описание |
|---|---|
| `/start` | Главное меню |
| `/mybookings` | Мои записи |
| `/cancel` | Выход из диалога |
| `/help` | Справка и контакты |
| `/admin` | Панель администратора |
| `/ping` | Статус бота *(только для администраторов)* |

---

## 🚀 Быстрый старт

### Требования

- Python 3.10+
- YClients API (Partner Token + User Token)
- Telegram Bot Token
- Прокси SOCKS5 (для Russian hosting) или прямое соединение

### Установка

```bash
cd persona_bot
pip install -r requirements.txt
pip install "python-telegram-bot[socks]"   # требуется для поддержки прокси

# Создать .env из примера
cp .env.example .env

# Заполнить обязательные переменные:
# - TELEGRAM_BOT_TOKEN
# - YCLIENTS_PARTNER_TOKEN, YCLIENTS_USER_TOKEN, YCLIENTS_COMPANY_ID
# - ADMIN_PASSWORD
# - ADMIN_TELEGRAM_IDS
# - PROXY_URL (если нужен)

# Запуск
python3 bot.py
```

База данных `bot.db` создаётся автоматически при первом запуске.

---

## ⚙️ Конфигурация

### Обязательные переменные окружения

```env
# Telegram
TELEGRAM_BOT_TOKEN=токен_от_@BotFather
ADMIN_TELEGRAM_IDS=123456789,987654321    # ID администраторов через запятую
ADMIN_PASSWORD=надёжный_пароль            # пароль для /admin

# YClients (обязательно подключен, mock-режим удалён)
YCLIENTS_PARTNER_TOKEN=...
YCLIENTS_USER_TOKEN=...
YCLIENTS_COMPANY_ID=182017
```

### Опциональные переменные

```env
# Прокси (НЕ требуется — сервер за границей имеет прямое соединение с Telegram)
# Может использоваться для корпоративной сети
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

---

## 🚀 Развертывание в Production

### Вариант 1: Railway (рекомендуется)

**Преимущества:** простейший деплой, автоматические обновления, встроенные переменные окружения.

#### Шаг 1: Подготовить репозиторий GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/ваш-юзер/persona_bot
git push -u origin main
```

#### Шаг 2: Развернуть на Railway

1. Перейти на [railway.app](https://railway.app)
2. Sign up → Connect GitHub → Select `persona_bot` repo
3. Railway автоматически определит Python и установит зависимости
4. Перейти в Dashboard → Variables и заполнить `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=...
   YCLIENTS_PARTNER_TOKEN=...
   YCLIENTS_USER_TOKEN=...
   YCLIENTS_COMPANY_ID=182017
   ADMIN_TELEGRAM_IDS=...
   ADMIN_PASSWORD=...
   ```
5. Нажать Deploy — бот запустится автоматически

**Логи в реальном времени:** Railway Dashboard → Deployments → View Logs

**Обновление кода:** `git push` → Railway автоматически redeploy

---

### Вариант 2: Contabo VPS (дешевый, полный контроль)

**Стоимость:** €3–4/месяц · **ОС:** Ubuntu 24.04

#### Шаг 1: Заказать VPS

1. [contabo.com](https://contabo.com) → выбрать VPS M (€3.99/мес)
2. Выбрать Ubuntu 24.04, регион Европа (Германия, Нидерланды)
3. Получить SSH-доступ

#### Шаг 2: Настроить сервер

```bash
ssh root@ВАШ_IP

# Обновить систему
apt-get update && apt-get upgrade -y

# Установить Python и зависимости
apt-get install -y python3.10 python3.10-venv python3-pip git

# Склонировать репозиторий
cd /root
git clone https://github.com/ваш-юзер/persona_bot
cd persona_bot

# Создать виртуальное окружение
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install "python-telegram-bot[socks]"
```

#### Шаг 3: Создать .env

```bash
cat > .env << EOF
TELEGRAM_BOT_TOKEN=...
YCLIENTS_PARTNER_TOKEN=...
YCLIENTS_USER_TOKEN=...
YCLIENTS_COMPANY_ID=182017
ADMIN_TELEGRAM_IDS=...
ADMIN_PASSWORD=...
EOF
```

#### Шаг 4: systemd-сервис

```bash
cat > /etc/systemd/system/persona-bot.service << EOF
[Unit]
Description=Persona Beauty Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/persona_bot
ExecStart=/root/persona_bot/venv/bin/python3 bot.py
Restart=always
RestartSec=10
EnvironmentFile=/root/persona_bot/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable persona-bot
systemctl start persona-bot
```

#### Управление

```bash
systemctl status persona-bot          # статус
systemctl restart persona-bot         # перезапуск
journalctl -u persona-bot -f          # логи
```

#### Обновление кода

```bash
cd /root/persona_bot
git pull
systemctl restart persona-bot
```

---

### Вариант 3: Oracle Cloud Always Free (бесплатно)

**Стоимость:** Бесплатно · **ОС:** Ubuntu 24.04 ARM · **ОСь:** Да, действительно бесплатно

1. [oracle.com/cloud/free](https://www.oracle.com/cloud/free) → регистрация
2. Compute → Instances → Create Instance → выбрать Ubuntu 24.04 Minimal (ARM)
3. Следовать инструкциям из Шага 2 выше (как для Contabo)

**Минусы:** Нужна валидная кредитная карта при регистрации, может быть медленнее чем x86

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

---

## 📦 Структура проекта

```
persona_bot/
├── bot.py                    # точка входа, scheduler напоминаний, error handler
├── config.py                 # конфиг из .env
├── handlers/
│   ├── start.py              # /start, меню, галерея мастеров
│   ├── booking.py            # флоу записи (12 состояний)
│   ├── recommendation.py     # анкета подбора и скоринг
│   ├── my_bookings.py        # просмотр и отмена записей
│   └── admin.py              # панель администратора
├── keyboards/
│   └── builders.py           # все InlineKeyboard-клавиатуры с пагинацией
├── services/
│   ├── yclients.py           # async-клиент YClients API (SSL, retry, singleton)
│   └── database.py           # SQLite: сессии, логи, аудит, напоминания
├── data/
│   ├── masters.py            # 13 мастеров и алгоритм рекомендаций
│   └── photos/               # фото мастеров и logo.jpg
├── requirements.txt
├── .env.example              # шаблон конфигурации
└── bot.db                    # база данных (создаётся автоматически)
```

---

## 🛠️ Технический стек

| Компонент | Версия | Назначение |
|---|---|---|
| **python-telegram-bot** | 22+ | Async Telegram Bot API, ConversationHandler FSM |
| **aiohttp** | 3.9+ | HTTP-клиент для YClients REST API |
| **certifi** | 2024.2+ | SSL-сертификаты для HTTPS на macOS |
| **aiosqlite** | 0.19+ | Async SQLite без блокировок |
| **APScheduler** | 3.10+ | Напоминания клиентам (каждый час) |
| **python-dotenv** | 1.0+ | Конфигурация через .env |

---

## 🔍 Особенности реализации

### Async/await везде
- Все операции YClients, БД, и Telegram асинхронные
- Сессия HTTP переиспользуется через singleton
- Нет блокировок в основном потоке

### Пагинация
- Услуги: по 20 на странице (категория «Волосы» имеет 109 услуг)
- Записи админа: по 10 на день
- Все клавиатуры находятся в пределах лимита Telegram (100 кнопок)

### Безопасность
- Markdown-экранирование: имена мастеров, названия услуг, данные клиентов
- Валидация SQL через параметризованные запросы (sqlite3 встроенная защита)
- Логирование всех действий администраторов
- Session timeout 24 часа для /admin

### Обработка ошибок
- Retry логика для YClients API
- Graceful fallback при недоступности сервиса
- Алерты администраторам об ошибках (дедублирование: не более 1 раза в 5 минут)
- Watchdog для прокси-соединения (при сбое ищет резервный)

---

## 📊 Статус проекта

**Последнее обновление:** 25 июля 2026

| Параметр | Значение |
|---|---|
| **Услуг в YClients** | 292 реальные |
| **Мастеров** | 13 профилей |
| **Категорий** | 4 (Волосы, Ногти, Косметология, Массаж) |
| **Режим** | Production (только реальный YClients, mock удалён) |
| **Язык интерфейса** | Русский |
| **Python** | 3.10+ |
| **Инфраструктура** | Railway / Contabo / Oracle Cloud (выбор) |
| **Прокси** | Не требуется (сервер за границей) |

### Развернуто

- ✅ Полная интеграция YClients API v2
- ✅ Telegram Bot API (python-telegram-bot 22+)
- ✅ SQLite с async операциями (aiosqlite)
- ✅ Пагинация услуг (по 20 на странице)
- ✅ Markdown-экранирование спецсимволов
- ✅ Обработка null-значений в данных YClients
- ✅ SSL-сертификаты (certifi)
- ✅ Напоминания клиентам (за 24 часа)
- ✅ Админ-панель с аудитом
- ✅ Статистика записей

---

## 📝 Лицензия

Приватный проект для салона красоты «Персона».
