from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import soundfile as sf
import streamlit as st
from eventmonitor.backup import create_backup, restore_backup
from eventmonitor.db import connect
from eventmonitor.features import FeaturePipelineConfig
from eventmonitor.importer import import_folder, import_package, resume_imports
from eventmonitor.inference import (
    generate_segment_predictions,
    latest_prediction,
    record_prediction_review,
)
from eventmonitor.segments import update_boundaries, wav_excerpt
from eventmonitor.training import build_labeled_dataset, load_model, save_model, train_baseline
from eventmonitor.visualization import calculate_spectrogram, spectrogram_records

st.set_page_config(page_title="EventMonitor AudioLab", page_icon="🎧", layout="wide")
DB = Path("data/eventmonitor.sqlite3")
LIB = Path("data/library")
INBOX = Path("data/inbox")
LABELS = [
    "Schreien",
    "Rufen",
    "Streit / mehrere Stimmen",
    "Schlagen / Aufprall",
    "Türknallen",
    "Auto / Vorbeifahrt",
    "Motorrad",
    "Hupe",
    "Normales Sprechen",
    "Hund",
    "Musik",
    "Maschine",
    "Wind / Regen",
    "Hintergrund",
    "Unklar",
]


def format_metric(value: float | None, suffix: str = "") -> str:
    return f"{float(value):.1f}{suffix}" if value is not None else "–"


conn = connect(DB)
page = st.sidebar.radio(
    "Bereich",
    ["Übersicht", "Import", "Ereignisse lernen", "Auswertung", "Modelltraining", "Sicherung"],
)

if page == "Import":
    st.title("Messungen importieren")
    uploads = st.file_uploader("ZIP-Dateien auswählen", type=["zip"], accept_multiple_files=True)
    if st.button("Ausgewählte Dateien importieren", type="primary", disabled=not uploads):
        INBOX.mkdir(parents=True, exist_ok=True)
        for u in uploads:
            content = bytes(u.getbuffer())
            digest = hashlib.sha256(content).hexdigest()
            source = INBOX / f"{digest[:16]}-{Path(u.name).name}"
            source.write_bytes(content)
            try:
                rid, created = import_package(source, DB, LIB)
                st.success(
                    f"{u.name}: Aufnahme #{rid} – "
                    + ("importiert" if created else "bereits vorhanden")
                )
            except Exception as e:
                st.error(f"{u.name}: {e}")
    folder = st.text_input("Oder vorhandenen Ordner rekursiv importieren")
    if st.button("Ordner importieren", disabled=not folder):
        rows = import_folder(folder, DB, LIB)
        st.dataframe(
            pd.DataFrame(rows, columns=["Datei", "Aufnahme", "Status", "Fehler"]),
            width="stretch",
        )
    st.subheader("Importprotokoll")
    if st.button("Fehlgeschlagene oder unterbrochene Importe fortsetzen"):
        resumed = resume_imports(DB, LIB)
        if resumed:
            st.dataframe(
                pd.DataFrame(resumed, columns=["Datei", "Aufnahme", "Status", "Fehler"]),
                width="stretch",
            )
        else:
            st.info("Keine fortsetzbaren Importe vorhanden.")
    journal = pd.read_sql_query(
        """
        SELECT id, source_path, status, attempts, recording_id, error_message,
               started_at, finished_at
        FROM import_jobs ORDER BY id DESC LIMIT 500
        """,
        conn,
    )
    st.dataframe(journal, width="stretch")

elif page == "Übersicht":
    st.title("EventMonitor AudioLab – Übersicht")
    recs = pd.read_sql_query("SELECT * FROM recordings ORDER BY started_at DESC", conn)
    segs = pd.read_sql_query("SELECT * FROM segments", conn)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aufnahmen", len(recs))
    c2.metric("Audiostunden", f"{recs.duration_seconds.sum()/3600:.1f}" if len(recs) else "0")
    c3.metric("Segmente", len(segs))
    c4.metric("Bestätigt", int(segs.label.notna().sum()) if len(segs) else 0)
    if len(recs):
        st.dataframe(
            recs[
                ["id", "started_at", "duration_seconds", "sample_rate", "channels", "source_path"]
            ],
            width="stretch",
        )
    else:
        st.info("Noch keine Messungen importiert.")

