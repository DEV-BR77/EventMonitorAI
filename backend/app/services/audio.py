from collections import defaultdict

from fastapi import WebSocket


class LiveAudioHub:
    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, device_id: str, websocket: WebSocket, sample_rate: int) -> None:
        await websocket.accept()
        await websocket.send_json({"device_id": device_id, "sample_rate": sample_rate})
        self._clients[device_id].add(websocket)

    def disconnect(self, device_id: str, websocket: WebSocket) -> None:
        self._clients[device_id].discard(websocket)
        if not self._clients[device_id]:
            del self._clients[device_id]

    async def broadcast(self, device_id: str, pcm: bytes) -> int:
        stale: list[WebSocket] = []
        delivered = 0
        for client in self._clients.get(device_id, set()).copy():
            try:
                await client.send_bytes(pcm)
                delivered += 1
            except RuntimeError:
                stale.append(client)
        for client in stale:
            self.disconnect(device_id, client)
        return delivered


live_audio_hub = LiveAudioHub()
