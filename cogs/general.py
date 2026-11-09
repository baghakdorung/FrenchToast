"""도움말 / 핑."""

from __future__ import annotations

import discord
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="도움", aliases=["help"])
    async def help(self, ctx: commands.Context):
        p = self.bot.command_prefix
        embed = discord.Embed(
            title="🍞 FrenchToast 도움",
            description=f"접두사: `{p}`",
            color=self.bot.embed_color,
        )
        embed.add_field(
            name="🎞️ 움짤",
            value=(
                f"`{p}움짤` + 이미지 첨부 / 이미지 URL / 커스텀 이모지 / 이미지에 답장\n"
                f"뒤에 글을 붙이면 캡션으로 표시돼요. 예) `{p}움짤 오늘 점심`"
            ),
            inline=False,
        )
        embed.add_field(
            name="👋 입장·퇴장 (서버 관리 권한 필요)",
            value=(
                f"`{p}입장설정 #채널 [메시지]` · `{p}퇴장설정 #채널 [메시지]`\n"
                f"`{p}입장끄기` · `{p}퇴장끄기`\n"
                f"`{p}입장테스트` · `{p}퇴장테스트` · `{p}설정확인`\n"
                "치환자: `{user}` `{name}` `{username}` `{server}` `{count}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="⏱️ 타임아웃 (멤버 타임아웃 권한 필요)",
            value=(
                f"`{p}타임아웃`(`{p}탐아`) `@유저 <시간> [사유]` · `{p}타임아웃해제`(`{p}탐아해제`) `@유저`\n"
                "시간: `30초` `10분` `2시간` `3일` `1시간30분` (최대 28일), 끝나면 자동으로 풀려요."
            ),
            inline=False,
        )
        embed.add_field(
            name="📝 메시지 로그 (서버 관리 권한 필요)",
            value=f"`{p}로그설정 #채널` · `{p}로그끄기`\n모든 채널의 메시지 작성·수정·삭제를 기록해요.",
            inline=False,
        )
        embed.add_field(
            name="⌨️ 한/영 변환",
            value=f"`{p}안드로어 dkssud` → 안녕 (`{p}안`) · `{p}역안드로어 안녕` → dkssud (`{p}역안`)\n메시지에 답장하며 쓰면 그 메시지를 변환해요.",
            inline=False,
        )
        embed.add_field(name="기타", value=f"`{p}핑` · `{p}도움`", inline=False)
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="핑", aliases=["ping"])
    async def ping(self, ctx: commands.Context):
        await ctx.reply(f"🏓 퐁! `{self.bot.latency * 1000:.0f}ms`", mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
