import struct
import sys
from pathlib import Path

EDGE_DIR = Path(__file__).resolve().parents[1] / "edge" / "raspberry-pi"
sys.path.insert(0, str(EDGE_DIR))

from audio_protocol import HEADER, decode_packet, sequence_gap  # noqa: E402


def test_framed_audio_packet_is_decoded() -> None:
    samples = struct.pack("<3h", 10, -20, 30)
    version_code = (0 << 12) | (3 << 6) | 0
    packet = (
        HEADER.pack(
            b"EMAI", 1, 0, HEADER.size, 0x9C9BDE8FCBA4, 42, 1234, 16000, 3, 30, version_code
        )
        + samples
    )

    metadata, payload = decode_packet(packet)

    assert payload == samples
    assert metadata is not None
    assert metadata.device_id == "esp32-a4cb8fde9b9c"
    assert metadata.sequence == 42
    assert metadata.firmware_version == "0.3.0"


def test_legacy_pcm_packet_remains_supported() -> None:
    packet = struct.pack("<2h", 1, -1)
    metadata, payload = decode_packet(packet)
    assert metadata is None
    assert payload == packet


def test_sequence_gap_handles_loss_and_wraparound() -> None:
    assert sequence_gap(None, 100) == 0
    assert sequence_gap(100, 101) == 0
    assert sequence_gap(100, 104) == 3
    assert sequence_gap(0xFFFFFFFF, 0) == 0
