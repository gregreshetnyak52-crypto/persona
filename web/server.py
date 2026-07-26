"""
Веб-сервер Mini App: отдаёт статику (webapp/, data/photos/) и JSON API (web/api.py).
Работает в том же asyncio-процессе, что и Telegram-бот (см. bot.py).
"""
import logging
import os

from aiohttp import web

from config import PORT
from web.api import routes as api_routes

log = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WEBAPP_DIR = os.path.join(_BASE_DIR, "webapp")
_PHOTOS_DIR = os.path.join(_BASE_DIR, "data", "photos")


async def _index(request: web.Request) -> web.FileResponse:
    # add_static не отдаёт index.html для корня директории автоматически —
    # без этого маршрута GET "/" возвращал бы 403.
    return web.FileResponse(os.path.join(_WEBAPP_DIR, "index.html"))


def create_web_app(ptb_app) -> web.Application:
    app = web.Application()
    app["ptb_app"] = ptb_app
    # Порядок важен: сначала /api/* и /healthz, потом статика — иначе catch-all
    # маршрут "/" может перехватить API-запросы раньше, чем до них дойдёт очередь.
    app.add_routes(api_routes)
    app.router.add_get("/", _index)
    app.router.add_static("/photos/", _PHOTOS_DIR, show_index=False, name="photos")
    app.router.add_static("/css/", os.path.join(_WEBAPP_DIR, "css"), show_index=False, name="css")
    app.router.add_static("/js/", os.path.join(_WEBAPP_DIR, "js"), show_index=False, name="js")
    return app


async def start_web_server(ptb_app) -> web.AppRunner:
    app = create_web_app(ptb_app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("Веб-сервер запущен на 0.0.0.0:%s", PORT)
    return runner
