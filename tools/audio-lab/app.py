from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import soundfile as sf
import streamlit as st
from eventmonitor.backup import create_backup, restore_backup
from eventmonitor.cases import (
    case_events,
    case_history,
    create_case,
    ensure_case_histories,
    update_case,
    verify_case_history,
)
from eventmonitor.db import connect
from eventmonitor.embeddings import generate_segment_embeddings, similar_segments
from eventmonitor.events import EVENT_GROUPING_VERSION, rebuild_events
from eventmonitor.features import FeaturePipelineConfig
from eventmonitor.importer import import_folder, import_package, resume_imports
from eventmonitor.inference import (
    generate_segment_predictions,
    latest_prediction,
    record_prediction_review,
)
from eventmonitor.model_registry import (
    activate_model,
    active_model,
    archive_model,
    list_models,
    register_model,
    rollback_model,
)
from eventmonitor.people import (
    assign_person,
    create_person,
    current_assignment,
    person_statistics,
    rename_person,
    set_person_active,
    suggest_person,
)
from eventmonitor.reports import build_noise_log_csv, build_noise_log_pdf
from eventmonitor.segments import update_boundaries, wav_excerpt
from eventmonitor.taxonomy import active_class_names, sync_class_definitions
from eventmonitor.training import build_labeled_dataset, load_model, save_model, train_baseline
from eventmonitor.visualization import calculate_spectrogram, spectrogram_records

st.set_page_config(page_title="EventMonitor AudioLab", page_icon="🎧", layout="wide")
DB = Path("data/eventmonitor.sqlite3")
LIB = Path("data/library")
INBOX = Path("data/inbox")


def format_metric(value: float | None, suffix: str = "") -> str:
    return f"{float(value):.1f}{suffix}" if value is not None else "–"


conn = connect(DB)
LABELS = active_class_names(conn)
ensure_case_histories(conn)
page = st.sidebar.radio(
    "Bereich",
    [
        "Übersicht",
        "Import",
        "Ereignisse lernen",
        "Ereignisse",
        "Auswertung",
        "Personen",
        "Klassen",
        "Modelltraining",
        "Sicherung",
    ],
)