elif page == "Modelltraining":
    st.title("Lokales Basismodell")
    labelled = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT recording_id), COUNT(DISTINCT label) "
        "FROM segments WHERE label IS NOT NULL"
    ).fetchone()
    first, second, third = st.columns(3)
    first.metric("Bestätigte Segmente", labelled[0])
    second.metric("Unabhängige Aufnahmen", labelled[1])
    third.metric("Klassen", labelled[2])
    st.caption(
        "Das Modell wird nur aus dem Trainingssplit gelernt. Validierung und Test stammen aus "
        "anderen vollständigen Aufnahmen."
    )
    if st.button("Basismodell trainieren", type="primary"):
        try:
            with st.spinner("Features berechnen und Modell auswerten …"):
                config = FeaturePipelineConfig()
                features, labels, recording_ids, _, feature_names = build_labeled_dataset(
                    conn, config
                )
                artifact = train_baseline(features, labels, recording_ids, feature_names, config)
                model_path = save_model(
                    artifact,
                    Path("models/audio-lab") / f"baseline-{datetime.now():%Y%m%d-%H%M%S}.joblib",
                )
        except (OSError, ValueError) as error:
            st.error(str(error))
        else:
            st.success(f"Modell gespeichert: {model_path}")
            st.session_state["baseline-metrics"] = artifact["metrics"]
    if "baseline-metrics" in st.session_state:
        for split_name, metrics in st.session_state["baseline-metrics"].items():
            st.subheader("Validierung" if split_name == "validation" else "Unberührter Test")
            columns = st.columns(4)
            columns[0].metric("Segmente", metrics["samples"])
            columns[1].metric("Accuracy", f"{metrics['accuracy']:.3f}")
            columns[2].metric("Balanced Accuracy", f"{metrics['balanced_accuracy']:.3f}")
            columns[3].metric("Macro-F1", f"{metrics['macro_f1']:.3f}")
            st.dataframe(pd.DataFrame(metrics["per_class"]).T, width="stretch")
    models = sorted(Path("models/audio-lab").glob("*.joblib"), reverse=True)
    st.subheader("Modellvorschläge")
    if models:
        selected_model = st.selectbox("Lokales Modell", models, format_func=lambda path: path.name)
        if st.button("Vorschläge für offene Segmente berechnen"):
            try:
                with st.spinner("Offene Segmente klassifizieren …"):
                    count = generate_segment_predictions(
                        conn, load_model(selected_model), selected_model.name
                    )
            except (OSError, ValueError) as error:
                st.error(str(error))
            else:
                st.success(f"{count} Modellvorschläge gespeichert.")
    else:
        st.info("Zuerst ein Basismodell trainieren.")

elif page == "Sicherung":
    st.title("Backup und Datenmigration")
    st.write(
        "Die Sicherung enthält Datenbank, Labels, Segmentgrenzen und alle "
        "importierten Audiodateien."
    )
    backup_dir = Path("data/backups")
    if st.button("Neue Sicherung erstellen", type="primary"):
        name = f"eventmonitor-audiolab-{datetime.now():%Y%m%d-%H%M%S}.emabackup"
        try:
            backup = create_backup(DB, backup_dir / name)
        except (OSError, ValueError) as error:
            st.error(str(error))
        else:
            st.session_state["latest-backup"] = str(backup)
    latest = st.session_state.get("latest-backup")
    if latest and Path(latest).is_file():
        st.download_button(
            "Sicherung herunterladen",
            Path(latest).read_bytes(),
            file_name=Path(latest).name,
            mime="application/zip",
        )

    st.subheader("Sicherung wiederherstellen / migrieren")
    upload = st.file_uploader("AudioLab-Sicherung auswählen", type=["emabackup", "zip"])
    confirmed = st.checkbox("Bestehende AudioLab-Daten durch diese Sicherung ersetzen")
    if st.button("Geprüft wiederherstellen", disabled=not (upload and confirmed)):
        with tempfile.NamedTemporaryFile(suffix=".emabackup", delete=False) as temporary:
            temporary.write(upload.getbuffer())
            restore_source = Path(temporary.name)
        try:
            conn.close()
            count, recovery = restore_backup(restore_source, DB, LIB)
        except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
            st.error(f"Wiederherstellung abgebrochen: {error}")
        else:
            st.success(
                f"{count} Aufnahmen wiederhergestellt. Rückfallkopie: {recovery or 'nicht nötig'}"
            )
            st.rerun()
        finally:
            restore_source.unlink(missing_ok=True)

