from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import tempfile
import wave
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

CLIP_PORT = int(os.getenv("EVENTMONITOR_CLIP_PORT", "12346"))
CLIP_DIRECTORY = Path(os.getenv("EVENTMONITOR_CLIP_DIR", "/var/lib/eventmonitor/clips"))
MAX_CLIP_BYTES = 16_000 * 2 * 10 + 44
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_wav(payload: bytes) -> dict[str, int]:
    if len(payload) > MAX_CLIP_BYTES:
        raise ValueError("Clip exceeds maximum size")
    try:
        with wave.open(io.BytesIO(payload), "rb") as audio:
            metadata = {
                "channels": audio.getnchannels(),
                "sample_width": audio.getsampwidth(),
                "sample_rate": audio.getframerate(),
                "frame_count": audio.getnframes(),
            }
    except (EOFError, wave.Error) as error:
        raise ValueError("Invalid WAV payload") from error
    if metadata["channels"] != 1 or metadata["sample_width"] != 2:
        raise ValueError("Clip must contain 16-bit mono PCM")
    if metadata["sample_rate"] != 16_000:
        raise ValueError("Clip sample rate must be 16000 Hz")
    if not 16_000 <= metadata["frame_count"] <= 160_000:
        raise ValueError("Clip duration must be between 1 and 10 seconds")
    return metadata


def save_clip(
    payload: bytes,
    directory: str | Path,
    *,
    device_id: str,
    event_id: str,
    trigger_uptime_ms: str,
    source_ip: str,
) -> Path:
    if not SAFE_ID.fullmatch(device_id) or not SAFE_ID.fullmatch(event_id):
        raise ValueError("Invalid device or event identifier")
    metadata = validate_wav(payload)
    target_directory = Path(directory)
    target_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC)
    stem = f"{timestamp:%Y%m%dT%H%M%S.%fZ}-{device_id}-{event_id}"
    target = target_directory / f"{stem}.wav"
    with tempfile.NamedTemporaryFile(dir=target_directory, suffix=".wav.tmp", delete=False) as file:
        temporary = Path(file.name)
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, target)
    sidecar = {
        **metadata,
        "device_id": device_id,
        "event_id": event_id,
        "trigger_uptime_ms": int(trigger_uptime_ms),
        "source_ip": source_ip,
        "received_at": timestamp.isoformat(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "wav_path": str(target),
    }
    sidecar_path = target.with_suffix(".json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    return target


class ClipRequestHandler(BaseHTTPRequestHandler):
    server_version = "EventMonitorClipReceiver/1.0"

    def _respond(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        self.connection.settimeout(10)
        if self.path != "/clips":
            self._respond(404, {"error": "not found"})
            return
        configured_token = os.getenv("EVENTMONITOR_CLIP_TOKEN", "")
        supplied_token = self.headers.get("X-Clip-Token", "")
        if not configured_token or not hmac.compare_digest(configured_token, supplied_token):
            self._respond(401, {"error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_CLIP_BYTES:
            self._respond(413, {"error": "invalid content length"})
            return
        payload = self.rfile.read(length)
        try:
            target = save_clip(
                payload,
                CLIP_DIRECTORY,
                device_id=self.headers.get("X-Device-ID", ""),
                event_id=self.headers.get("X-Event-ID", ""),
                trigger_uptime_ms=self.headers.get("X-Trigger-Uptime-Ms", "0"),
                source_ip=self.client_address[0],
            )
        except (OSError, ValueError) as error:
            self._respond(400, {"error": str(error)})
            return
        self._respond(201, {"path": str(target), "bytes": len(payload)})

    def log_message(self, message: str, *args: object) -> None:
        print(f"Clip receiver {self.address_string()}: {message % args}")


def start_clip_server(
    host: str = "0.0.0.0", port: int = CLIP_PORT
) -> tuple[ThreadingHTTPServer, Thread]:
    server = ThreadingHTTPServer((host, port), ClipRequestHandler)
    thread = Thread(target=server.serve_forever, name="eventmonitor-clips", daemon=True)
    thread.start()
    return server, thread
