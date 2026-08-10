import asyncio

from fastapi import WebSocket


class LiveEventHub:
    def __init__(self) -> None:
        self._clients: dict[int, set[WebSocket]] = {}

    async def connect(self, tenant_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.setdefault(tenant_id, set()).add(websocket)

    def disconnect(self, tenant_id: int, websocket: WebSocket) -> None:
        self._clients.get(tenant_id, set()).discard(websocket)

    async def broadcast(self, tenant_id: int, payload: dict[str, object]) -> None:
        stale: list[WebSocket] = []
        for client in self._clients.get(tenant_id, set()):
            try:
                await client.send_json(payload)
            except RuntimeError:
                stale.append(client)
        for client in stale:
            self.disconnect(tenant_id, client)

    def publish(self, tenant_id: int, payload: dict[str, object]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.broadcast(tenant_id, payload))


live_hub = LiveEventHub()
