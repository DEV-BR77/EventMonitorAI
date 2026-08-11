import asyncio
import wave
from collections import defaultdict
from io import BytesIO

from fastapi import WebSocket


class LiveAudioHub:
    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._buffers: dict[str, bytearray] = defaultdict(bytearray)
        self._buffer_bytes = 16_000 * 2 * 5
        self._send_timeout_seconds = 1.0

    async def connect(self, device_id: str, websocket: WebSocket, sample_rate: int) -> None:
        await websocket.accept()
        await websocket.send_json({"device_id": device_id, "sample_rate": sample_rate})
        self._clients[device_id].add(websocket)

    def disconnect(self, device_id: str, websocket: WebSocket) -> None:
        self._clients[device_id].discard(websocket)
        if not self._clients[device_id]:
            del self._clients[device_id]

    async def broadcast(self, device_id: str, pcm: bytes) -> int:
        buffer = self._buffers[device_id]
        buffer.extend(pcm)
        if len(buffer) > self._buffer_bytes:
            del buffer[: len(buffer) - self._buffer_bytes]
        stale: list[WebSocket] = []
        delivered = 0
        for client in self._clients.get(device_id, set()).copy():
            try:
                await asyncio.wait_for(
                    client.send_bytes(pcm), timeout=self._send_timeout_seconds
                )
                delivered += 1
            except (RuntimeError, TimeoutError):
                stale.append(client)
        for client in stale:
            self.disconnect(device_id, client)
        return delivered

    def wav_snapshot(self, device_id: str, minimum_seconds: int = 1) -> bytes | None:
        pcm = bytes(self._buffers.get(device_id, b""))
        if len(pcm) < 16_000 * 2 * minimum_seconds:
            return None
        output = BytesIO()
        with wave.open(output, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16_000)
            audio.writeframes(pcm)
        return output.getvalue()


live_audio_hub = LiveAudioHub()
