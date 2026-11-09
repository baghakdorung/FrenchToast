"""FrenchToast 디스코드 봇 진입점."""

from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from keep_alive import start_web_server
from utils.storage import create_storage

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("frenchtoast")

PREFIX = "+"
EMBED_COLOR = 0xE8A75D  # 프렌치토스트 색


class FrenchToast(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True          # 입장/퇴장 이벤트 (개발자 포털에서 활성화 필요)
        intents.message_content = True  # 접두사 명령어 (개발자 포털에서 활성화 필요)
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            max_messages=5000,  # 수정/삭제 로그용 메시지 캐시
            activity=discord.Game(name=f"{PREFIX}도움"),
        )
        self.storage = create_storage()
        self.embed_color = EMBED_COLOR
        self._web_runner = None

    async def setup_hook(self) -> None:
        self._web_runner = await start_web_server(self)
        for ext in ("cogs.welcome", "cogs.gif", "cogs.general", "cogs.moderation", "cogs.logging_cog", "cogs.hanyeong"):
            await self.load_extension(ext)
            log.info("확장 로드: %s", ext)

    async def on_ready(self) -> None:
        log.info("로그인 완료: %s (ID %s) / 서버 %d개", self.user, self.user.id, len(self.guilds))

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        error = getattr(error, "original", error)
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            msg = f"❌ 이 명령어를 쓸 권한이 없어요. (필요 권한: `{perms}`)"
        elif isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            msg = f"❌ 봇에게 권한이 없어요. (필요 권한: `{perms}`)"
        elif isinstance(error, commands.MemberNotFound):
            msg = "❌ 해당 멤버를 찾을 수 없어요."
        elif isinstance(error, discord.Forbidden):
            msg = "❌ 봇 권한이 부족해 처리할 수 없어요. 봇 역할 순서와 권한을 확인해 주세요."
        elif isinstance(error, commands.NoPrivateMessage):
            msg = "❌ 이 명령어는 서버에서만 쓸 수 있어요."
        elif isinstance(error, commands.MissingRequiredArgument):
            msg = f"❌ 빠진 값이 있어요: `{error.param.name}`\n`{PREFIX}도움` 으로 사용법을 확인하세요."
        elif isinstance(error, (commands.ChannelNotFound, commands.BadArgument)):
            msg = f"❌ 입력값이 올바르지 않아요: {error}"
        elif isinstance(error, commands.CommandOnCooldown):
            msg = f"⏳ 잠시 후 다시 시도해 주세요. ({error.retry_after:.1f}초)"
        elif type(error).__module__.startswith("pymongo"):
            log.error("DB 오류: %s", error)
            msg = "⚠️ 설정 저장소(MongoDB)에 연결하지 못했어요. 봇 관리자는 `MONGODB_URI` 를 확인해 주세요."
        else:
            log.exception("명령어 오류: %s", ctx.message.content, exc_info=error)
            msg = "⚠️ 처리 중 오류가 발생했어요."
        try:
            await ctx.reply(msg, mention_author=False)
        except discord.HTTPException:
            pass

    async def close(self) -> None:
        await self.storage.close()
        if self._web_runner:
            await self._web_runner.cleanup()
        await super().close()


async def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("환경변수 DISCORD_TOKEN 이 설정되지 않았습니다.")
    bot = FrenchToast()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
