"""서버별 입장/퇴장 메시지 설정."""

from __future__ import annotations

import discord
from discord.ext import commands

PLACEHOLDER_HELP = (
    "`{user}` 멘션 · `{name}` 닉네임 · `{username}` 아이디 · "
    "`{server}` 서버 이름 · `{count}` 현재 인원 수"
)

DEFAULTS = {
    "welcome": "{user}님, **{server}**에 오신 걸 환영해요! 🍞 (현재 {count}명)",
    "leave": "**{name}**님이 서버를 떠났어요. 👋 (현재 {count}명)",
}

KIND_LABEL = {"welcome": "입장", "leave": "퇴장"}


def render(template: str, member: discord.Member) -> str:
    values = {
        "user": member.mention,
        "name": member.display_name,
        "username": member.name,
        "server": member.guild.name,
        "count": member.guild.member_count or len(member.guild.members),
    }
    # format_map 대신 replace 사용 → 사용자가 입력한 다른 중괄호로 오류가 나지 않음
    for key, val in values.items():
        template = template.replace("{" + key + "}", str(val))
    return template


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ---------- 내부 헬퍼 ----------

    async def _send(self, kind: str, member: discord.Member) -> bool:
        conf = await self.bot.storage.get(member.guild.id)
        channel_id = conf.get(f"{kind}_channel")
        if not channel_id:
            return False
        channel = member.guild.get_channel(channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return False
        text = render(conf.get(f"{kind}_message") or DEFAULTS[kind], member)
        try:
            await channel.send(
                text[:2000],
                allowed_mentions=discord.AllowedMentions(users=True, everyone=False, roles=False),
            )
            return True
        except discord.HTTPException:
            return False

    async def _set(
        self, ctx: commands.Context, kind: str, channel: discord.TextChannel, message: str | None
    ) -> None:
        perms = channel.permissions_for(ctx.guild.me)
        if not perms.send_messages:
            await ctx.reply(f"❌ {channel.mention} 채널에 메시지를 보낼 권한이 없어요.", mention_author=False)
            return
        fields = {f"{kind}_channel": channel.id}
        if message:
            fields[f"{kind}_message"] = message
        await self.bot.storage.update(ctx.guild.id, **fields)
        conf = await self.bot.storage.get(ctx.guild.id)
        preview = render(conf.get(f"{kind}_message") or DEFAULTS[kind], ctx.author)
        embed = discord.Embed(
            title=f"✅ {KIND_LABEL[kind]} 메시지 설정 완료",
            color=self.bot.embed_color,
        )
        embed.add_field(name="채널", value=channel.mention, inline=False)
        embed.add_field(name="미리보기", value=preview[:1024], inline=False)
        embed.set_footer(text=f"사용 가능한 치환자: {{user}} {{name}} {{username}} {{server}} {{count}}")
        await ctx.reply(embed=embed, mention_author=False)

    # ---------- 이벤트 ----------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self._send("welcome", member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self._send("leave", member)

    # ---------- 관리자 명령어 ----------

    @commands.command(name="입장설정", aliases=["welcome"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def set_welcome(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str | None = None):
        """+입장설정 #채널 [메시지]"""
        await self._set(ctx, "welcome", channel, message)

    @commands.command(name="퇴장설정", aliases=["leave"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def set_leave(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str | None = None):
        """+퇴장설정 #채널 [메시지]"""
        await self._set(ctx, "leave", channel, message)

    @commands.command(name="입장끄기", aliases=["welcomeoff"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def disable_welcome(self, ctx: commands.Context):
        await self.bot.storage.update(ctx.guild.id, welcome_channel=None)
        await ctx.reply("🔕 입장 메시지를 껐어요.", mention_author=False)

    @commands.command(name="퇴장끄기", aliases=["leaveoff"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def disable_leave(self, ctx: commands.Context):
        await self.bot.storage.update(ctx.guild.id, leave_channel=None)
        await ctx.reply("🔕 퇴장 메시지를 껐어요.", mention_author=False)

    @commands.command(name="입장테스트", aliases=["welcometest"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def test_welcome(self, ctx: commands.Context):
        if not await self._send("welcome", ctx.author):
            await ctx.reply("❌ 입장 메시지가 설정되지 않았거나 보낼 수 없어요. `+입장설정 #채널` 먼저 해주세요.", mention_author=False)

    @commands.command(name="퇴장테스트", aliases=["leavetest"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def test_leave(self, ctx: commands.Context):
        if not await self._send("leave", ctx.author):
            await ctx.reply("❌ 퇴장 메시지가 설정되지 않았거나 보낼 수 없어요. `+퇴장설정 #채널` 먼저 해주세요.", mention_author=False)

    @commands.command(name="설정확인", aliases=["settings"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def show_settings(self, ctx: commands.Context):
        conf = await self.bot.storage.get(ctx.guild.id)
        embed = discord.Embed(title=f"⚙️ {ctx.guild.name} 설정", color=self.bot.embed_color)
        for kind in ("welcome", "leave"):
            ch_id = conf.get(f"{kind}_channel")
            ch = ctx.guild.get_channel(ch_id) if ch_id else None
            status = ch.mention if ch else "꺼짐"
            msg = conf.get(f"{kind}_message") or f"(기본값) {DEFAULTS[kind]}"
            embed.add_field(
                name=f"{KIND_LABEL[kind]} 메시지",
                value=f"채널: {status}\n메시지: {msg}"[:1024],
                inline=False,
            )
        embed.add_field(name="치환자", value=PLACEHOLDER_HELP, inline=False)
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
