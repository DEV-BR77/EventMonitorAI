from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

DEFAULT_CLASSES = (
    ("HORN", "Hupen", "base", None),
    ("VOICE_LOUD", "Rufen/Schreien", "base", None),
    ("IMPACT", "Schlag/Aufprall", "base", None),
    ("MUSIC", "Musik", "base", None),
    ("DOG", "Hund", "base", None),
    ("ENGINE", "Motor", "base", None),
    ("SIREN", "Sirene", "base", None),
    ("BIRDS", "Vögel", "base", None),
    ("MACHINERY", "Maschinen", "base", None),
    ("VEHICLE", "Fahrzeuge", "base", None),
    ("BALL_CONCRETE", "Fußball gegen Beton", "fine", "IMPACT"),
    ("BALL_METAL", "Fußball gegen Metall", "fine", "IMPACT"),
    ("HIT_LAMPPOST", "Schlagen gegen Laterne", "fine", "IMPACT"),
    ("VOICE_SUSTAINED", "Anhaltendes Rufen", "fine", "VOICE_LOUD"),
    ("VEHICLE_HORN", "Fahrzeughupen", "fine", "HORN"),
    ("OTHER_NOISE", "Sonstiger Lärm", "fine", None),
)


def seed_local_classes(conn: Any) -> None:
    for order, (code, name, level, parent_code) in enumerate(DEFAULT_CLASSES, start=1):
        conn.execute(
            """
            INSERT OR IGNORE INTO event_classes(code,name,level,parent_code,sort_order)
            VALUES (?,?,?,?,?)
            """,
            (code, name, level, parent_code, order),
        )


def active_class_names(conn: Any) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM event_classes WHERE active=1 ORDER BY sort_order,name"
        )
    ]


def sync_class_definitions(conn: Any, definitions: Iterable[Mapping[str, object]]) -> int:
    rows = list(definitions)
    codes = {str(row["code"]) for row in rows}
    base_codes = {str(row["code"]) for row in rows if row["level"] == "base"}
    for row in rows:
        level = str(row["level"])
        parent = row.get("parent_code")
        if level not in {"base", "fine"}:
            raise ValueError(f"Ungültige Klassenebene: {level}")
        if level == "base" and parent is not None:
            raise ValueError("Basisklasse mit unzulässiger Elternklasse")
        if parent is not None and str(parent) not in base_codes:
            raise ValueError(f"Unbekannte Basisklasse: {parent}")

    synced_at = datetime.now(UTC).isoformat()
    with conn:
        if codes:
            placeholders = ",".join("?" for _ in codes)
            conn.execute(
                f"UPDATE event_classes SET active=0,synced_at=? WHERE code NOT IN ({placeholders})",
                (synced_at, *sorted(codes)),
            )
        for row in rows:
            conn.execute(
                """
                INSERT INTO event_classes(
                    code,name,level,parent_code,active,trainable,sort_order,synced_at
                ) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(code) DO UPDATE SET
                    name=excluded.name,level=excluded.level,parent_code=excluded.parent_code,
                    active=excluded.active,trainable=excluded.trainable,
                    sort_order=excluded.sort_order,synced_at=excluded.synced_at
                """,
                (
                    row["code"],
                    row["name"],
                    row["level"],
                    row.get("parent_code"),
                    int(bool(row.get("active", True))),
                    int(bool(row.get("trainable", True))),
                    int(row.get("sort_order", 0)),
                    synced_at,
                ),
            )
    return len(rows)
