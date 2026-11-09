"""서버별 설정 저장소.

- 환경변수 MONGODB_URI 가 있으면 MongoDB(Atlas 무료 티어 권장)에 저장합니다.
- 없으면 로컬 JSON 파일(data/guilds.json)에 저장합니다.

Render 무료 플랜은 디스크가 휘발성이라 재시작/재배포 시 JSON 파일이 초기화됩니다.
배포 환경에서는 반드시 MONGODB_URI 를 설정하세요.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("frenchtoast.storage")


class GuildStorage:
    async def get(self, guild_id: int) -> dict[str, Any]:
        raise NotImplementedError

    async def update(self, guild_id: int, **fields: Any) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        pass


class JsonStorage(GuildStorage):
    def __init__(self, path: str | Path = "data/guilds.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        try:
            self._data: dict[str, dict[str, Any]] = json.loads(self.path.read_text("utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

    async def get(self, guild_id: int) -> dict[str, Any]:
        return dict(self._data.get(str(guild_id), {}))

    async def update(self, guild_id: int, **fields: Any) -> None:
        async with self._lock:
            self._data.setdefault(str(guild_id), {}).update(fields)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), "utf-8")
            tmp.replace(self.path)


class MongoStorage(GuildStorage):
    def __init__(self, uri: str, db_name: str = "frenchtoast") -> None:
        from motor.motor_asyncio import AsyncIOMotorClient

        self._client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=8000)
        self._col = self._client[db_name]["guilds"]

    async def get(self, guild_id: int) -> dict[str, Any]:
        doc = await self._col.find_one({"_id": guild_id}) or {}
        doc.pop("_id", None)
        return doc

    async def update(self, guild_id: int, **fields: Any) -> None:
        await self._col.update_one({"_id": guild_id}, {"$set": fields}, upsert=True)

    async def close(self) -> None:
        self._client.close()


def create_storage() -> GuildStorage:
    uri = os.getenv("MONGODB_URI")
    if uri:
        log.info("MongoDB 저장소 사용")
        return MongoStorage(uri)
    log.warning("MONGODB_URI 미설정 → JSON 파일 저장소 사용 (Render에서는 재시작 시 초기화됨)")
    return JsonStorage()
