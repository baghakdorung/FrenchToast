"""+움짤 : 이미지를 GIF 로 변환해 사용자 프로필/닉네임과 함께 임베드로 출력."""

from __future__ import annotations

import asyncio
import io
import re

import aiohttp
import discord
from discord.ext import commands
from PIL import Image, ImageSequence, UnidentifiedImageError

MAX_DOWNLOAD = 25 * 1024 * 1024        # 원본 최대 25MB
MAX_FRAMES = 300                        # 너무 긴 애니메이션 방지
SIZE_STEPS = (512, 400, 320, 240, 160)  # 용량 초과 시 점점 줄여서 재시도
URL_RE = re.compile(r"^<?(https?://\S+?)>?$")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".apng")


class ConvertError(Exception):
    pass


def _load_frames(data: bytes) -> tuple[list[Image.Image], list[int]]:
    try:
        src = Image.open(io.BytesIO(data))
    except UnidentifiedImageError as e:
        raise ConvertError("이미지 파일이 아니거나 지원하지 않는 형식이에요.") from e

    frames: list[Image.Image] = []
    durations: list[int] = []
    default_dur = src.info.get("duration") or 100
    for frame in ImageSequence.Iterator(src):
        frames.append(frame.convert("RGBA"))
        durations.append(int(frame.info.get("duration") or default_dur))
        if len(frames) >= MAX_FRAMES:
            break
    if not frames:
        raise ConvertError("이미지에서 프레임을 읽지 못했어요.")
    # 너무 빠른 프레임(0~10ms)은 브라우저/디스코드에서 느리게 재생되므로 보정
    durations = [d if d >= 20 else 100 for d in durations]
    return frames, durations


def _encode(frames: list[Image.Image], durations: list[int], max_side: int, step: int) -> bytes:
    picked = frames[::step]
    picked_dur = [sum(durations[i:i + step]) for i in range(0, len(durations), step)]
    resized = []
    for f in picked:
        f = f.copy()
        f.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        resized.append(f)
    buf = io.BytesIO()
    resized[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=resized[1:],
        duration=picked_dur if len(resized) > 1 else picked_dur[0],
        loop=0,
        disposal=2,
        optimize=True,
    )
    return buf.getvalue()


def convert_to_gif(data: bytes, size_limit: int) -> tuple[bytes, int, int]:
    """(gif 바이트, 프레임 수, 최대 변 길이) 반환. 용량 제한을 맞출 때까지 크기/프레임을 줄인다."""
    frames, durations = _load_frames(data)
    for step in (1, 2, 3):
        for side in SIZE_STEPS:
            out = _encode(frames, durations, side, step)
            if len(out) <= size_limit:
                return out, len(frames[::step]), side
    raise ConvertError("변환된 GIF 가 디스코드 업로드 용량을 초과해요. 더 짧거나 작은 이미지를 써주세요.")


class Gif(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    async def cog_unload(self) -> None:
        if self.session:
            await self.session.close()

    async def _download(self, url: str) -> bytes:
        assert self.session
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    raise ConvertError(f"이미지를 받아오지 못했어요. (HTTP {resp.status})")
                if (resp.content_length or 0) > MAX_DOWNLOAD:
                    raise ConvertError("이미지가 너무 커요. (최대 25MB)")
                data = bytearray()
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    data.extend(chunk)
                    if len(data) > MAX_DOWNLOAD:
                        raise ConvertError("이미지가 너무 커요. (최대 25MB)")
                return bytes(data)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise ConvertError("이미지 다운로드 중 오류가 발생했어요.") from e

    @staticmethod
    def _image_from_message(msg: discord.Message) -> str | None:
        for att in msg.attachments:
            if (att.content_type or "").startswith("image/") or att.filename.lower().endswith(IMAGE_EXTS):
                return att.url
        for emb in msg.embeds:
            if emb.image and emb.image.url:
                return emb.image.url
            if emb.thumbnail and emb.thumbnail.url:
                return emb.thumbnail.url
        return None

    async def _find_source(self, ctx: commands.Context, args: str) -> tuple[str | None, str]:
        """(이미지 URL, 캡션) 반환. 우선순위: 첨부파일 → 인자 URL → 커스텀 이모지 → 답장한 메시지."""
        caption_parts: list[str] = []
        url: str | None = self._image_from_message(ctx.message) if ctx.message.attachments else None

        for token in args.split():
            m = URL_RE.match(token)
            if m and url is None:
                url = m.group(1)
                continue
            if url is None:
                try:
                    emoji = await commands.PartialEmojiConverter().convert(ctx, token)
                    url = emoji.url
                    continue
                except commands.BadArgument:
                    pass
            caption_parts.append(token)

        if url is None and ctx.message.reference and ctx.message.reference.message_id:
            ref = ctx.message.reference.resolved
            if not isinstance(ref, discord.Message):
                try:
                    ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                except discord.HTTPException:
                    ref = None
            if isinstance(ref, discord.Message):
                url = self._image_from_message(ref)

        return url, " ".join(caption_parts)

    @commands.command(name="움짤", aliases=["gif", "짤"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def make_gif(self, ctx: commands.Context, *, args: str = ""):
        """+움짤 [이미지 첨부 | 이미지 URL | 커스텀 이모지 | 이미지에 답장] [캡션]"""
        url, caption = await self._find_source(ctx, args)
        if not url:
            await ctx.reply(
                "🖼️ 이미지를 같이 보내주세요!\n"
                "• `+움짤` + 이미지 첨부\n• `+움짤 <이미지 URL>`\n"
                "• `+움짤 :커스텀이모지:`\n• 이미지 메시지에 답장하며 `+움짤`",
                mention_author=False,
            )
            return

        size_limit = (ctx.guild.filesize_limit if ctx.guild else 10 * 1024 * 1024) - 256 * 1024

        async with ctx.typing():
            try:
                data = await self._download(url)
                gif_bytes, frame_count, side = await asyncio.to_thread(convert_to_gif, data, size_limit)
            except ConvertError as e:
                await ctx.reply(f"❌ {e}", mention_author=False)
                return

        author = ctx.author
        embed = discord.Embed(description=caption or None, color=self.bot.embed_color)
        embed.set_image(url="attachment://frenchtoast.gif")
        # 푸터는 이미지 아래에 표시됨 → 프로필 사진 + 닉네임
        embed.set_footer(text=author.display_name, icon_url=author.display_avatar.url)

        file = discord.File(io.BytesIO(gif_bytes), filename="frenchtoast.gif")
        await ctx.send(embed=embed, file=file)

        # 원본 명령 메시지 정리 (메시지 관리 권한이 있을 때만)
        if ctx.guild and ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gif(bot))
