import csv
import io
import sys
from pathlib import Path

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.cases import create_case, update_case  # noqa: E402
from eventmonitor.db import connect  # noqa: E402
from eventmonitor.reports import build_noise_log_csv, build_noise_log_pdf  # noqa: E402


def _confirmed_case(conn) -> None:
    conn.execute(
        "INSERT INTO recordings(source_path,source_hash,audio_path,started_at) "
        "VALUES ('a','a','a.wav','2026-08-08T20:00:00')"
    )
    event_id = conn.execute("""
        INSERT INTO events(
            recording_id,start_seconds,end_seconds,primary_label,event_family,
            grouping_version,segment_count,peak_dba,mean_dba
        ) VALUES (1,2,5,'Rufen','voice','1.0.0',2,61.5,54.2)
        """).lastrowid
    conn.commit()
    case_id = create_case(conn, "Abendlicher Ruf", [event_id])
    update_case(
        conn,
        case_id,
        title="Abendlicher Ruf",
        notes="Zweimal deutlich hörbar.",
        status="confirmed",
        actor="Admin",
        reason="Audio geprüft",
    )


def test_csv_contains_confirmed_case_and_utf8_bom(tmp_path: Path) -> None:
    conn = connect(tmp_path / "report.sqlite3")
    _confirmed_case(conn)
    payload = build_noise_log_csv(conn)
    assert payload.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), delimiter=";"))
    assert rows[0]["Case-Titel"] == "Abendlicher Ruf"
    assert rows[0]["Historie intakt"] == "Ja"
    assert rows[0]["Kategorie"] == "Rufen"
    conn.close()


def test_pdf_is_generated_for_confirmed_case(tmp_path: Path) -> None:
    conn = connect(tmp_path / "report-pdf.sqlite3")
    _confirmed_case(conn)
    payload = build_noise_log_pdf(conn)
    assert payload.startswith(b"%PDF-")
    assert len(payload) > 2_000
    conn.close()