elif page == "Ereignisse lernen":
    st.title("Ereignisse anhören und zuordnen")
    recs = conn.execute("SELECT * FROM recordings ORDER BY started_at DESC").fetchall()
    if not recs:
        st.info("Zuerst Messungen importieren.")
        st.stop()
    rec_map = {f"#{r['id']} | {r['started_at']} | {Path(r['audio_path']).name}": r for r in recs}
    rec = rec_map[st.selectbox("Aufnahme", list(rec_map))]
    only_open = st.checkbox("Nur unbestätigte Segmente", True)
    order = st.selectbox(
        "Reihenfolge",
        ["Active Learning", "Auffälligste zuerst", "Lauteste zuerst", "Chronologisch"],
    )
    order_sql = {
        "Auffälligste zuerst": "event_score DESC",
        "Lauteste zuerst": "peak_dba DESC",
        "Chronologisch": "start_seconds",
        "Active Learning": "COALESCE((SELECT active_learning_score FROM predictions p "
        "WHERE p.segment_id=segments.id ORDER BY p.created_at DESC,p.id DESC LIMIT 1),-1) DESC",
    }[order]
    sql = (
        "SELECT * FROM segments WHERE recording_id=?"
        + (" AND label IS NULL" if only_open else "")
        + f" ORDER BY {order_sql}"
    )
    segments = conn.execute(sql, (rec["id"],)).fetchall()
    if not segments:
        st.success("Für diese Auswahl sind keine Segmente offen.")
        st.stop()
    navigation_key = f"segment-position-{rec['id']}-{int(only_open)}-{order}"
    if navigation_key not in st.session_state:
        st.session_state[navigation_key] = 0
    st.session_state[navigation_key] = min(int(st.session_state[navigation_key]), len(segments) - 1)
    previous_column, position_column, next_column = st.columns([1, 2, 1])
    if previous_column.button(
        "← Vorheriges Segment", disabled=st.session_state[navigation_key] == 0
    ):
        st.session_state[navigation_key] -= 1
        st.rerun()
    if next_column.button(
        "Nächstes Segment →",
        disabled=st.session_state[navigation_key] >= len(segments) - 1,
    ):
        st.session_state[navigation_key] += 1
        st.rerun()
    pos = position_column.number_input(
        "Segmentposition",
        min_value=0,
        max_value=len(segments) - 1,
        step=1,
        key=navigation_key,
    )
    seg = segments[int(pos)]
    prediction = latest_prediction(conn, seg["id"])
    if prediction:
        review_status = (
            "bereits geprüft"
            if prediction["reviewed_at"]
            else "noch zu bestätigen oder zu korrigieren"
        )
        st.info(
            f"Modellvorschlag: **{prediction['predicted_label']}** "
            f"({float(prediction['confidence']):.1%}) · {review_status} · "
            f"Active-Learning-Priorität: "
            f"{format_metric(prediction['active_learning_score'])}"
        )
    st.subheader("Ereignis zuschneiden")
    boundary_start, boundary_end, boundary_actions = st.columns([2, 2, 2])
    start_seconds = boundary_start.number_input(
        "Start (s)",
        0.0,
        float(rec["duration_seconds"]),
        float(seg["start_seconds"]),
        0.1,
        key=f"segment-start-{seg['id']}",
    )
    end_seconds = boundary_end.number_input(
        "Ende (s)",
        0.0,
        float(rec["duration_seconds"]),
        float(seg["end_seconds"]),
        0.1,
        key=f"segment-end-{seg['id']}",
    )
    if boundary_actions.button("Grenzen speichern", key=f"save-boundaries-{seg['id']}"):
        try:
            update_boundaries(conn, seg["id"], start_seconds, end_seconds, rec["duration_seconds"])
        except ValueError as error:
            st.error(str(error))
        else:
            st.success("Segmentgrenzen und dB-Kennwerte wurden aktualisiert.")
            st.rerun()
    if boundary_actions.button("Auf Ursprung zurücksetzen", key=f"reset-boundaries-{seg['id']}"):
        update_boundaries(
            conn,
            seg["id"],
            seg["original_start_seconds"],
            seg["original_end_seconds"],
            rec["duration_seconds"],
        )
        st.rerun()
    before = st.slider("Vorlauf / Nachlauf in Sekunden", 0.0, 5.0, 2.0, 0.5)
    data, sr = sf.read(rec["audio_path"], always_2d=True)
    a = max(0, int((seg["start_seconds"] - before) * sr))
    b = min(len(data), int((seg["end_seconds"] + before) * sr))
    buf = io.BytesIO()
    sf.write(buf, data[a:b], sr, format="WAV", subtype="PCM_16")
    st.audio(buf.getvalue(), format="audio/wav")
    st.download_button(
        "Exakten Ereignisclip als WAV herunterladen",
        wav_excerpt(data, int(sr), seg["start_seconds"], seg["end_seconds"]),
        file_name=f"aufnahme-{rec['id']}-segment-{seg['id']}.wav",
        mime="audio/wav",
    )
    st.write(
        f"**Zeit:** {seg['start_seconds']:.1f}–{seg['end_seconds']:.1f}s · "
        f"**Peak:** {format_metric(seg['peak_dba'], ' dB(A)')} · "
        f"**Mittel:** {format_metric(seg['mean_dba'], ' dB(A)')} · "
        f"**Auffälligkeit:** {format_metric(seg['event_score'])}"
    )
    db_series = pd.read_sql_query(
        """
        SELECT offset_seconds, current_dba, max_dba, average_dba
        FROM db_samples WHERE recording_id=? ORDER BY offset_seconds
        """,
        conn,
        params=(rec["id"],),
    )
    st.subheader("Interaktiver dB-Verlauf")
    if db_series.empty:
        st.info("Für diese Aufnahme sind keine dB-Zeitwerte vorhanden.")
    else:
        st.vega_lite_chart(
            db_series,
            {
                "height": 260,
                "params": [
                    {
                        "name": "zoom",
                        "select": {"type": "interval", "encodings": ["x"]},
                        "bind": "scales",
                    }
                ],
                "layer": [
                    {
                        "mark": {"type": "line", "color": "#70e0ae"},
                        "encoding": {
                            "x": {
                                "field": "offset_seconds",
                                "type": "quantitative",
                                "title": "Zeit (s)",
                            },
                            "y": {
                                "field": "current_dba",
                                "type": "quantitative",
                                "title": "dB(A)",
                                "scale": {"zero": False},
                            },
                            "tooltip": [
                                {"field": "offset_seconds", "title": "Sekunde"},
                                {"field": "current_dba", "title": "Aktuell"},
                                {"field": "max_dba", "title": "Maximum"},
                                {"field": "average_dba", "title": "Mittel"},
                            ],
                        },
                    },
                    {
                        "data": {
                            "values": [
                                {
                                    "start": float(seg["start_seconds"]),
                                    "end": float(seg["end_seconds"]),
                                }
                            ]
                        },
                        "mark": {"type": "rect", "color": "#f6bd60", "opacity": 0.2},
                        "encoding": {
                            "x": {"field": "start", "type": "quantitative"},
                            "x2": {"field": "end"},
                        },
                    },
                ],
            },
            width="stretch",
        )

    st.subheader("Spektrogramm des Audioausschnitts")
    times, frequencies, power_db = calculate_spectrogram(data[a:b], int(sr))
    spectrum = spectrogram_records(times, frequencies, power_db, a / sr)
    if spectrum:
        st.vega_lite_chart(
            pd.DataFrame(spectrum),
            {
                "height": 300,
                "mark": "rect",
                "encoding": {
                    "x": {
                        "field": "time",
                        "type": "quantitative",
                        "title": "Zeit (s)",
                    },
                    "y": {
                        "field": "frequency",
                        "type": "quantitative",
                        "title": "Frequenz (Hz)",
                    },
                    "color": {
                        "field": "level",
                        "type": "quantitative",
                        "title": "relativer Pegel (dB)",
                        "scale": {"scheme": "viridis", "domain": [-100, 0]},
                    },
                    "tooltip": [
                        {"field": "time", "title": "Sekunde"},
                        {"field": "frequency", "title": "Hz"},
                        {"field": "level", "title": "dB relativ"},
                    ],
                },
            },
            width="stretch",
        )
    suggested_label = prediction["predicted_label"] if prediction else None
    selected_default = seg["label"] if seg["label"] in LABELS else suggested_label
    label = st.selectbox(
        "Lärmart", LABELS, index=LABELS.index(selected_default) if selected_default in LABELS else 0
    )
    confidence = st.slider("Sicherheit", 0.0, 1.0, float(seg["label_confidence"] or 1.0), 0.05)
    notes = st.text_input("Notiz", seg["notes"] or "")
    if st.button("Bestätigen und speichern", type="primary"):
        conn.execute(
            "UPDATE segments SET label=?,label_confidence=?,notes=?,labelled_at=? WHERE id=?",
            (label, confidence, notes, datetime.now().isoformat(), seg["id"]),
        )
        conn.commit()
        if prediction:
            record_prediction_review(conn, prediction["id"], label)
        st.success("Gespeichert.")
        st.rerun()

else:
    st.title("Auswertung")
    df = pd.read_sql_query(
        """
    SELECT
        r.started_at,
        s.start_seconds,
        s.end_seconds,
        s.peak_dba,
        s.mean_dba,
        s.label,
        s.label_confidence,
        s.notes
    FROM segments s
    JOIN recordings r ON r.id = s.recording_id
    WHERE s.label IS NOT NULL
    ORDER BY r.started_at, s.start_seconds
    """,
        conn,
    )
    if df.empty:
        st.info("Noch keine bestätigten Ereignisse.")
        st.stop()
    st.bar_chart(df["label"].value_counts())
    labels = st.multiselect(
        "Klassen filtern", sorted(df.label.unique()), default=sorted(df.label.unique())
    )
    out = df[df.label.isin(labels)].copy()
    st.dataframe(out, width="stretch")
    st.download_button(
        "Lärmprotokoll als CSV herunterladen",
        out.to_csv(index=False).encode("utf-8-sig"),
        "laermprotokoll.csv",
        "text/csv",
    )
