"""Render 무료 Web Service 용 HTTP 서버.

Render Web Service 는 포트를 열어야 정상 배포로 인식하며,
무료 플랜은 15분간 HTTP 요청이 없으면 슬립합니다.
UptimeRobot 등으로 /health 를 5분마다 호출하면 24시간 깨어 있게 할 수 있습니다.
"""

from __future__ import annotations

import logging
import os

from aiohttp import web

log = logging.getLogger("frenchtoast.web")


async def start_web_server(bot) -> web.AppRunner:
    async def index(_: web.Request) -> web.Response:
        return web.Response(text="FrenchToast is alive 🍞")

    async def health(_: web.Request) -> web.Response:
        ready = bot.is_ready()
        return web.json_response(
            {"status": "ok" if ready else "starting", "guilds": len(bot.guilds) if ready else 0}
        )

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_route("HEAD", "/", index)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("웹 서버 시작: 0.0.0.0:%d", port)
    return runner
