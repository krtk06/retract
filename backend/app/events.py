"""Redis-backed event bus for analysis progress (history list + pub/sub)."""

import json
import time
from collections.abc import Generator
from typing import Any, Protocol

import redis

from app.config import get_settings

EVENT_TTL_SECONDS = 3600
_TERMINAL_TYPES = {"done", "failed"}


class EventBus(Protocol):
    def publish(self, analysis_id: int, type_: str, payload: dict[str, Any]) -> None: ...
    def history(self, analysis_id: int) -> list[dict[str, Any]]: ...
    def stream(self, analysis_id: int) -> Generator[dict[str, Any], None, None]: ...


class RedisEventBus:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    @staticmethod
    def _key(analysis_id: int) -> str:
        return f"analysis:{analysis_id}:events"

    def publish(self, analysis_id: int, type_: str, payload: dict[str, Any]) -> None:
        event = {"type": type_, "payload": payload, "ts": time.time()}
        raw = json.dumps(event)
        key = self._key(analysis_id)
        pipe = self._client.pipeline()
        pipe.rpush(key, raw)
        pipe.expire(key, EVENT_TTL_SECONDS)
        pipe.publish(key, raw)
        pipe.execute()

    def history(self, analysis_id: int) -> list[dict[str, Any]]:
        raw_events = self._client.lrange(self._key(analysis_id), 0, -1)
        return [json.loads(e) for e in raw_events]

    def stream(self, analysis_id: int) -> Generator[dict[str, Any], None, None]:
        pubsub = self._client.pubsub(ignore_subscribe_messages=True)
        try:
            pubsub.subscribe(self._key(analysis_id))
            while True:
                message = pubsub.get_message(timeout=30.0)
                if message is None:
                    yield {"type": "ping", "payload": {}, "ts": time.time()}
                    continue
                if message.get("type") != "message":
                    continue
                event = json.loads(message["data"])
                yield event
                if event.get("type") in _TERMINAL_TYPES:
                    return
        finally:
            pubsub.close()


_bus: EventBus | None = None


def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
        _bus = RedisEventBus(client)
    return _bus


def set_bus(bus: EventBus | None) -> None:
    """Test helper: inject a fake bus."""
    global _bus
    _bus = bus
