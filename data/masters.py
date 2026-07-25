"""
Расширенные профили мастеров салона «Персона» для системы рекомендаций.

Поля:
  name        — имя мастера (должно совпадать с YClients)
  experience  — лет опыта
  level       — "any" | "experienced" | "top"
  categories  — категории услуг: "hair" | "nails" | "cosmetology" | "massage"
  tags        — теги специализации для скоринга
  bio         — короткое описание для клиента
  photo_url   — URL фото с сайта (None = показывать без фото)
  photo_id    — Telegram file_id после первой отправки (заполняется автоматически)

Как добавить фото:
  1. Откройте persona-krasnogorsk.ru/masters/ в браузере
  2. F12 → вкладка Network → фильтр Img → обновите страницу
  3. Скопируйте URL фото нужного мастера в поле photo_url
"""

MASTERS: list[dict] = [
    # ── ВОЛОСЫ ──────────────────────────────────────────────────────────
    {
        "name": "Наталья Березкина",
        "experience": 17,
        "level": "top",
        "categories": ["hair"],
        "tags": ["окрашивание", "сложное окрашивание", "стрижка", "уход", "женские стрижки"],
        "bio": "Мастер сложного окрашивания и авторских стрижек. Топ-специалист салона.",
        "photo_url": "data/photos/natalya_berezkina.png",
        "photo_id": None,
    },
    {
        "name": "Валентина Жданова",
        "experience": 5,
        "level": "any",
        "categories": ["hair"],
        "tags": ["стрижка", "окрашивание", "женские стрижки", "мужские стрижки", "укладка"],
        "bio": "Владеет всеми видами стрижек и базовым окрашиванием.",
        "photo_url": "data/photos/valentina_zhdanova.jpg",
        "photo_id": None,
    },
    {
        "name": "Лиля",
        "experience": 10,
        "level": "experienced",
        "categories": ["hair"],
        "tags": ["шатуш", "сложное окрашивание", "окрашивание", "креативные стрижки", "стрижка"],
        "bio": "Специалист по технике шатуш и нестандартным стрижкам.",
        "photo_url": "data/photos/liliya.jpg",
        "photo_id": None,
    },
    {
        "name": "Елена Почестнева",
        "experience": 5,
        "level": "any",
        "categories": ["hair"],
        "tags": ["мужские стрижки", "женские стрижки", "стрижка", "детские стрижки"],
        "bio": "Отлично делает мужские и женские стрижки, работает с детьми.",
        "photo_url": "data/photos/lena_pochestneva.png",
        "photo_id": None,
    },
    {
        "name": "Рита",
        "experience": 10,
        "level": "experienced",
        "categories": ["hair"],
        "tags": ["стрижка", "женские стрижки", "укладка", "уход"],
        "bio": "Стрижки любой сложности, идеальные укладки.",
        "photo_url": "data/photos/rita.jpg",
        "photo_id": None,
    },
    {
        "name": "Мария Королева",
        "experience": 10,
        "level": "experienced",
        "categories": ["hair"],
        "tags": ["плетение", "косы", "укладка", "стрижка"],
        "bio": "Специалист по плетению кос и свадебным укладкам.",
        "photo_url": "data/photos/mariya_koroleva.jpg",
        "photo_id": None,
    },
    {
        "name": "Светлана Рожкова",
        "experience": 10,
        "level": "experienced",
        "categories": ["hair"],
        "tags": ["выход из черного", "сложное окрашивание", "окрашивание", "осветление"],
        "bio": "Эксперт по выводу из тёмного цвета и сложному осветлению.",
        "photo_url": "data/photos/svetlana_rozhkova.jpg",
        "photo_id": None,
    },
    {
        "name": "Арам Акопян",
        "experience": 3,
        "level": "any",
        "categories": ["hair"],
        "tags": ["airtach", "мужские стрижки", "стрижка", "современные техники"],
        "bio": "Специализируется на технике AirTach и мужских стрижках.",
        "photo_url": "data/photos/aram.jpg",
        "photo_id": None,
    },
    {
        "name": "Наталья Попкова",
        "experience": 8,
        "level": "experienced",
        "categories": ["hair"],
        "tags": ["сложное окрашивание", "окрашивание", "балаяж", "мелирование", "стрижка"],
        "bio": "Специалист по балаяжу, мелированию и сложному окрашиванию.",
        "photo_url": "data/photos/natalya_popkova.jpg",
        "photo_id": None,
    },

    # ── НОГТИ ───────────────────────────────────────────────────────────
    {
        "name": "Аня Ершова",
        "experience": 10,
        "level": "top",
        "categories": ["nails"],
        "tags": ["маникюр", "педикюр", "гель-лак", "дизайн", "наращивание"],
        "bio": "Топ-мастер ногтевого сервиса. Маникюр, педикюр, сложный дизайн.",
        "photo_url": "data/photos/anna_ershova.jpg",
        "photo_id": None,
    },
    {
        "name": "Нина",
        "experience": 10,
        "level": "experienced",
        "categories": ["nails"],
        "tags": ["педикюр", "подология", "маникюр", "аппаратный маникюр", "гель-лак"],
        "bio": "Подолог. Медицинский педикюр и уход за проблемными ногтями.",
        "photo_url": "data/photos/nina.jpg",
        "photo_id": None,
    },
    {
        "name": "Таранкова Виктория",
        "experience": 10,
        "level": "experienced",
        "categories": ["nails"],
        "tags": ["наращивание", "маникюр", "гель-лак", "акрил", "дизайн"],
        "bio": "Наращивание ногтей, маникюр с гель-лаком.",
        "photo_url": "data/photos/viktoriya.jpg",
        "photo_id": None,
    },

    # ── КОСМЕТОЛОГИЯ ────────────────────────────────────────────────────
    {
        "name": "Светлана",
        "experience": 7,
        "level": "experienced",
        "categories": ["cosmetology"],
        "tags": ["уход", "пилинг", "чистка", "косметология", "омоложение", "лазер"],
        "bio": "Профессиональные уходы, пилинги, лазерная эпиляция.",
        "photo_url": "data/photos/svetlana_levashova.png",
        "photo_id": None,
    },
]


def recommend(category: str, desire_tag: str, experience_pref: str) -> list[dict]:
    """Возвращает до 3 мастеров по скорингу."""
    level_scores = {"any": 1, "experienced": 2, "top": 3}
    pref_score = level_scores.get(experience_pref, 0)

    scored = []
    for m in MASTERS:
        if category not in m["categories"]:
            continue

        score = 0
        # Совпадение по тегу желания
        if desire_tag and any(desire_tag.lower() in t.lower() for t in m["tags"]):
            score += 3
        # Совпадение по уровню опыта
        m_level = level_scores.get(m["level"], 0)
        score += max(0, 3 - abs(m_level - pref_score))
        # Бонус за большой опыт
        score += min(m["experience"] // 5, 2)

        scored.append((score, m))

    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:3]]
