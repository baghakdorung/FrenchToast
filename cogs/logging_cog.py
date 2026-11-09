"""메시지 로그: 서버 모든 채널의 메시지 작성/수정/삭제를 지정한 로그 채널에 기록."""

from __future__ import annotations

import discord
from discord.ext import commands

COLOR_SEND = discord.Color.blurple()
COLOR_EDIT = discord.Color.gold()
COLOR_DELETE = discord.Color.red()


def _clip(text: str | None, limit: int = 1024) -> str:
    if not text:
        return "*(내용 없음)*"
    return text if len(text) <= limit else text[: limit - 1] + "…"


class MessageLog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # guild_id -> log channel id (None = 꺼짐). 메시지마다 DB 를 읽지 않도록 캐시.
        self._cache: dict[int, int | None] = {}

    # ---------- 헬퍼 ----------

    async def _log_channel(self, guild: discord.Guild | None) -> discord.TextChannel | None:
        if guild is None:
            return None
        if guild.id not in self._cache:
            try:
                conf = await self.bot.storage.get(guild.id)
            except Exception:
                return None  # DB 오류 시 로그만 건너뜀 (캐시하지 않아 다음에 재시도)
            self._cache[guild.id] = conf.get("log_channel")
        ch_id = self._cache[guild.id]
        ch = guild.get_channel(ch_id) if ch_id else None
        return ch if isinstance(ch, discord.TextChannel) else None

    def _skip(self, message: discord.Message, log_ch: discord.TextChannel) -> bool:
        return message.author.bot or message.channel.id == log_ch.id

    @staticmethod
    def _base_embed(title: str, color: discord.Color, author: discord.abc.User | None) -> discord.Embed:
        embed = discord.Embed(title=title, color=color, timestamp=discord.utils.utcnow())
        if author:
            embed.set_author(name=f"{author.display_name} ({author.name})", icon_url=author.display_avatar.url)
            embed.set_footer(text=f"유저 ID: {author.id}")
        return embed

    @staticmethod
    def _attachments(message: discord.Message) -> str | None:
        if not message.attachments:
            return None
        return "\n".join(f"[{a.filename}]({a.url})" for a in message.attachments)[:1024]

    async def _send(self, log_ch: discord.TextChannel, embed: discord.Embed) -> None:
        try:
            await log_ch.send(embed=embed)
        except discord.HTTPException:
            pass

    # ---------- 이벤트 ----------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        log_ch = await self._log_channel(message.guild)
        if not log_ch or self._skip(message, log_ch):
            return
        embed = self._base_embed("💬 메시지 작성", COLOR_SEND, message.author)
        embed.description = _clip(message.content, 4000)
        embed.add_field(name="채널", value=f"{message.channel.mention} · [바로가기]({message.jump_url})", inline=False)
        if att := self._attachments(message):
            embed.add_field(name="첨부파일", value=att, inline=False)
        await self._send(log_ch, embed)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        log_ch = await self._log_channel(guild)
        if not log_ch:
            return
        after = payload.message
        before = payload.cached_message
        if after.author.bot or after.channel.id == log_ch.id:
            return
        if before is not None and before.content == after.content:
            return  # 임베드 미리보기 생성 등 내용 변화 없는 수정은 무시
        embed = self._base_embed("✏️ 메시지 수정", COLOR_EDIT, after.author)
        embed.add_field(
            name="수정 전",
            value=_clip(before.content) if before else "*(봇 재시작 이전 메시지라 알 수 없음)*",
            inline=False,
        )
        embed.add_field(name="수정 후", value=_clip(after.content), inline=False)
        embed.add_field(name="채널", value=f"<#{payload.channel_id}> · [바로가기]({after.jump_url})", inline=False)
        await self._send(log_ch, embed)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        log_ch = await self._log_channel(guild)
        if not log_ch or payload.channel_id == log_ch.id:
            return
        msg = payload.cached_message
        if msg is not None and msg.author.bot:
            return
        embed = self._base_embed("🗑️ 메시지 삭제", COLOR_DELETE, msg.author if msg else None)
        if msg:
            embed.description = _clip(msg.content, 4000)
            if att := self._attachments(msg):
                embed.add_field(name="첨부파일 (링크가 만료될 수 있음)", value=att, inline=False)
        else:
            embed.description = "*(봇 재시작 이전 메시지라 내용을 알 수 없음)*"
        embed.add_field(name="채널", value=f"<#{payload.channel_id}>", inline=False)
        await self._send(log_ch, embed)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent) -> None:
        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        log_ch = await self._log_channel(guild)
        if not log_ch or payload.channel_id == log_ch.id:
            return
        embed = self._base_embed(f"🧹 메시지 {len(payload.message_ids)}개 일괄 삭제", COLOR_DELETE, None)
        lines = [
            f"**{m.author.display_name}**: {m.content[:100] or '(내용 없음)'}"
            for m in sorted(payload.cached_messages, key=lambda m: m.created_at)
            if not m.author.bot
        ]
        embed.description = _clip("\n".join(lines) or "*(내용 알 수 없음)*", 4000)
        embed.add_field(name="채널", value=f"<#{payload.channel_id}>", inline=False)
        await self._send(log_ch, embed)

    # ---------- 명령어 ----------

    @commands.command(name="로그설정", aliases=["logset"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def set_log(self, ctx: commands.Context, channel: discord.TextChannel):
        """+로그설정 #채널"""
        perms = channel.permissions_for(ctx.guild.me)
        if not (perms.send_messages and perms.embed_links):
            await ctx.reply(f"❌ {channel.mention} 채널에 메시지/임베드를 보낼 권한이 없어요.", mention_author=False)
            return
        await self.bot.storage.update(ctx.guild.id, log_channel=channel.id)
        self._cache[ctx.guild.id] = channel.id
        await ctx.reply(
            f"📝 이제 모든 채널의 메시지 작성·수정·삭제를 {channel.mention} 에 기록해요.\n"
            "봇이 볼 수 없는 채널은 기록되지 않아요.",
            mention_author=False,
        )

    @commands.command(name="로그끄기", aliases=["logoff"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def disable_log(self, ctx: commands.Context):
        await self.bot.storage.update(ctx.guild.id, log_channel=None)
        self._cache[ctx.guild.id] = None
        await ctx.reply("🔕 메시지 로그를 껐어요.", mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MessageLog(bot))
