from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_navigation_is_grouped_and_renamed() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    admin_start = html.index('id="admin-navigation"')
    admin_end = html.index("</div>", admin_start)
    admin_navigation = html[admin_start:admin_end]

    assert 'data-view="devices" data-short="A">Audioeinstellungen' in admin_navigation
    assert 'data-view="people" data-short="P">Personen' in admin_navigation
    assert 'data-view="review" data-short="L">Lernregeln' in admin_navigation
    assert 'data-view="user-management"' in admin_navigation
    assert 'data-view="live-sound-access"' in admin_navigation
    assert '<span>Beta</span>' in html
    assert 'data-view="image-evidence"' in html
    assert 'data-view="documents"' in html


def test_admin_navigation_and_data_are_role_guarded() -> None:
    javascript = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert '$("#admin-navigation").classList.toggle("hidden", me.role !== "admin")' in javascript
    assert 'button.closest("#admin-navigation") && state.role !== "admin"' in javascript
    assert '"user-management": [loadUsers]' in javascript
    assert '"live-sound-access": [loadAudioPermissions]' in javascript
    assert 'devices: [loadTelemetry, loadCalibrations, loadCalibrationReferenceRuns]' in javascript
    assert 'people: [loadPeople, loadSpeakerClusters, loadSpeakerAnalysisProgress]' in javascript
    assert 'review: [loadReview]' in javascript


def test_admin_content_is_split_into_dedicated_views() -> None:
    javascript = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    for line in (
        '$("#user-management").append($("#user-management-content"));',
        '$("#live-sound-access").append($("#audio-permissions"));',
        '$("#tenant-management-view").append($("#tenant-management"));',
        '$("#website-access").append($("#website-analytics"));',
        '$("#class-management-view").append($("#class-management-content"));',
    ):
        assert line in javascript


def test_person_analysis_is_separate_from_live_event_classification() -> None:
    javascript = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert 'data-live-person-event="${eventId}"' not in javascript
    assert html.index('id="people"') < html.index('id="speaker-analyze"')
    assert "/api/speaker-analysis/runs/latest" in javascript
    assert "if (me.role !== \"viewer\") await loadPeople();" in javascript
