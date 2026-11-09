"""+안드로어 / +역안드로어 : 한/영 자판 변환 (두벌식).

+안드로어 안녕   → dkssud   (한글을 영문 자판 입력으로)
+역안드로어 dkssud → 안녕   (영문 자판 입력을 한글로)
메시지에 답장하면서 명령어만 쓰면 그 메시지를 변환합니다.
"""

from __future__ import annotations

import discord
from discord.ext import commands

CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ",
        "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]

# 단일 자모 ↔ 키
JAMO_TO_KEY = {
    "ㄱ": "r", "ㄲ": "R", "ㄴ": "s", "ㄷ": "e", "ㄸ": "E", "ㄹ": "f", "ㅁ": "a", "ㅂ": "q", "ㅃ": "Q",
    "ㅅ": "t", "ㅆ": "T", "ㅇ": "d", "ㅈ": "w", "ㅉ": "W", "ㅊ": "c", "ㅋ": "z", "ㅌ": "x", "ㅍ": "v",
    "ㅎ": "g",
    "ㅏ": "k", "ㅐ": "o", "ㅑ": "i", "ㅒ": "O", "ㅓ": "j", "ㅔ": "p", "ㅕ": "u", "ㅖ": "P", "ㅗ": "h",
    "ㅛ": "y", "ㅜ": "n", "ㅠ": "b", "ㅡ": "m", "ㅣ": "l",
}
KEY_TO_JAMO = {v: k for k, v in JAMO_TO_KEY.items()}

# 겹자모 = 두 자모의 조합
COMPOUND = {
    "ㅘ": "ㅗㅏ", "ㅙ": "ㅗㅐ", "ㅚ": "ㅗㅣ", "ㅝ": "ㅜㅓ", "ㅞ": "ㅜㅔ", "ㅟ": "ㅜㅣ", "ㅢ": "ㅡㅣ",
    "ㄳ": "ㄱㅅ", "ㄵ": "ㄴㅈ", "ㄶ": "ㄴㅎ", "ㄺ": "ㄹㄱ", "ㄻ": "ㄹㅁ", "ㄼ": "ㄹㅂ", "ㄽ": "ㄹㅅ",
    "ㄾ": "ㄹㅌ", "ㄿ": "ㄹㅍ", "ㅀ": "ㄹㅎ", "ㅄ": "ㅂㅅ",
}
COMBINE = {v: k for k, v in COMPOUND.items()}
VOWELS = set(JUNG)


def _jamo_keys(j: str) -> str:
    return "".join(JAMO_TO_KEY[c] for c in COMPOUND.get(j, j))


def ko_to_en(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            cho, rest = divmod(code, 588)
            jung, jong = divmod(rest, 28)
            out.append(_jamo_keys(CHO[cho]) + _jamo_keys(JUNG[jung]) + (_jamo_keys(JONG[jong]) if jong else ""))
        elif ch in JAMO_TO_KEY or ch in COMPOUND:
            out.append(_jamo_keys(ch))
        else:
            out.append(ch)
    return "".join(out)


def en_to_ko(text: str) -> str:
    out: list[str] = []
    cho = jung = jong = ""

    def flush() -> None:
        nonlocal cho, jung, jong
        if cho and jung:
            out.append(chr(0xAC00 + (CHO.index(cho) * 21 + JUNG.index(jung)) * 28 + JONG.index(jong)))
        else:
            out.append(cho + jung)  # 미완성 글자는 자모 그대로
        cho = jung = jong = ""

    for ch in text:
        jamo = KEY_TO_JAMO.get(ch) or KEY_TO_JAMO.get(ch.lower())
        if jamo is None:
            flush()
            out.append(ch)
            continue

        if jamo in VOWELS:
            if jong:
                # 받침이 다음 글자 초성으로 넘어감 (겹받침이면 뒤쪽만)
                if jong in COMPOUND:
                    keep, move = COMPOUND[jong]
                    jong = keep
                else:
                    move, jong = jong, ""
                flush()
                cho, jung = move, jamo
            elif jung:
                if jung + jamo in COMBINE:
                    jung = COMBINE[jung + jamo]
                else:
                    flush()
                    jung = jamo
            else:
                jung = jamo
        else:  # 자음
            if cho and jung and not jong:
                if jamo in JONG:
                    jong = jamo
                else:  # ㄸ ㅃ ㅉ 는 받침 불가
                    flush()
                    cho = jamo
            elif jong:
                if jong + jamo in COMBINE:
                    jong = COMBINE[jong + jamo]
                else:
                    flush()
                    cho = jamo
            else:
                if cho or jung:
                    flush()
                cho = jamo
    flush()
    return "".join(out)


class HanYeong(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _source_text(self, ctx: commands.Context, text: str) -> str | None:
        if text.strip():
            return text
        ref = ctx.message.reference
        if ref and ref.message_id:
            msg = ref.resolved if isinstance(ref.resolved, discord.Message) else None
            if msg is None:
                try:
                    msg = await ctx.channel.fetch_message(ref.message_id)
                except discord.HTTPException:
                    return None
            return msg.content or None
        return None

    async def _reply(self, ctx: commands.Context, result: str) -> None:
        await ctx.reply(
            result[:2000] or "(빈 결과)",
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @commands.command(name="안드로어", aliases=["안"])
    async def to_english(self, ctx: commands.Context, *, text: str = ""):
        """+안드로어 안녕 → dkssud"""
        src = await self._source_text(ctx, text)
        if not src:
            await ctx.reply("사용법: `+안드로어 안녕` → `dkssud` (메시지에 답장하며 `+안드로어` 도 가능)", mention_author=False)
            return
        await self._reply(ctx, ko_to_en(src))

    @commands.command(name="역안드로어", aliases=["역안"])
    async def to_korean(self, ctx: commands.Context, *, text: str = ""):
        """+역안드로어 dkssud → 안녕"""
        src = await self._source_text(ctx, text)
        if not src:
            await ctx.reply("사용법: `+역안드로어 dkssud` → `안녕` (메시지에 답장하며 `+역안드로어` 도 가능)", mention_author=False)
            return
        await self._reply(ctx, en_to_ko(src))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HanYeong(bot))
