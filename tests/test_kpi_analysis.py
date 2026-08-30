from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from app.api.dashboard import export_kpis, noise_kpis
from app.database.base import Base
from app.models.event import Event
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]


def _event(timestamp: str, category: str, level: float, average: float, label: str) -> Event:
    return Event(
        timestamp=timestamp,
        event_type="AUDIO",
        label=label,
        label_de=label,
        category=category,
        confidence=0.9,
        db_level=level,
        avg_db_level=average,
        duration_seconds=2.5,
        device="hof",
        primary_class_code=category,
    )


def test_kpis_filter_local_hours_and_category_and_aggregate_mean_levels() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                _event("2026-08-11T06:15:00+00:00", "VOICE", 61, 54, "Rufen"),
                _event("2026-08-11T06:45:00+00:00", "VEHICLE", 70, 63, "Pkw"),
                _event("2026-08-11T10:15:00+00:00", "VOICE", 66, 59, "Schreien"),
            ]
        )
        db.commit()

        result = noise_kpis(
            db,
            SimpleNamespace(),
            days=1,
            device="hof",
            date_from=date(2026, 8, 11),
            date_to=date(2026, 8, 11),
            start_hour=8,
            end_hour=10,
            category="VOICE",
        )

        assert result["total"] == 1
        assert result["average_db"] == 54
        assert result["maximum_db"] == 61
        assert result["hours"] == [
            {
                "hour": 8,
                "count": 1,
                "exceeded": 1,
                "average_db": 54.0,
                "maximum_db": 61.0,
                "duration_seconds": 2.5,
                "share": 1.0,
            },
            {
                "hour": 9,
                "count": 0,
                "exceeded": 0,
                "average_db": 0,
                "maximum_db": 0,
                "duration_seconds": 0,
                "share": 0.0,
            },
        ]
        assert {item["code"] for item in result["available_categories"]} == {
            "VEHICLE",
            "VOICE",
        }


def test_kpi_exports_contain_only_selected_events_and_valid_xlsx() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                _event("2026-08-11T06:15:00+00:00", "VOICE", 61, 54, "Rufen"),
                _event("2026-08-11T06:45:00+00:00", "VEHICLE", 70, 63, "Pkw"),
            ]
        )
        db.commit()
        common = dict(
            days=1,
            device="hof",
            date_from=date(2026, 8, 11),
            date_to=date(2026, 8, 11),
            start_hour=8,
            end_hour=9,
            category="VOICE",
        )

        csv_response = export_kpis(db, SimpleNamespace(), file_format="csv", **common)
        csv_text = csv_response.body.decode("utf-8-sig")
        assert "Rufen" in csv_text
        assert "Pkw" not in csv_text
        assert "Durchschnitt dB(A)" in csv_text

        xlsx_response = export_kpis(db, SimpleNamespace(), file_format="xlsx", **common)
        with ZipFile(BytesIO(xlsx_response.body)) as workbook:
            assert "xl/worksheets/sheet1.xml" in workbook.namelist()
            assert "xl/worksheets/sheet2.xml" in workbook.namelist()
            assert "Rufen" in workbook.read("xl/worksheets/sheet2.xml").decode()
            assert "Pkw" not in workbook.read("xl/worksheets/sheet2.xml").decode()


def test_dashboard_exposes_flexible_kpi_filters_charts_and_exports() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    for element_id in (
        "kpi-date-from",
        "kpi-date-to",
        "kpi-hour-from",
        "kpi-hour-to",
        "kpi-category",
        "kpi-level-timeline",
        "kpi-event-timeline",
        "kpi-hour-share",
        "kpi-export-csv",
        "kpi-export-xlsx",
    ):
        assert f'id="{element_id}"' in html
    assert 'query.set("category", $("#kpi-category").value)' in javascript
    assert 'start_hour: $("#kpi-hour-from").value' in javascript
    assert "/api/kpis/export?format=${format}" in javascript
