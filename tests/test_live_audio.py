import asyncio
from types import SimpleNamespace

from app.api.dashboard import live_audio_devices, update_live_audio_permission
from app.api.events import ingest_live_audio
from app.database.base import Base
from app.models.dashboard import Device, LiveAudioAccess, User
from app.schemas.dashboard import LiveAudioPermissionUpdate
from app.services.audio import LiveAudioHub
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
