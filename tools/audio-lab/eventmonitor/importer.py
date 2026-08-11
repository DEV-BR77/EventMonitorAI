from __future__ import annotations

import csv
import hashlib
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from .db import connect

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parse_frequency(text: str) -> float:
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", text or "")
    if not m:
        raise ValueError(f"Keine Frequenz erkannt: {text!r}")
    return float(m.group(1))


def discover_files(folder: Path):
    files = [p for p in folder.rglob("*") if p.is_file()]
    audios = [p for p in files if p.suffix.lower() in AUDIO_EXTENSIONS]
    by_name = {p.name.lower(): p for p in files}
    return (
        audios[0] if audios else None,
        by_name.get("db.csv"),
        by_name.get("extended.csv"),
        by_name.get("extended_logarithm.csv"),
    )


def read_db_csv(path: Path):
    rows = []
    first = None
    occurrence = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            dt = datetime.strptime(f"{r['Date']} {r['Time']}", "%d.%m.%Y %H:%M:%S")
            first = first or dt
            n = occurrence.get(dt, 0)
            occurrence[dt] = n + 1
            offset = (dt - first).total_seconds() + n * 0.2
            avg_key = next(k for k in r if "Average" in k)
            rows.append(
                (
                    offset,
                    dt.isoformat(),
                    float(r["Current (dB-A)"]),
                    float(r["Max (dB-A)"]),
                    float(r[avg_key]),
                )
            )
    return first, rows


def read_spectrum(path: Path):
    out = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            first_key = next(iter(r))
            out.append(
                (parse_frequency(r[first_key]), float(r["MIN"]), float(r["MAX"]), float(r["AVG"]))
            )
    return out


