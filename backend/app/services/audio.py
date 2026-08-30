import asyncio
import wave
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from io import BytesIO

import numpy as np

from fastapi import WebSocket


class LiveAudioHub:
    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._buffers: dict[str, bytearray] = defaultdict(bytearray)
        self._last_received_at: dict[str, datetime] = {}
        self._sample_rate = 16_000
        self._bytes_per_second = self._sample_rate * 2
        self._buffer_bytes = self._bytes_per_second * 20
        self._maximum_snapshot_bytes = self._bytes_per_second * 10
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
        self._last_received_at[device_id] = datetime.now(UTC)
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

    def wav_snapshot(
        self,
        device_id: str,
        minimum_seconds: int = 1,
        *,
        event_start: datetime | None = None,
        event_end: datetime | None = None,
    ) -> bytes | None:
        pcm = bytes(self._buffers.get(device_id, b""))
        if len(pcm) < self._bytes_per_second * minimum_seconds:
            return None
        candidate = pcm
        buffer_end = self._last_received_at.get(device_id)
        if event_start is not None and event_end is not None and buffer_end is not None:
            buffer_start = buffer_end - timedelta(seconds=len(pcm) / self._bytes_per_second)
            wanted_start = event_start - timedelta(seconds=1)
            wanted_end = event_end + timedelta(seconds=1)
            overlap_start = max(buffer_start, wanted_start)
            overlap_end = min(buffer_end, wanted_end)
            if overlap_end > overlap_start:
                first_sample = max(
                    0,
                    round((overlap_start - buffer_start).total_seconds() * self._sample_rate),
                )
                last_sample = min(
                    len(pcm) // 2,
                    round((overlap_end - buffer_start).total_seconds() * self._sample_rate),
                )
                candidate = pcm[first_sample * 2 : last_sample * 2]
        if len(candidate) > self._maximum_snapshot_bytes:
            # Preserve two seconds before the strongest sample and the remaining
            # context after it. This keeps short impulsive sounds and the start
            # of screams audible even when an event lasts longer than ten seconds.
            samples = np.frombuffer(candidate, dtype="<i2")
            peak_sample = int(np.argmax(np.abs(samples.astype(np.int32))))
            snapshot_samples = self._maximum_snapshot_bytes // 2
            start_sample = max(0, peak_sample - self._sample_rate * 2)
            start_sample = min(start_sample, len(samples) - snapshot_samples)
            candidate = candidate[start_sample * 2 : (start_sample + snapshot_samples) * 2]
        if len(candidate) < self._bytes_per_second * minimum_seconds:
            return None
        output = BytesIO()
        with wave.open(output, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(self._sample_rate)
            audio.writeframes(candidate)
        return output.getvalue()


live_audio_hub = LiveAudioHub()
