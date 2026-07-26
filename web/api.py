"""
JSON API для Telegram Mini App (webapp/). Переиспользует ту же бизнес-логику,
что и текстовый флоу записи в handlers/booking.py — никакой YClients-логики
здесь заново не пишется.
"""
import logging

from aiohttp import web
from telegram.helpers import escape_markdown

from config import ADMIN_TELEGRAM_IDS, WEBAPP_DEV_MODE, BUSINESS_PHONE_LINK
from services import yclients
from services.catalog import CATEGORIES, filter_services_by_category, find_master_profile, master_photo_web_url
from services.database import log_booking
from services.telegram_auth import validate_init_data
from services.validators import is_valid_name, normalize_ru_phone

log = logging.getLogger(__name__)
routes = web.RouteTableDef()


@routes.get("/healthz")
async def healthz(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


@routes.get("/api/categories")
async def api_categories(request: web.Request) -> web.Response:
    return web.json_response(CATEGORIES)


@routes.get("/api/services")
async def api_services(request: web.Request) -> web.Response:
    category = request.query.get("category", "")
    try:
        all_services = await yclients.get_services()
    except Exception as e:
        log.error("api_services: get_services error: %s", e)
        return web.json_response({"error": "yclients_unavailable"}, status=502)

    services = filter_services_by_category(all_services, category) if category else all_services
    return web.json_response([
        {"id": s["id"], "title": s.get("title", ""), "price_min": s.get("price_min")}
        for s in services
    ])


@routes.get("/api/masters")
async def api_masters(request: web.Request) -> web.Response:
    service_id = request.query.get("service_id")
    service_ids = [int(service_id)] if service_id else None
    try:
        staff = await yclients.get_staff(service_ids)
    except Exception as e:
        log.error("api_masters: get_staff error: %s", e)
        return web.json_response({"error": "yclients_unavailable"}, status=502)

    result = []
    for s in staff:
        profile = find_master_profile(s.get("name", ""))
        result.append({
            "id": s["id"],
            "name": s.get("name", ""),
            "bio": profile["bio"] if profile else "",
            "experience": profile["experience"] if profile else None,
            "photo_url": master_photo_web_url(profile["photo_url"]) if profile else None,
        })
    return web.json_response(result)


@routes.get("/api/dates")
async def api_dates(request: web.Request) -> web.Response:
    try:
        staff_id = int(request.query["staff_id"])
        service_id = int(request.query["service_id"])
    except (KeyError, ValueError):
        return web.json_response({"error": "bad_request"}, status=400)

    try:
        dates = await yclients.get_available_dates(staff_id, [service_id])
    except Exception as e:
        log.error("api_dates error: %s", e)
        return web.json_response({"error": "yclients_unavailable"}, status=502)
    return web.json_response(dates)


@routes.get("/api/times")
async def api_times(request: web.Request) -> web.Response:
    try:
        staff_id = int(request.query["staff_id"])
        service_id = int(request.query["service_id"])
        date = request.query["date"]
    except (KeyError, ValueError):
        return web.json_response({"error": "bad_request"}, status=400)

    try:
        slots = await yclients.get_available_times(staff_id, date, [service_id])
    except Exception as e:
        log.error("api_times error: %s", e)
        return web.json_response({"error": "yclients_unavailable"}, status=502)
    return web.json_response(slots)


@routes.post("/api/booking")
async def api_booking(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"success": False, "message": "Некорректный запрос"}, status=400)

    user = validate_init_data(body.get("init_data", ""))
    if user is None:
        if WEBAPP_DEV_MODE:
            log.warning("WEBAPP_DEV_MODE=true — принимаю запись БЕЗ проверки initData!")
            user = {"id": int(body.get("dev_user_id", 0) or 0)}
        else:
            return web.json_response(
                {"success": False, "message": "Не удалось подтвердить пользователя Telegram"}, status=401
            )

    telegram_user_id = user.get("id")
    if not telegram_user_id:
        return web.json_response({"success": False, "message": "Не удалось определить пользователя"}, status=401)

    client_name = (body.get("client_name") or "").strip()
    if not is_valid_name(client_name):
        return web.json_response(
            {"success": False, "message": "Введите имя буквами (например: Анна)"}, status=400
        )

    phone = normalize_ru_phone(body.get("client_phone") or "")
    if not phone:
        return web.json_response(
            {"success": False, "message": "Не удалось распознать номер телефона"}, status=400
        )

    try:
        staff_id = int(body["staff_id"])
        service_id = int(body["service_id"])
        datetime_str = body["datetime"]
        service_name = body.get("service_name", "")
        master_name = body.get("master_name", "")
    except (KeyError, ValueError, TypeError):
        return web.json_response({"success": False, "message": "Некорректные данные записи"}, status=400)

    ptb_app = request.app["ptb_app"]

    success = False
    record_id = None
    try:
        result = await yclients.create_booking(
            fullname=client_name,
            phone=phone,
            staff_id=staff_id,
            service_id=service_id,
            datetime_str=datetime_str,
        )
        success = result.get("success", False)
        if success:
            records = result.get("data", [])
            if not records or not records[0].get("id"):
                log.error("api_booking: success=True но data пустой или без id: %s", result)
                success = False
            else:
                record_id = records[0]["id"]
        else:
            log.error(
                "api_booking: YClients вернул success=False. meta=%s data=%s",
                result.get("meta"), result.get("data"),
            )
    except Exception as e:
        log.error("api_booking: create_booking error: %s", e)
        success = False

    date_display = datetime_str[:10] if datetime_str else "?"
    time_display = datetime_str[11:16] if len(datetime_str) >= 16 else "?"

    if success:
        await log_booking(
            user_id=telegram_user_id,
            yclients_record_id=record_id,
            master_name=master_name,
            service_name=service_name,
            appointment_datetime=datetime_str,
            client_name=client_name,
            client_phone=phone,
        )
        try:
            await ptb_app.bot.send_message(
                telegram_user_id,
                f"✅ *Запись подтверждена!*\n\n"
                f"📅 {date_display} в {time_display}\n"
                f"👤 Мастер: {escape_markdown(master_name, version=1)}\n"
                f"💅 Услуга: {escape_markdown(service_name, version=1)}\n\n"
                f"Ждём вас! Если понадобится перенести — позвоните:\n"
                f"📞 {BUSINESS_PHONE_LINK}",
                parse_mode="Markdown",
            )
        except Exception as e:
            log.warning("api_booking: не удалось отправить подтверждение клиенту: %s", e)

        admin_text = (
            f"🔔 *Новая запись (Mini App)!*\n"
            f"👤 {client_name} / +{phone}\n"
            f"💅 {escape_markdown(service_name, version=1)}\n"
            f"✂️ Мастер: {escape_markdown(master_name, version=1)}\n"
            f"📅 {date_display} в {time_display}"
        )
        for admin_id in ADMIN_TELEGRAM_IDS:
            try:
                await ptb_app.bot.send_message(admin_id, admin_text, parse_mode="Markdown")
            except Exception:
                pass

        return web.json_response({"success": True})

    try:
        await ptb_app.bot.send_message(
            telegram_user_id,
            f"❌ Не удалось создать запись онлайн.\n\n"
            f"Позвоните нам напрямую:\n📞 {BUSINESS_PHONE_LINK}\n"
            f"Ежедневно 10:00–22:00",
            parse_mode="Markdown",
        )
    except Exception:
        pass
    return web.json_response({"success": False, "message": "Не удалось создать запись, позвоните нам напрямую"})