def create_segments(conn, recording_id: int, duration: float, seconds: float = 5.0):
    samples = conn.execute(
        """
    SELECT offset_seconds, current_dba
    FROM db_samples
    WHERE recording_id = ?
    ORDER BY offset_seconds
    """,
        (recording_id,),
    ).fetchall()
    all_vals = [float(r["current_dba"]) for r in samples]
    baseline = sorted(all_vals)[len(all_vals) // 2] if all_vals else 0
    start = 0.0
    while start < duration:
        end = min(duration, start + seconds)
        vals = [
            float(r["current_dba"]) for r in samples if start <= float(r["offset_seconds"]) < end
        ]
        peak = max(vals) if vals else None
        mean = sum(vals) / len(vals) if vals else None
        score = (peak - baseline) if peak is not None else None
        conn.execute(
            """
    INSERT OR IGNORE INTO segments(
        recording_id,
        start_seconds,
        end_seconds,
        peak_dba,
        mean_dba,
        event_score
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """,
            (recording_id, start, end, peak, mean, score),
        )
        start = end


def begin_import_job(conn, source: Path, source_hash: str) -> int:
    existing = conn.execute(
        "SELECT id, attempts FROM import_jobs WHERE source_hash=?", (source_hash,)
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE import_jobs
            SET source_path=?, status='running', attempts=?, recording_id=NULL,
                error_message=NULL, started_at=CURRENT_TIMESTAMP, finished_at=NULL
            WHERE id=?
            """,
            (str(source), int(existing["attempts"]) + 1, int(existing["id"])),
        )
        job_id = int(existing["id"])
    else:
        cursor = conn.execute(
            "INSERT INTO import_jobs(source_path, source_hash, status) VALUES (?, ?, 'running')",
            (str(source), source_hash),
        )
        job_id = int(cursor.lastrowid)
    conn.commit()
    return job_id


def finish_import_job(
    conn,
    job_id: int,
    status: str,
    recording_id: int | None = None,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE import_jobs
        SET status=?, recording_id=?, error_message=?, finished_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (status, recording_id, error_message, job_id),
    )
    conn.commit()


def import_package(
    source: str | Path,
    db_path: str | Path = "data/eventmonitor.sqlite3",
    library_dir: str | Path = "data/library",
    segment_seconds: float = 5.0,
) -> tuple[int, bool]:
    source = Path(source).resolve()
    library = Path(library_dir).resolve()
    library.mkdir(parents=True, exist_ok=True)
    source_hash = (
        sha256_file(source)
        if source.is_file()
        else hashlib.sha256(str(source).encode()).hexdigest()
    )
    conn = connect(db_path)
    job_id = begin_import_job(conn, source, source_hash)
    existing = conn.execute(
        "SELECT id FROM recordings WHERE source_hash=?", (source_hash,)
    ).fetchone()
    if existing:
        finish_import_job(conn, job_id, "skipped", int(existing["id"]))
        conn.close()
        return int(existing["id"]), False
    temp = None
    rec_dir = None
    try:
        if source.is_file() and zipfile.is_zipfile(source):
            temp = tempfile.TemporaryDirectory()
            folder = Path(temp.name)
            with zipfile.ZipFile(source) as zf:
                zf.extractall(folder)
        else:
            folder = source if source.is_dir() else source.parent
        audio, db_csv, ext_csv, log_csv = discover_files(folder)
        if not audio or not db_csv:
            raise ValueError("Paket benötigt mindestens eine Audiodatei und db.csv.")
        import soundfile as sf

        info = sf.info(audio)
        started, db_rows = read_db_csv(db_csv)
        rec_dir = library / source_hash[:16]
        rec_dir.mkdir(parents=True, exist_ok=True)
        audio_copy = rec_dir / audio.name
        shutil.copy2(audio, audio_copy)
        cur = conn.execute(
            """
            INSERT INTO recordings(
                source_path,
                source_hash,
                audio_path,
                started_at,
                duration_seconds,
                sample_rate,
                channels
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(source),
                source_hash,
                str(audio_copy),
                started.isoformat() if started else None,
                float(info.duration),
                int(info.samplerate),
                int(info.channels),
            ),
        )
        rid = int(cur.lastrowid)
        conn.executemany(
            """
            INSERT INTO db_samples(
                recording_id,
                offset_seconds,
                measured_at,
                current_dba,
                max_dba,
                average_dba
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(rid, *row) for row in db_rows],
        )
        for kind, p in [("linear", ext_csv), ("logarithmic", log_csv)]:
            if p:
                conn.executemany(
                    """
                    INSERT INTO spectrum_bins(
                        recording_id,
                        spectrum_type,
                        frequency_hz,
                        min_db,
                        max_db,
                        avg_db
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [(rid, kind, *row) for row in read_spectrum(p)],
                )
        create_segments(conn, rid, float(info.duration), segment_seconds)
        conn.commit()
        finish_import_job(conn, job_id, "completed", rid)
        return rid, True
    except Exception as error:
        conn.rollback()
        finish_import_job(conn, job_id, "failed", error_message=str(error))
        if rec_dir and rec_dir.exists():
            shutil.rmtree(rec_dir)
        raise
    finally:
        conn.close()
        if temp:
            temp.cleanup()


def import_folder(
    folder: str | Path, db_path="data/eventmonitor.sqlite3", library_dir="data/library"
):
    results = []
    for p in sorted(Path(folder).rglob("*.zip")):
        try:
            rid, created = import_package(p, db_path, library_dir)
            results.append((str(p), rid, "importiert" if created else "bereits vorhanden", ""))
        except Exception as e:
            results.append((str(p), None, "Fehler", str(e)))
    return results


def resume_imports(
    db_path: str | Path = "data/eventmonitor.sqlite3",
    library_dir: str | Path = "data/library",
):
    conn = connect(db_path)
    pending = conn.execute(
        """
        SELECT source_path FROM import_jobs
        WHERE status IN ('failed', 'running')
        ORDER BY started_at, id
        """
    ).fetchall()
    conn.close()
    results = []
    for row in pending:
        source = Path(row["source_path"])
        if not source.exists():
            results.append((str(source), None, "Fehler", "Quelldatei ist nicht mehr verfügbar"))
            continue
        try:
            recording_id, created = import_package(source, db_path, library_dir)
            results.append(
                (
                    str(source),
                    recording_id,
                    "importiert" if created else "bereits vorhanden",
                    "",
                )
            )
        except Exception as error:
            results.append((str(source), None, "Fehler", str(error)))
    return results