if page == "Klassen":
    st.title("Gemeinsamer Klassenkatalog")
    st.caption(
        "Die Taxonomie wird vom EventMonitorAI-Dashboard verwaltet "
        "und hier explizit synchronisiert."
    )
    class_rows = conn.execute(
        """
        SELECT code,name,level,parent_code,active,trainable,synced_at
        FROM event_classes ORDER BY sort_order,name
        """
    ).fetchall()
    st.dataframe(pd.DataFrame([dict(row) for row in class_rows]), width="stretch")
    with st.form("class-sync"):
        dashboard_url = st.text_input("Dashboard-URL", "https://dashboard.eventmonitor.eu")
        username = st.text_input("Benutzername")
        password = st.text_input("Passwort", type="password")
        synchronize = st.form_submit_button("Klassen vom Dashboard synchronisieren")
    if synchronize:
        try:
            base_url = dashboard_url.rstrip("/")
            login_response = requests.post(
                f"{base_url}/auth/login",
                json={"username": username, "password": password},
                timeout=10,
            )
            login_response.raise_for_status()
            token = login_response.json()["access_token"]
            class_response = requests.get(
                f"{base_url}/api/event-classes",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            class_response.raise_for_status()
            count = sync_class_definitions(conn, class_response.json())
            st.success(f"{count} Klassen synchronisiert.")
            st.rerun()
        except (requests.RequestException, KeyError, ValueError) as error:
            st.error(f"Synchronisierung fehlgeschlagen: {error}")

elif page == "Import":
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

elif page == "Ereignisse":
    st.title("Zusammenhängende Ereignisse")
    st.caption(
        f"Gruppierungsversion {EVENT_GROUPING_VERSION}: Rufen/Schreien bis 3,0 s Abstand, "
        "Impulse bis 1,5 s und gleiche sonstige Klassen bis 1,0 s."
    )
    if st.button("Ereignisse aus bestätigten Segmenten neu aufbauen", type="primary"):
        count = rebuild_events(conn)
        st.success(f"{count} zusammenhängende Ereignisse erzeugt.")
    events = pd.read_sql_query(
        """
        SELECT e.id,r.started_at,e.start_seconds,e.end_seconds,
               ROUND(e.end_seconds-e.start_seconds,3) AS duration_seconds,
               e.primary_label,e.event_family,e.segment_count,e.peak_dba,e.mean_dba,
               e.grouping_version
        FROM events e JOIN recordings r ON r.id=e.recording_id
        ORDER BY r.started_at,e.start_seconds
        """,
        conn,
    )
    if events.empty:
        st.info("Noch keine Ereignisse aufgebaut.")
    else:
        metrics = st.columns(4)
        metrics[0].metric("Ereignisse", len(events))
        metrics[1].metric("Verknüpfte Segmente", int(events.segment_count.sum()))
        metrics[2].metric("Rufen / Schreien", int((events.event_family == "voice").sum()))
        metrics[3].metric("Impulsgruppen", int((events.event_family == "impulse").sum()))
        st.dataframe(events, width="stretch", hide_index=True)
    st.subheader("Case aus Ereignissen erstellen")
    available_events = conn.execute(
        """
        SELECT e.id,e.primary_label,e.start_seconds,r.started_at
        FROM events e JOIN recordings r ON r.id=e.recording_id
        WHERE NOT EXISTS (SELECT 1 FROM case_events ce WHERE ce.event_id=e.id)
        ORDER BY r.started_at,e.start_seconds
        """
    ).fetchall()
    event_options = {
        f"#{row['id']} · {row['started_at']} + {row['start_seconds']:.1f}s · "
        f"{row['primary_label']}": row["id"]
        for row in available_events
    }
    case_title = st.text_input("Case-Titel")
    case_actor = st.text_input("Bearbeiter", value="Administrator", key="create-case-actor")
    case_reason = st.text_input("Begründung", value="Case aus ausgewählten Ereignissen erstellt")
    selected_events = st.multiselect("Teilereignisse", list(event_options))
    if st.button("Case erstellen", disabled=not (case_title and selected_events), type="primary"):
        try:
            case_id = create_case(
                conn,
                case_title,
                [event_options[label] for label in selected_events],
                actor=case_actor,
                reason=case_reason,
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.success(f"Case #{case_id} erstellt.")
            st.rerun()
    cases = conn.execute("SELECT * FROM cases ORDER BY started_at DESC,id DESC").fetchall()
    st.subheader("Cases")
    if cases:
        case_frame = pd.DataFrame([dict(row) for row in cases])
        st.dataframe(
            case_frame[["id", "title", "started_at", "ended_at", "duration_seconds", "status"]],
            width="stretch",
            hide_index=True,
        )
        case_map = {f"#{row['id']} · {row['title']}": row for row in cases}
        selected_case = case_map[st.selectbox("Case-Details", list(case_map))]
        subevents = pd.DataFrame([dict(row) for row in case_events(conn, selected_case["id"])])
        st.dataframe(subevents, width="stretch", hide_index=True)
        st.subheader("Case bearbeiten")
        edited_title = st.text_input(
            "Titel", selected_case["title"], key=f"case-title-{selected_case['id']}"
        )
        edited_notes = st.text_area(
            "Notizen", selected_case["notes"] or "", key=f"case-notes-{selected_case['id']}"
        )
        status_labels = {
            "Entwurf": "draft",
            "Bestätigt": "confirmed",
            "Abgelehnt": "rejected",
        }
        current_status_label = next(
            label for label, value in status_labels.items() if value == selected_case["status"]
        )
        edited_status_label = st.selectbox(
            "Bestätigungsstatus",
            list(status_labels),
            index=list(status_labels).index(current_status_label),
        )
        editor = st.text_input("Bearbeiter der Änderung", value="Administrator")
        edit_reason = st.text_input("Änderungsbegründung")
        if st.button("Case-Änderung revisionssicher speichern", disabled=not edit_reason):
            try:
                update_case(
                    conn,
                    selected_case["id"],
                    title=edited_title,
                    notes=edited_notes,
                    status=status_labels[edited_status_label],
                    actor=editor,
                    reason=edit_reason,
                )
            except ValueError as error:
                st.error(str(error))
            else:
                st.rerun()
        history = case_history(conn, selected_case["id"])
        integrity = verify_case_history(conn, selected_case["id"])
        st.subheader("Änderungshistorie")
        if integrity:
            st.success("Hash-Kette vollständig und gültig.")
        else:
            st.error("Integritätsprüfung der Änderungshistorie fehlgeschlagen.")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "revision": row["revision_number"],
                        "action": row["action"],
                        "actor": row["actor"],
                        "reason": row["reason"],
                        "created_at": row["created_at"],
                        "hash": row["revision_hash"],
                    }
                    for row in history
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Noch keine Cases vorhanden.")
    st.subheader("Lärmprotokoll exportieren")
    include_unconfirmed = st.checkbox("Entwürfe und abgelehnte Cases mit exportieren")
    export_columns = st.columns(2)
    export_columns[0].download_button(
        "Lärmprotokoll als CSV",
        build_noise_log_csv(conn, confirmed_only=not include_unconfirmed),
        file_name="eventmonitor-laermprotokoll.csv",
        mime="text/csv",
    )
    export_columns[1].download_button(
        "Lärmprotokoll als PDF",
        build_noise_log_pdf(conn, confirmed_only=not include_unconfirmed),
        file_name="eventmonitor-laermprotokoll.pdf",
        mime="application/pdf",
    )

elif page == "Personen":
    st.title("Personenverwaltung und Statistik")
    new_name = st.text_input("Neue Person")
    if st.button("Person anlegen", disabled=not new_name):
        try:
            create_person(conn, new_name)
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()
    persons = conn.execute("SELECT * FROM persons ORDER BY active DESC,name").fetchall()
    if persons:
        person_map = {f"#{row['id']} · {row['name']}": row for row in persons}
        selected = person_map[st.selectbox("Person bearbeiten", list(person_map))]
        edited_name = st.text_input("Anzeigename", selected["name"])
        active = st.checkbox("Aktiv", bool(selected["active"]))
        if st.button("Änderungen speichern"):
            try:
                rename_person(conn, selected["id"], edited_name)
                set_person_active(conn, selected["id"], active)
            except ValueError as error:
                st.error(str(error))
            else:
                st.rerun()
    else:
        st.info("Noch keine Personen angelegt.")
    statistics = person_statistics(conn)
    st.subheader("Statistik nach Person, Beurteilungszeit und Lärmkategorie")
    if statistics:
        frame = pd.DataFrame(statistics)
        frame["duration_seconds"] = frame["duration_seconds"].round(1)
        st.dataframe(frame, width="stretch", hide_index=True)
    else:
        st.info("Noch keine bestätigten Personenzuordnungen vorhanden.")

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
                model_id = register_model(conn, model_path, artifact)
                if active_model(conn) is None:
                    activate_model(conn, model_id, reason="initial")
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
    models = sorted(
        (path.resolve() for path in Path("models/audio-lab").glob("*.joblib")), reverse=True
    )
    for existing_model in models:
        try:
            register_model(conn, existing_model, load_model(existing_model))
        except (OSError, ValueError):
            st.warning(f"Ungültiges Modellartefakt übersprungen: {existing_model.name}")
    registered_models = list_models(conn)
    st.subheader("Lokale Modellverwaltung")
    if registered_models:
        registry_frame = pd.DataFrame([dict(row) for row in registered_models])
        registry_frame["test_macro_f1"] = registry_frame["metrics_json"].map(
            lambda payload: json.loads(payload).get("test", {}).get("macro_f1")
        )
        st.dataframe(
            registry_frame[
                ["id", "name", "artifact_version", "status", "test_macro_f1", "activated_at"]
            ],
            width="stretch",
            hide_index=True,
        )
        registry_map = {
            f"#{row['id']} · {row['name']} · {row['status']}": row for row in registered_models
        }
        managed_model = registry_map[st.selectbox("Modellversion verwalten", list(registry_map))]
        activate_column, archive_column, rollback_column = st.columns(3)
        if activate_column.button("Als aktives Modell verwenden"):
            try:
                activate_model(conn, managed_model["id"])
            except (OSError, ValueError) as error:
                st.error(str(error))
            else:
                st.rerun()
        if archive_column.button(
            "Modell archivieren", disabled=managed_model["status"] == "active"
        ):
            archive_model(conn, managed_model["id"])
            st.rerun()
        if rollback_column.button("Auf vorheriges Modell zurückrollen"):
            try:
                rollback_model(conn)
            except (OSError, ValueError) as error:
                st.error(str(error))
            else:
                st.rerun()
    else:
        st.info("Noch keine Modellversion registriert.")
    st.subheader("Modellvorschläge")
    if models:
        current = active_model(conn)
        active_path = Path(current["artifact_path"]) if current else None
        default_model = models.index(active_path) if active_path in models else 0
        selected_model = st.selectbox(
            "Lokales Modell", models, index=default_model, format_func=lambda path: path.name
        )
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
        if st.button("Audio-Embeddings für Ähnlichkeitssuche berechnen"):
            try:
                with st.spinner("Audio-Embeddings berechnen …"):
                    count = generate_segment_embeddings(
                        conn, load_model(selected_model), selected_model.name
                    )
            except (OSError, ValueError) as error:
                st.error(str(error))
            else:
                st.success(f"{count} Segment-Embeddings gespeichert.")
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
    person_assignment = current_assignment(conn, seg["id"])
    person_suggestion = suggest_person(conn, seg["id"])
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
    neighbours = similar_segments(conn, seg["id"], limit=5)
    if neighbours:
        with st.expander("Ähnliche Audioereignisse"):
            similarity_frame = pd.DataFrame(neighbours)
            similarity_frame["similarity"] = similarity_frame["similarity"].map(
                lambda value: f"{value:.1%}"
            )
            st.dataframe(similarity_frame, width="stretch", hide_index=True)
    if person_suggestion and not person_assignment:
        st.info(
            f"Personenvorschlag: **{person_suggestion['name']}** "
            f"(Embedding-Ähnlichkeit {person_suggestion['similarity']:.1%})"
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
    class_rows = conn.execute(
        """
        SELECT code,name,level,parent_code FROM event_classes
        WHERE active=1 ORDER BY sort_order,name
        """
    ).fetchall()
    class_by_code = {row["code"]: row for row in class_rows}
    class_by_name = {row["name"]: row for row in class_rows}
    bases = [row for row in class_rows if row["level"] == "base"]
    suggested_label = prediction["predicted_label"] if prediction else None
    selected_row = class_by_code.get(seg["base_class_code"]) or class_by_name.get(
        seg["label"] or suggested_label
    )
    if selected_row and selected_row["level"] == "fine":
        selected_row = class_by_code.get(selected_row["parent_code"])
    base_names = [row["name"] for row in bases]
    primary_name = st.selectbox(
        "Automatische Basisklasse",
        base_names,
        index=base_names.index(selected_row["name"]) if selected_row else 0,
    )
    primary = class_by_name[primary_name]
    fine_rows = [
        row
        for row in class_rows
        if row["level"] == "fine" and row["parent_code"] in (None, primary["code"])
    ]
    fine_names = ["Keine Feinzuordnung", *(row["name"] for row in fine_rows)]
    selected_fine = class_by_code.get(seg["fine_class_code"])
    if selected_fine is None and seg["label"] in class_by_name:
        candidate = class_by_name[seg["label"]]
        selected_fine = candidate if candidate["level"] == "fine" else None
    fine_name = st.selectbox(
        "Manuelle Feinzuordnung",
        fine_names,
        index=fine_names.index(selected_fine["name"]) if selected_fine else 0,
    )
    fine = class_by_name.get(fine_name)
    label = fine["name"] if fine else primary["name"]
    active_people = conn.execute(
        "SELECT id,name FROM persons WHERE active=1 ORDER BY name"
    ).fetchall()
    person_options = {"Keine Person": None} | {row["name"]: row["id"] for row in active_people}
    default_person_id = (
        person_assignment["person_id"]
        if person_assignment
        else person_suggestion["person_id"] if person_suggestion else None
    )
    default_person_name = next(
        (name for name, person_id in person_options.items() if person_id == default_person_id),
        "Keine Person",
    )
    selected_person_name = st.selectbox(
        "Zugeordnete Person (optional)",
        list(person_options),
        index=list(person_options).index(default_person_name),
    )
    confidence = st.slider("Sicherheit", 0.0, 1.0, float(seg["label_confidence"] or 1.0), 0.05)
    notes = st.text_input("Notiz", seg["notes"] or "")
    if st.button("Bestätigen und speichern", type="primary"):
        conn.execute(
            """
            UPDATE segments SET
                label=?,base_class_code=?,fine_class_code=?,assignment_status='manual',
                label_confidence=?,notes=?,labelled_at=?
            WHERE id=?
            """,
            (
                label,
                primary["code"],
                fine["code"] if fine else None,
                confidence,
                notes,
                datetime.now().isoformat(),
                seg["id"],
            ),
        )
        conn.commit()
        if prediction:
            record_prediction_review(conn, prediction["id"], label)
        selected_person_id = person_options[selected_person_name]
        source = (
            "model_confirmed"
            if person_suggestion and selected_person_id == person_suggestion["person_id"]
            else "manual"
        )
        assign_person(
            conn,
            seg["id"],
            selected_person_id,
            source=source,
            confidence=person_suggestion["similarity"] if source == "model_confirmed" else 1.0,
        )
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
