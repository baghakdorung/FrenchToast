"""+타임아웃 / +타임아웃해제 (디스코드 기본 타임아웃 기능 사용 → 시간이 지나면 디스코드가 자동 해제)."""

from __future__ import annotations

import re
from datetime import timedelta

import discord
from discord.ext import commands

MAX_TIMEOUT = timedelta(days=28)  # 디스코드 제한
UNITS = {
    "초": 1, "s": 1, "sec": 1,
    "분": 60, "m": 60, "min": 60,
    "시간": 3600, "h": 3600, "hr": 3600,
    "일": 86400, "d": 86400, "day": 86400,
}
TOKEN_RE = re.compile(r"(\d+)\s*(초|분|시간|일|sec|min|hr|day|s|m|h|d)", re.IGNORECASE)


def parse_duration(text: str) -> timedelta | None:
    """'30초', '10분', '2시간', '3일', '1시간30분', '1h30m' → timedelta. 형식이 틀리면 None."""
    compact = text.replace(" ", "").lower()
    if not compact:
        return None
    total, pos = 0, 0
    for m in TOKEN_RE.finditer(compact):
        if m.start() != pos:
            return None
        total += int(m.group(1)) * UNITS[m.group(2)]
        pos = m.end()
    if pos != len(compact) or total <= 0:
        return None
    return timedelta(seconds=total)


def format_duration(td: timedelta) -> str:
    secs = int(td.total_seconds())
    parts = []
    for label, size in (("일", 86400), ("시간", 3600), ("분", 60), ("초", 1)):
        if secs >= size:
            parts.append(f"{secs // size}{label}")
            secs %= size
    return " ".join(parts)


class DurationConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> timedelta:
        td = parse_duration(argument)
        if td is None:
            raise commands.BadArgument("시간 형식은 `30초` `10분` `2시간` `3일` `1시간30분` 처럼 입력해 주세요.")
        if td > MAX_TIMEOUT:
            raise commands.BadArgument("타임아웃은 최대 28일까지 가능해요.")
        return td


USAGE = "사용법: `+탐아 @유저 10분 [사유]` (닉네임에 띄어쓰기가 있어도 돼요: `+탐아 ts pig 47초`)"


async def resolve_member(ctx: commands.Context, text: str) -> discord.Member | None:
    """멘션/ID/이름/닉네임(띄어쓰기 포함, 대소문자 무시)으로 멤버 찾기."""
    text = text.strip().strip('"').strip()
    if not text:
        return None
    try:
        return await commands.MemberConverter().convert(ctx, text)
    except commands.BadArgument:
        pass
    low = text.lower()
    matches = [
        m for m in ctx.guild.members
        if low in {(m.nick or "").lower(), (m.global_name or "").lower(), m.name.lower(), m.display_name.lower()}
    ]
    return matches[0] if len(matches) == 1 else None


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _parse_timeout_args(
        self, ctx: commands.Context, args: str
    ) -> tuple[discord.Member, timedelta, str | None]:
        """'<멤버(띄어쓰기 가능)> <시간> [사유]' 해석. 시간처럼 보이는 첫 위치에서 멤버를 찾는다."""
        tokens = args.split()
        for i in range(1, len(tokens)):
            if parse_duration(tokens[i]) is None:
                continue
            member = await resolve_member(ctx, " ".join(tokens[:i]))
            if member is None:
                continue
            j = i
            while j < len(tokens) and parse_duration(tokens[j]) is not None:
                j += 1  # '1시간 30분' 처럼 띄어 쓴 시간도 합침
            duration = parse_duration("".join(tokens[i:j]))
            if duration > MAX_TIMEOUT:
                raise commands.BadArgument("타임아웃은 최대 28일까지 가능해요.")
            return member, duration, " ".join(tokens[j:]) or None
        if not any(parse_duration(t) for t in tokens[1:]):
            raise commands.BadArgument(f"시간을 찾지 못했어요. `30초` `10분` `2시간` `3일` 처럼 입력해 주세요.\n{USAGE}")
        raise commands.BadArgument(f"해당 멤버를 찾을 수 없어요. 멘션(@)으로 지정하면 가장 정확해요.\n{USAGE}")

    def _check_target(self, ctx: commands.Context, member: discord.Member) -> str | None:
        me = ctx.guild.me
        if member == ctx.author:
            return "자기 자신은 타임아웃할 수 없어요."
        if member == me:
            return "저는 타임아웃할 수 없어요. 🍞"
        if member == ctx.guild.owner or member.guild_permissions.administrator:
            return "서버 주인이나 관리자는 타임아웃할 수 없어요."
        if ctx.author != ctx.guild.owner and member.top_role >= ctx.author.top_role:
            return "나보다 역할이 같거나 높은 멤버는 타임아웃할 수 없어요."
        if member.top_role >= me.top_role:
            return "봇 역할이 대상보다 낮아요. 서버 설정에서 봇 역할을 더 위로 올려주세요."
        return None

    @commands.command(name="타임아웃", aliases=["탐아", "timeout", "뮤트"])
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def timeout(self, ctx: commands.Context, *, args: str = ""):
        """+타임아웃 @유저 10분 [사유]"""
        member, duration, reason = await self._parse_timeout_args(ctx, args)
        if err := self._check_target(ctx, member):
            await ctx.reply(f"❌ {err}", mention_author=False)
            return
        audit_reason = f"{ctx.author} : {reason or '사유 없음'}"
        await member.timeout(duration, reason=audit_reason)
        until = discord.utils.utcnow() + duration
        msg = (
            f"⏱️ {member.mention}님을 **{format_duration(duration)}** 동안 타임아웃했어요.\n"
            f"해제 예정: {discord.utils.format_dt(until, 'F')} ({discord.utils.format_dt(until, 'R')})"
        )
        if reason:
            msg += f"\n사유: {reason}"
        await ctx.reply(msg, mention_author=False, allowed_mentions=discord.AllowedMentions(users=False))

    @commands.command(name="타임아웃해제", aliases=["탐아해제", "untimeout", "언뮤트"])
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def untimeout(self, ctx: commands.Context, *, args: str = ""):
        """+타임아웃해제 @유저 [사유]"""
        tokens = args.split()
        member, reason = None, None
        for i in range(len(tokens), 0, -1):  # 가장 긴 이름부터 시도, 나머지는 사유
            member = await resolve_member(ctx, " ".join(tokens[:i]))
            if member:
                reason = " ".join(tokens[i:]) or None
                break
        if member is None:
            raise commands.BadArgument("해당 멤버를 찾을 수 없어요. 사용법: `+탐아해제 @유저` 또는 `+탐아해제 닉네임`")
        if not member.is_timed_out():
            await ctx.reply(f"ℹ️ {member.display_name}님은 타임아웃 상태가 아니에요.", mention_author=False)
            return
        if member.top_role >= ctx.guild.me.top_role:
            await ctx.reply("❌ 봇 역할이 대상보다 낮아서 해제할 수 없어요.", mention_author=False)
            return
        await member.timeout(None, reason=f"{ctx.author} : {reason or '수동 해제'}")
        await ctx.reply(
            f"✅ {member.mention}님의 타임아웃을 해제했어요.",
            mention_author=False,
            allowed_mentions=discord.AllowedMentions(users=False),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
