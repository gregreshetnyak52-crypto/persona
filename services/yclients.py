import asyncio
import logging
import os
import ssl
import time
import aiohttp
import certifi
from config import (
    YCLIENTS_PARTNER_TOKEN,
    YCLIENTS_USER_TOKEN,
    YCLIENTS_COMPANY_ID,
)

log = logging.getLogger(__name__)

BASE = "https://api.yclients.com/api/v1"
BOOK_BASE = "https://api.yclients.com/api/v1"

_cache: dict[str, tuple[float, object]] = {}
CACHE_TTL = 3600  # 1 hour

# ── Singleton HTTP-сессия ──────────────────────────────────────────────────────

_session: aiohttp.ClientSession | None = None


def get_session() -> aiohttp.ClientSession:
    """Возвращает единственную сессию приложения, создаёт при необходимости."""
    global _session
    if _session is None or _session.closed:
        # certifi вместо системного доверенного хранилища: на некоторых
        # установках Python (например, python.org на macOS) системные
        # корневые сертификаты не подхвачены, и TLS-запросы падают с
        # SSLCertVerificationError.
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            connector=aiohttp.TCPConnector(ssl=ssl_context),
        )
    return _session


async def close_session() -> None:
    """Закрыть сессию при завершении бота (вызывается из post_shutdown)."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


# ── Retry-хелпер ──────────────────────────────────────────────────────────────

async def _request(method: str, url: str, **kwargs) -> dict:
    """
    Выполнить HTTP-запрос с 3 попытками и экспоненциальным backoff.
    Ретраит на: сетевые ошибки, таймауты, HTTP 5xx.
    Не ретраит на HTTP 4xx (логические ошибки).
    """
    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(3):
        try:
            async with get_session().request(method, url, **kwargs) as resp:
                if resp.status in (401, 403):
                    log.critical(
                        "YClients auth error HTTP %s — проверь YCLIENTS_PARTNER_TOKEN / YCLIENTS_USER_TOKEN!",
                        resp.status,
                    )
                    raise RuntimeError(f"YClients auth error {resp.status}")
                if resp.status == 429:
                    log.warning("YClients rate limit (429), ждём 10с... (попытка %d)", attempt + 1)
                    await asyncio.sleep(10)
                    continue
                if resp.status < 500:
                    if resp.status >= 400:
                        body = await resp.text()
                        log.error(
                            "YClients HTTP %s для %s %s: %s",
                            resp.status, method, url, body,
                        )
                    resp.raise_for_status()
                    return await resp.json()
                # HTTP 5xx — сервер временно недоступен, пробуем ещё
                log.warning("YClients HTTP %s, retry %d/3 (%s)", resp.status, attempt + 1, url)
                last_exc = aiohttp.ClientResponseError(
                    resp.request_info, resp.history, status=resp.status
                )
        except RuntimeError:
            raise  # auth-ошибки пробрасываем сразу без retry
        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
            log.warning("YClients connection error, retry %d/3: %s", attempt + 1, e)
            last_exc = e
        if attempt < 2:
            await asyncio.sleep(2 ** attempt)  # 1s, 2s
    raise RuntimeError(f"YClients недоступен после 3 попыток ({url}): {last_exc}")


# ── Кеш ───────────────────────────────────────────────────────────────────────

def _cached(key: str) -> object | None:
    entry = _cache.get(key)
    if entry and time.monotonic() - entry[0] < CACHE_TTL:
        return entry[1]
    return None


def _set_cache(key: str, value: object) -> None:
    _cache[key] = (time.monotonic(), value)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {YCLIENTS_PARTNER_TOKEN}, User {YCLIENTS_USER_TOKEN}",
        "Accept": "application/vnd.yclients.v2+json",
        "Content-Type": "application/json",
    }


# ── API-функции ────────────────────────────────────────────────────────────────

async def get_services(staff_id: int | None = None) -> list[dict]:
    cache_key = f"services_{staff_id}"
    cached = _cached(cache_key)
    if cached:
        log.debug("Cache hit: %s (%d услуг)", cache_key, len(cached))  # type: ignore
        return cached  # type: ignore

    params = {}
    if staff_id:
        params["staff_id"] = staff_id

    data = await _request(
        "GET",
        f"{BOOK_BASE}/book_services/{YCLIENTS_COMPANY_ID}",
        headers=_headers(),
        params=params,
    )
    services = data.get("data", {}).get("services", [])
    _set_cache(cache_key, services)
    log.info("get_services: загружено %d услуг (staff_id=%s)", len(services), staff_id)
    return services


async def get_staff(service_ids: list[int] | None = None) -> list[dict]:
    cache_key = f"staff_{'_'.join(map(str, service_ids)) if service_ids else 'all'}"
    cached = _cached(cache_key)
    if cached:
        log.debug("Cache hit: %s (%d мастеров)", cache_key, len(cached))  # type: ignore
        return cached  # type: ignore

    params = {}
    if service_ids:
        params["service_ids[]"] = service_ids

    data = await _request(
        "GET",
        f"{BOOK_BASE}/book_staff/{YCLIENTS_COMPANY_ID}",
        headers=_headers(),
        params=params,
    )
    staff = data.get("data", [])
    _set_cache(cache_key, staff)
    log.info("get_staff: загружено %d мастеров (service_ids=%s)", len(staff), service_ids)
    return staff


async def get_available_dates(staff_id: int, service_ids: list[int]) -> list[str]:
    params: dict = {"staff_id": staff_id}
    for sid in service_ids:
        params.setdefault("service_ids[]", []).append(sid)

    data = await _request(
        "GET",
        f"{BOOK_BASE}/book_dates/{YCLIENTS_COMPANY_ID}",
        headers=_headers(),
        params=params,
    )
    return data.get("data", {}).get("booking_dates", [])


async def get_available_times(staff_id: int, date: str, service_ids: list[int]) -> list[dict]:
    params: dict = {}
    for sid in service_ids:
        params.setdefault("service_ids[]", []).append(sid)

    data = await _request(
        "GET",
        f"{BOOK_BASE}/book_times/{YCLIENTS_COMPANY_ID}/{staff_id}/{date}",
        headers=_headers(),
        params=params,
    )
    return data.get("data", [])


async def create_booking(
    fullname: str,
    phone: str,
    staff_id: int,
    service_id: int,
    datetime_str: str,
    comment: str = "",
) -> dict:
    # YClients требует телефон с +
    phone_formatted = phone if phone.startswith("+") else f"+{phone}"
    payload = {
        "phone": phone_formatted,
        "fullname": fullname,
        "email": "",
        "appointments": [
            {
                "id": 1,
                "services": [int(service_id)],
                "staff_id": int(staff_id),
                "events": [],
                "datetime": datetime_str,
                "chargeStatus": "",
                "comment": comment,
            }
        ],
    }
    result = await _request(
        "POST",
        f"{BASE}/book_record/{YCLIENTS_COMPANY_ID}/",
        headers=_headers(),
        json=payload,
    )
    records = result.get("data", [])
    record_id = records[0].get("id") if records else None
    log.info(
        "create_booking: record_id=%s client=%s phone=%s datetime=%s",
        record_id, fullname, phone_formatted, datetime_str,
    )
    return result


async def get_records(date: str) -> list[dict]:
    params = {"start_date": date, "end_date": date, "count": 100}
    data = await _request(
        "GET",
        f"{BASE}/records/{YCLIENTS_COMPANY_ID}",
        headers=_headers(),
        params=params,
    )
    return data.get("data", [])


async def delete_record(record_id: int) -> bool:
    try:
        async with get_session().delete(
            f"{BASE}/record/{YCLIENTS_COMPANY_ID}/{record_id}",
            headers=_headers(),
        ) as resp:
            ok = resp.status in (200, 204)  # YClients отвечает 204 No Content на успешный DELETE
            if ok:
                log.info("delete_record: запись #%s успешно отменена", record_id)
            else:
                log.warning("delete_record: HTTP %s для record_id=%s", resp.status, record_id)
            return ok
    except Exception as e:
        log.error("delete_record(%s) failed: %s", record_id, e)
        return False
