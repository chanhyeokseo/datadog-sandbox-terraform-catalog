import asyncio
import json
import logging
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        logger.debug("SSE subscriber added (total=%d)", len(self._subscribers))
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)
        logger.debug("SSE subscriber removed (total=%d)", len(self._subscribers))

    def publish(self, event_type: str, data: Any) -> None:
        if not self._subscribers:
            return
        payload = json.dumps({"type": event_type, "data": data})
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)
            logger.debug("Dropped slow SSE subscriber (total=%d)", len(self._subscribers))

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


event_bus = EventBus()
