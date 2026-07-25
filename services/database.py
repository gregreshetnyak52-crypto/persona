import aiosqlite
from datetime import datetime, timedelta
from config import DB_PATH


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS admin_auth (
                user_id INTEGER PRIMARY KEY,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS booking_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                yclients_record_id INTEGER,
                master_name TEXT,
                service_name TEXT,
                appointment_datetime TEXT,
                client_name TEXT,
                client_phone TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                reminded INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS admin_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_id INTEGER,
                detail TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS admin_login_attempts (
                user_id INTEGER PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                locked_until TEXT
            );
        """)
        await db.commit()


async def is_admin_authed(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT expires_at FROM admin_auth WHERE user_id = ? AND expires_at > datetime('now')",
            (user_id,),
        ) as cursor:
            return await cursor.fetchone() is not None


async def set_admin_auth(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO admin_auth (user_id, expires_at) VALUES (?, datetime('now', '+24 hours'))",
            (user_id,),
        )
        await db.commit()


async def log_booking(
    user_id: int,
    yclients_record_id: int | None,
    master_name: str,
    service_name: str,
    appointment_datetime: str,
    client_name: str,
    client_phone: str,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO booking_log
               (user_id, yclients_record_id, master_name, service_name,
                appointment_datetime, client_name, client_phone)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, yclients_record_id, master_name, service_name,
             appointment_datetime, client_name, client_phone),
        )
        await db.commit()


async def get_unreminded_bookings() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM booking_log
               WHERE reminded = 0
                 AND appointment_datetime > datetime('now')
                 AND appointment_datetime <= datetime('now', '+25 hours')"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def mark_reminded(booking_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE booking_log SET reminded = 1 WHERE id = ?", (booking_id,))
        await db.commit()


async def get_user_upcoming_bookings(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM booking_log
               WHERE user_id = ?
                 AND appointment_datetime > datetime('now')
               ORDER BY appointment_datetime""",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_booking_by_record_id(yclients_record_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM booking_log WHERE yclients_record_id = ?",
            (yclients_record_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def cancel_booking_by_id(booking_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM booking_log WHERE id = ?", (booking_id,))
        await db.commit()


_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_MINUTES = 30


async def check_login_attempt(user_id: int) -> tuple[bool, int]:
    """Возвращает (разрешён_ли_вход, попыток_осталось).
    Блокирует на 30 минут после 5 неудачных попыток."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT attempts, locked_until FROM admin_login_attempts WHERE user_id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()

    if row is None:
        return True, _MAX_LOGIN_ATTEMPTS

    attempts, locked_until = row
    if locked_until:
        from datetime import datetime
        if datetime.fromisoformat(locked_until) > datetime.now():
            return False, 0

    remaining = _MAX_LOGIN_ATTEMPTS - attempts
    return remaining > 0, max(0, remaining)


async def record_failed_login(user_id: int) -> tuple[bool, int]:
    """Фиксирует неудачную попытку. Возвращает (заблокирован_ли, попыток_осталось)."""
    from datetime import datetime, timedelta
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT attempts FROM admin_login_attempts WHERE user_id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()

        attempts = (row[0] if row else 0) + 1
        locked_until = None
        if attempts >= _MAX_LOGIN_ATTEMPTS:
            locked_until = (datetime.now() + timedelta(minutes=_LOCKOUT_MINUTES)).isoformat()

        await db.execute(
            "INSERT OR REPLACE INTO admin_login_attempts (user_id, attempts, locked_until) "
            "VALUES (?, ?, ?)",
            (user_id, attempts, locked_until),
        )
        await db.commit()

    remaining = max(0, _MAX_LOGIN_ATTEMPTS - attempts)
    return locked_until is not None, remaining


async def reset_login_attempts(user_id: int) -> None:
    """Сбрасывает счётчик после успешного входа."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admin_login_attempts WHERE user_id = ?", (user_id,))
        await db.commit()


async def clear_admin_auth(user_id: int) -> None:
    """Удаляет сессию администратора (выход)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admin_auth WHERE user_id = ?", (user_id,))
        await db.commit()


async def search_bookings(query: str) -> list[dict]:
    """Поиск по client_name и client_phone в booking_log (регистронезависимо, последние 50)."""
    like = f"%{query}%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM booking_log
               WHERE client_name LIKE ? OR client_phone LIKE ?
               ORDER BY appointment_datetime DESC
               LIMIT 50""",
            (like, like),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def log_admin_action(admin_user_id: int, action: str, target_id: int | None = None, detail: str = "") -> None:
    """Аудит-лог действий администратора."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO admin_audit (admin_user_id, action, target_id, detail) VALUES (?, ?, ?, ?)",
            (admin_user_id, action, target_id, detail),
        )
        await db.commit()


async def get_stats() -> dict:
    """Статистика из booking_log для админ-панели."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM booking_log WHERE date(appointment_datetime) = date('now')"
        ) as cur:
            today_count = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM booking_log WHERE appointment_datetime >= datetime('now', '-7 days')"
        ) as cur:
            week_count = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM booking_log WHERE appointment_datetime >= datetime('now', '-30 days')"
        ) as cur:
            month_count = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT service_name, COUNT(*) cnt FROM booking_log "
            "GROUP BY service_name ORDER BY cnt DESC LIMIT 3"
        ) as cur:
            top_services = await cur.fetchall()
        async with db.execute(
            "SELECT master_name, COUNT(*) cnt FROM booking_log "
            "GROUP BY master_name ORDER BY cnt DESC LIMIT 3"
        ) as cur:
            top_masters = await cur.fetchall()
    return {
        "today": today_count,
        "week": week_count,
        "month": month_count,
        "top_services": top_services,
        "top_masters": top_masters,
    }


async def ping() -> bool:
    """Проверка доступности базы данных (SELECT 1)."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("SELECT 1")
        return True
    except Exception:
        return False
