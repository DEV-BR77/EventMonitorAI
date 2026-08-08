from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

EVENT_GROUPING_VERSION = "1.0.0"
VOCAL_LABELS = {"Schreien", "Rufen", "Streit / mehrere Stimmen"}
IMPULSE_LABELS = {"Schlagen / Aufprall", "Türknallen", "Hupe"}


@dataclass(frozen=True)
class GroupingPolicy:
    version: str = EVENT_GROUPING_VERSION
    default_gap_seconds: float = 1.0
    vocal_gap_seconds: float = 3.0
    impulse_gap_seconds: float = 1.5

    def __post_init__(self) -> None:
        if self.version != EVENT_GROUPING_VERSION:
            raise ValueError("Nicht unterstützte Ereignisgruppierungs-Version.")
        if min(self.default_gap_seconds, self.vocal_gap_seconds, self.impulse_gap_seconds) < 0:
            raise ValueError("Gruppierungsabstände dürfen nicht negativ sein.")


@dataclass(frozen=True)
class EventGroup:
    recording_id: int
    start_seconds: float
    end_seconds: float
    primary_label: str
    event_family: str
    segment_ids: tuple[int, ...]
    peak_dba: float | None
    mean_dba: float | None


def event_family(label: str) -> str:
    if label in VOCAL_LABELS:
        return "voice"
    if label in IMPULSE_LABELS:
        return "impulse"
    return f"label:{label}"


def _allowed_gap(family: str, policy: GroupingPolicy) -> float:
    if family == "voice":
        return policy.vocal_gap_seconds
    if family == "impulse":
        return policy.impulse_gap_seconds
    return policy.default_gap_seconds


def _finish(rows: list[Any], family: str) -> EventGroup:
    durations: dict[str, float] = {}
    for row in rows:
        durations[row["label"]] = durations.get(row["label"], 0) + max(
            0.0, float(row["end_seconds"] - row["start_seconds"])
        )
    primary_label = max(durations, key=lambda label: (durations[label], label))
    peaks = [float(row["peak_dba"]) for row in rows if row["peak_dba"] is not None]
    weighted = [
        (float(row["mean_dba"]), float(row["end_seconds"] - row["start_seconds"]))
        for row in rows
        if row["mean_dba"] is not None
    ]
    total_weight = sum(weight for _, weight in weighted)
    return EventGroup(
        recording_id=int(rows[0]["recording_id"]),
        start_seconds=float(rows[0]["start_seconds"]),
        end_seconds=max(float(row["end_seconds"]) for row in rows),
        primary_label=primary_label,
        event_family=family,
        segment_ids=tuple(int(row["id"]) for row in rows),
        peak_dba=max(peaks) if peaks else None,
        mean_dba=(
            sum(value * weight for value, weight in weighted) / total_weight
            if total_weight > 0
            else None
        ),
    )


def group_segments(
    segments: Iterable[Any], policy: GroupingPolicy | None = None
) -> list[EventGroup]:
    policy = policy or GroupingPolicy()
    ordered = sorted(
        segments,
        key=lambda row: (int(row["recording_id"]), float(row["start_seconds"]), int(row["id"])),
    )
    groups: list[EventGroup] = []
    current: list[Any] = []
    current_family = ""
    for row in ordered:
        family = event_family(row["label"])
        can_join = bool(current) and int(row["recording_id"]) == int(current[0]["recording_id"])
        if can_join:
            gap = float(row["start_seconds"]) - max(float(item["end_seconds"]) for item in current)
            can_join = family == current_family and gap <= _allowed_gap(family, policy)
        if not can_join and current:
            groups.append(_finish(current, current_family))
            current = []
        if not current:
            current_family = family
        current.append(row)
    if current:
        groups.append(_finish(current, current_family))
    return groups


def rebuild_events(conn: Any, policy: GroupingPolicy | None = None) -> int:
    policy = policy or GroupingPolicy()
    rows = conn.execute(
        """
        SELECT id,recording_id,start_seconds,end_seconds,label,peak_dba,mean_dba
        FROM segments s WHERE label IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM event_segments es JOIN events e ON e.id=es.event_id
              WHERE es.segment_id=s.id AND e.source<>'automatic'
          )
        ORDER BY recording_id,start_seconds,id
        """
    ).fetchall()
    groups = group_segments(rows, policy)
    try:
        conn.execute("DELETE FROM events WHERE source='automatic'")
        for group in groups:
            cursor = conn.execute(
                """
                INSERT INTO events(
                    recording_id,start_seconds,end_seconds,primary_label,event_family,
                    grouping_version,segment_count,peak_dba,mean_dba
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    group.recording_id,
                    group.start_seconds,
                    group.end_seconds,
                    group.primary_label,
                    group.event_family,
                    policy.version,
                    len(group.segment_ids),
                    group.peak_dba,
                    group.mean_dba,
                ),
            )
            event_id = cursor.lastrowid
            conn.executemany(
                "INSERT INTO event_segments(event_id,segment_id,position) VALUES (?,?,?)",
                [
                    (event_id, segment_id, position)
                    for position, segment_id in enumerate(group.segment_ids)
                ],
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(groups)
