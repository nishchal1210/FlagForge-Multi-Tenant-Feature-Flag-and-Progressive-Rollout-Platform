import asyncio
from collections import defaultdict
# automatically creates a default value when a missing dictionary key is accesses
from typing import Any


class SSEConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[
            str,
            set[asyncio.Queue[dict[str, Any]]],
        ] = defaultdict(set)

        self._lock = asyncio.Lock()

    async def connect(
        self,
        environment_id: str,
    ) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = (
            asyncio.Queue(maxsize=10)
        )

        async with self._lock:
            self._connections[environment_id].add(queue)

        return queue

    async def disconnect(
        self,
        environment_id: str,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> None:
        async with self._lock:
            connections = self._connections.get(
                environment_id
            )

            if connections is None:
                return

            connections.discard(queue)

            if not connections:
                self._connections.pop(
                    environment_id,
                    None,
                )

    async def broadcast(
        self,
        environment_id: str,
        event: dict[str, Any],
    ) -> None:
        async with self._lock:
            queues = list(
                self._connections.get(
                    environment_id,
                    set(),
                )
            )

        for queue in queues:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


sse_manager = SSEConnectionManager()