import asyncio

from fastapi import WebSocket


class LiveEventHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, payload: dict[str, object]) -> None:
        stale: list[WebSocket] = []
        for client in self._clients:
            try:
                await client.send_json(payload)
            except RuntimeError:
                stale.append(client)
        for client in stale:
            self.disconnect(client)

    def publish(self, payload: dict[str, object]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.broadcast(payload))


live_hub = LiveEventHub()
