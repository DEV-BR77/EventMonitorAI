import asyncio
import io
import wave
from types import SimpleNamespace

from app.api.dashboard import live_audio_devices, update_live_audio_permission
from app.api.events import create_event, ingest_live_audio, update_device_telemetry
from app.core.config import settings
from app.database.base import Base
from app.models.dashboard import AudioClip, Device, DeviceCalibration, LiveAudioAccess, User
from app.schemas.dashboard import DeviceTelemetryWrite, LiveAudioPermissionUpdate
from app.schemas.event import EventCreate
from app.services.audio import LiveAudioHub, live_audio_hub
from fastapi import BackgroundTasks
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _database() -> tuple[object, Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def test_viewer_sees_only_explicitly_allowed_active_microphone() -> None:
    _, db = _database()
    with db:
        viewer = User(username="viewer", password_hash="x", role="viewer")
        db.add_all(
            [
                viewer,
                Device(device_id="allowed", name="Allowed"),
                Device(device_id="other", name="Other"),
                Device(device_id="inactive", name="Inactive", enabled=False),
            ]
        )
        db.commit()
        db.add_all(
            [
                LiveAudioAccess(user_id=viewer.id, device_id="allowed"),
                LiveAudioAccess(user_id=viewer.id, device_id="inactive"),
            ]
        )
        db.commit()

        assert [item.device_id for item in live_audio_devices(db, viewer)] == ["allowed"]


def test_admin_replaces_user_live_audio_permissions() -> None:
    _, db = _database()
    with db:
        viewer = User(username="viewer", password_hash="x", role="viewer")
        db.add_all(
            [viewer, Device(device_id="mic-b", name="B"), Device(device_id="mic-a", name="A")]
        )
        db.commit()

        result = update_live_audio_permission(
            viewer.id,
            LiveAudioPermissionUpdate(device_ids=["mic-b", "mic-a", "mic-b"]),
            db,
            SimpleNamespace(username="admin", role="admin"),
        )

        assert result.device_ids == ["mic-a", "mic-b"]
        assert list(db.scalars(select(LiveAudioAccess.device_id)).all()) == ["mic-a", "mic-b"]


def test_audio_ingest_broadcasts_pcm_only_for_active_device() -> None:
    _, db = _database()
    with db:
        db.add(Device(device_id="mic", name="Mic"))
        db.commit()
        result = asyncio.run(ingest_live_audio("mic", b"\x01\x00" * 100, db, None))

        assert result == {"bytes": 200, "listeners": 0}


def test_applied_calibration_offset_changes_new_telemetry_values() -> None:
    _, db = _database()
    with db:
        db.add_all(
            [
                Device(device_id="mic", name="Mic"),
                DeviceCalibration(device_id="mic", applied_offset_db=-7.5),
            ]
        )
        db.commit()

        result = update_device_telemetry(
            DeviceTelemetryWrite(device_id="mic", db_level=54.0), db, None
        )

        assert result.db_level == 46.5


def test_live_audio_hub_sends_binary_pcm() -> None:
    class Socket:
        def __init__(self) -> None:
            self.payloads: list[bytes] = []

        async def accept(self) -> None:
            pass

        async def send_json(self, payload: dict[str, object]) -> None:
            pass

        async def send_bytes(self, payload: bytes) -> None:
            self.payloads.append(payload)

    async def exercise() -> tuple[int, list[bytes]]:
        hub = LiveAudioHub()
        socket = Socket()
        await hub.connect("mic", socket, 16_000)  # type: ignore[arg-type]
        delivered = await hub.broadcast("mic", b"pcm")
        return delivered, socket.payloads

    assert asyncio.run(exercise()) == (1, [b"pcm"])


def test_live_audio_hub_disconnects_blocked_client() -> None:
    class BlockedSocket:
        async def accept(self) -> None:
            pass

        async def send_json(self, payload: dict[str, object]) -> None:
            pass

        async def send_bytes(self, payload: bytes) -> None:
            await asyncio.sleep(1)

    async def exercise() -> tuple[int, bool]:
        hub = LiveAudioHub()
        hub._send_timeout_seconds = 0.01
        socket = BlockedSocket()
        await hub.connect("mic", socket, 16_000)  # type: ignore[arg-type]
        delivered = await hub.broadcast("mic", b"pcm")
        return delivered, "mic" in hub._clients

    assert asyncio.run(exercise()) == (0, False)


def test_live_audio_hub_keeps_five_second_wav_ring_buffer() -> None:
    hub = LiveAudioHub()
    asyncio.run(hub.broadcast("mic", b"\x01\x00" * 16_000 * 6))

    snapshot = hub.wav_snapshot("mic")

    assert snapshot is not None
    with wave.open(io.BytesIO(snapshot), "rb") as audio:
        assert audio.getframerate() == 16_000
        assert audio.getnframes() == 16_000 * 5


def test_new_event_receives_server_ring_buffer_clip(tmp_path) -> None:
    device_id = "server-ring-test"
    original_directory = settings.clip_directory
    settings.clip_directory = str(tmp_path / "clips")
    try:
        _, db = _database()
        with db:
            db.add(Device(device_id=device_id, name="Server ring test"))
            db.commit()
            asyncio.run(
                live_audio_hub.broadcast(
                    device_id,
                    b"\x01\x00" * 16_000 * 5,
                )
            )

            event = asyncio.run(
                create_event(
                    EventCreate(
                        timestamp="2026-08-09T04:00:00",
                        label="Speech",
                        confidence=0.9,
                        db_level=72.0,
                        device=device_id,
                    ),
                    BackgroundTasks(),
                    db,
                    None,
                )
            )

            clip = db.scalar(select(AudioClip).where(AudioClip.event_id == event.id))
            assert event.audio_available is True
            assert clip is not None
            assert clip.frame_count == 16_000 * 5
            assert clip.trigger_id == f"server-{event.id}"
    finally:
        settings.clip_directory = original_directory
