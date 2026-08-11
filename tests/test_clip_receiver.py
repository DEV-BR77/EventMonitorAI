import io
import json
import os
import sys
import urllib.error
import urllib.request
import wave
from pathlib import Path

import pytest

EDGE_DIR = Path(__file__).resolve().parents[1] / "edge" / "raspberry-pi"
sys.path.append(str(EDGE_DIR))

import clip_receiver  # noqa: E402
from clip_receiver import save_clip, start_clip_server, validate_wav  # noqa: E402


def _wav(seconds: int = 5) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\x00\x00" * 16_000 * seconds)
    return output.getvalue()


def test_wav_validation_and_atomic_sidecar(tmp_path: Path) -> None:
    metadata = validate_wav(_wav())
    assert metadata["frame_count"] == 80_000
    target = save_clip(
        _wav(),
        tmp_path,
        device_id="esp32-aabb",
        event_id="17",
        trigger_uptime_ms="1234",
        source_ip="127.0.0.1",
    )
    assert target.is_file()
    sidecar = json.loads(target.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["sample_rate"] == 16_000
    assert sidecar["event_id"] == "17"
    assert len(sidecar["sha256"]) == 64
    with pytest.raises(ValueError, match="Invalid WAV"):
        validate_wav(b"not-wave")


def test_http_receiver_requires_token_and_accepts_valid_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EVENTMONITOR_CLIP_TOKEN", "test-secret")
    monkeypatch.setattr(clip_receiver, "CLIP_DIRECTORY", tmp_path)
    server, thread = start_clip_server("127.0.0.1", 0)
    url = f"http://127.0.0.1:{server.server_port}/clips"
    try:
        unauthorized = urllib.request.Request(url, data=_wav(), method="POST")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(unauthorized)
        assert error.value.code == 401
        request = urllib.request.Request(
            url,
            data=_wav(),
            method="POST",
            headers={
                "X-Clip-Token": os.environ["EVENTMONITOR_CLIP_TOKEN"],
                "X-Device-ID": "esp32-aabb",
                "X-Event-ID": "18",
                "X-Trigger-Uptime-Ms": "5000",
                "Content-Type": "audio/wav",
            },
        )
        with urllib.request.urlopen(request) as response:
            assert response.status == 201
        assert len(list(tmp_path.glob("*.wav"))) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
