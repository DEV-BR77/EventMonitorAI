from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_microphones_and_audio_lab_are_grouped_under_admin_navigation() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    admin_start = html.index('id="admin-navigation"')
    admin_end = html.index("</div>", admin_start)
    admin_navigation = html[admin_start:admin_end]

    assert 'data-view="devices">Mikrofone' in admin_navigation
    assert 'data-view="people">Personen' in admin_navigation
    assert 'data-view="review">Audio-Lab' in admin_navigation


def test_admin_navigation_and_data_are_role_guarded() -> None:
    javascript = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert '$("#admin-navigation").classList.toggle("hidden", me.role !== "admin")' in javascript
    assert 'button.closest("#admin-navigation") && state.role !== "admin"' in javascript
    assert '...(me.role === "admin" ? [loadAdminNotifications(), loadTelemetry(), loadCalibrations(), loadCalibrationReferenceRuns(), loadReview()' in javascript


def test_person_analysis_is_separate_from_live_event_classification() -> None:
    javascript = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert 'data-live-person-event="${eventId}"' not in javascript
    assert html.index('id="people"') < html.index('id="speaker-analyze"')
    assert "/api/speaker-analysis/runs/latest" in javascript
    assert "if (me.role !== \"viewer\") await loadPeople();" in javascript
