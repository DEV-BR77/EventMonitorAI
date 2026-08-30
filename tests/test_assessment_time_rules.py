from pathlib import Path

import pytest
from app.schemas.dashboard import AssessmentConfigWrite
from app.services.noise_assessment import assessment_for
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def test_custom_reference_and_sensitive_periods_drive_assessment() -> None:
    reference_rules = [
        {"name": "Nacht", "start_time": "00:00", "end_time": "08:00", "reference_db": 40},
        {"name": "Tag", "start_time": "08:00", "end_time": "00:00", "reference_db": 55},
    ]
    sensitive_periods = [
        {
            "name": "Abendruhe",
            "start_time": "20:00",
            "end_time": "22:00",
            "weekdays": [0, 1, 2, 3, 4, 5, 6],
            "include_holidays": True,
        }
    ]

    daytime = assessment_for(
        "2026-08-31T18:30:00+02:00", 54, 6, True, reference_rules, sensitive_periods
    )
    evening = assessment_for(
        "2026-08-31T20:30:00+02:00", 50, 6, True, reference_rules, sensitive_periods
    )

    assert daytime["reference_db"] == 55
    assert daytime["exceeded"] is False
    assert evening["reference_db"] == 55
    assert evening["assessed_db"] == 56
    assert evening["exceeded"] is True


def test_reference_rules_must_cover_each_minute_exactly_once() -> None:
    with pytest.raises(ValidationError, match="lückenlos"):
        AssessmentConfigWrite(
            sensitive_surcharge_db=6,
            apply_to_live=True,
            reference_rules=[
                {
                    "name": "Nur morgens",
                    "start_time": "06:00",
                    "end_time": "12:00",
                    "reference_db": 50,
                }
            ],
            sensitive_periods=[],
        )


def test_dashboard_exposes_time_rules_class_filter_and_scaled_db_chart() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'data-view="assessment"' in html
    assert 'id="assessment-reference-rules"' in html
    assert 'id="assessment-sensitive-periods"' in html
    assert 'id="kpi-class-filter"' in html
    assert 'id="kpi-quiet-gap"' in html
    assert "readAssessmentTimeRules" in javascript
    assert "minimum: 30, paddedMaximum: true" in javascript
    assert "Math.min(24, data.length)" in javascript
