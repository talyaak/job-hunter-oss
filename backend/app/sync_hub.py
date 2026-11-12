import asyncio
import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)

IDLE_STATE: dict[str, Any] = {
    "phase": "idle",
    "run_id": None,
    "raw_count": 0,
    "passed_count": 0,
    "processed": 0,
    "hard_rejected": 0,
    "deduped": 0,
    "llm_rejected": 0,
    "current_job": None,
    "error_message": None,
}


class SyncHub:
    def __init__(self) -> None:
        self.clients: list[WebSocket] = []
        self.state = dict(IDLE_STATE)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.append(ws)
        await ws.send_json(self.state)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.clients:
            self.clients.remove(ws)

    def emit(self, **fields: Any) -> None:
        self.state = {**self.state, **fields}
        if self._loop and self.clients:
            asyncio.run_coroutine_threadsafe(self._broadcast(), self._loop)

    def reset_idle(self) -> None:
        self.emit(**IDLE_STATE)

    async def _broadcast(self) -> None:
        dead: list[WebSocket] = []
        for ws in self.clients:
            try:
                await ws.send_json(self.state)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


hub = SyncHub()
