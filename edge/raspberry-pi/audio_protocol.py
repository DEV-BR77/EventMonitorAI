from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = b"EMAI"
PROTOCOL_VERSION = 1
HEADER = struct.Struct("<4sBBHQIIHHHH")


@dataclass(frozen=True)
class PacketMetadata:
    protocol_version: int
    device_id: str
    sequence: int
    uptime_ms: int
    sample_rate: int
    sample_count: int
    peak: int
    firmware_version: str


def decode_packet(data: bytes) -> tuple[PacketMetadata | None, bytes]:
    """Decode a framed packet while accepting legacy raw PCM packets."""
    if len(data) < HEADER.size or data[:4] != MAGIC:
        return None, data

    (
        magic,
        protocol_version,
        _flags,
        header_size,
        numeric_device_id,
        sequence,
        uptime_ms,
        sample_rate,
        sample_count,
        peak,
        firmware_version_code,
    ) = HEADER.unpack_from(data)
    if magic != MAGIC or protocol_version != PROTOCOL_VERSION or header_size != HEADER.size:
        raise ValueError("Unsupported EventMonitorAI audio packet")

    payload = data[header_size:]
    if len(payload) != sample_count * 2:
        raise ValueError("Audio packet sample count does not match payload")

    return (
        PacketMetadata(
            protocol_version=protocol_version,
            device_id=f"esp32-{numeric_device_id.to_bytes(6, 'little').hex()}",
            sequence=sequence,
            uptime_ms=uptime_ms,
            sample_rate=sample_rate,
            sample_count=sample_count,
            peak=peak,
            firmware_version=(
                f"{(firmware_version_code >> 12) & 0x0F}."
                f"{(firmware_version_code >> 6) & 0x3F}."
                f"{firmware_version_code & 0x3F}"
            ),
        ),
        payload,
    )


def sequence_gap(previous: int | None, current: int) -> int:
    if previous is None:
        return 0
    expected = (previous + 1) & 0xFFFFFFFF
    return (current - expected) & 0xFFFFFFFF
