from __future__ import annotations

import csv
import html
import io
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from eventmonitor.cases import verify_case_history

STATUS_LABELS = {"draft": "Entwurf", "confirmed": "Bestätigt", "rejected": "Abgelehnt"}
CSV_FIELDS = [
    "Case-ID",
    "Case-Titel",
    "Status",
    "Case-Beginn",
    "Case-Ende",
    "Case-Dauer (s)",
    "Notizen",
    "Historie intakt",
    "Ereignis-ID",
    "Position",
    "Kategorie",
    "Primärklasse-Code",
    "Unterklasse-Code",
    "Zuordnungsstatus",
    "Familie",
    "Ereignis-Beginn (s)",
    "Ereignis-Ende (s)",
    "Ereignis-Dauer (s)",
    "Segmente",
    "Peak dB(A)",
    "Mittel dB(A)",
    "Personen",
]


def noise_log_rows(conn: Any, confirmed_only: bool = True) -> list[dict[str, Any]]:
    condition = "WHERE c.status='confirmed'" if confirmed_only else ""
    rows = conn.execute(
        f"""
        SELECT c.id AS case_id,c.title,c.status,c.started_at,c.ended_at,
               c.duration_seconds AS case_duration,c.notes,ce.position,
               e.id AS event_id,e.primary_label,e.event_family,e.start_seconds,
               e.end_seconds,e.segment_count,e.peak_dba,e.mean_dba,
               MAX(s.base_class_code) AS base_class_code,
               MAX(s.fine_class_code) AS fine_class_code,
               MAX(s.assignment_status) AS assignment_status,
               GROUP_CONCAT(DISTINCT p.name) AS persons
        FROM cases c JOIN case_events ce ON ce.case_id=c.id
        JOIN events e ON e.id=ce.event_id
        LEFT JOIN event_segments es ON es.event_id=e.id
        LEFT JOIN segments s ON s.id=es.segment_id
        LEFT JOIN segment_person_assignments spa ON spa.segment_id=es.segment_id
             AND spa.confirmed=1
        LEFT JOIN persons p ON p.id=spa.person_id
        {condition}
        GROUP BY c.id,ce.position,e.id
        ORDER BY c.started_at,c.id,ce.position
        """
    ).fetchall()
    integrity = {row["case_id"]: verify_case_history(conn, row["case_id"]) for row in rows}
    return [
        {
            "Case-ID": row["case_id"],
            "Case-Titel": row["title"],
            "Status": STATUS_LABELS.get(row["status"], row["status"]),
            "Case-Beginn": row["started_at"],
            "Case-Ende": row["ended_at"],
            "Case-Dauer (s)": round(float(row["case_duration"]), 3),
            "Notizen": row["notes"] or "",
            "Historie intakt": "Ja" if integrity[row["case_id"]] else "Nein",
            "Ereignis-ID": row["event_id"],
            "Position": row["position"] + 1,
            "Kategorie": row["primary_label"],
            "Primärklasse-Code": row["base_class_code"] or "",
            "Unterklasse-Code": row["fine_class_code"] or "",
            "Zuordnungsstatus": row["assignment_status"] or "automatic",
            "Familie": row["event_family"],
            "Ereignis-Beginn (s)": row["start_seconds"],
            "Ereignis-Ende (s)": row["end_seconds"],
            "Ereignis-Dauer (s)": round(float(row["end_seconds"] - row["start_seconds"]), 3),
            "Segmente": row["segment_count"],
            "Peak dB(A)": row["peak_dba"],
            "Mittel dB(A)": row["mean_dba"],
            "Personen": row["persons"] or "",
        }
        for row in rows
    ]


def _csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def build_noise_log_csv(conn: Any, confirmed_only: bool = True) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, delimiter=";", lineterminator="\r\n")
    writer.writeheader()
    for row in noise_log_rows(conn, confirmed_only):
        writer.writerow({key: _csv_safe(value) for key, value in row.items()})
    return output.getvalue().encode("utf-8-sig")


def _footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(15 * mm, 12 * mm, landscape(A4)[0] - 15 * mm, 12 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawString(15 * mm, 7 * mm, "EventMonitorAI - lokales Lärmprotokoll")
    canvas.drawRightString(landscape(A4)[0] - 15 * mm, 7 * mm, f"Seite {document.page}")
    canvas.restoreState()


def _text(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def build_noise_log_pdf(conn: Any, confirmed_only: bool = True) -> bytes:
    rows = noise_log_rows(conn, confirmed_only)
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["Case-ID"])].append(row)
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=18 * mm,
        title="EventMonitorAI Lärmprotokoll",
        author="EventMonitorAI",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0F172A"),
        alignment=TA_CENTER,
        spaceAfter=6 * mm,
    )
    heading = ParagraphStyle(
        "CaseHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.HexColor("#0F766E"),
        spaceBefore=3 * mm,
        spaceAfter=2 * mm,
    )
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("Small", parent=body, fontSize=7.5, leading=9)
    story = [
        Paragraph("EventMonitorAI Lärmprotokoll", title_style),
        Paragraph(
            f"Erstellt: {datetime.now(UTC).isoformat(timespec='seconds')} UTC | "
            f"Filter: {'nur bestätigte Cases' if confirmed_only else 'alle Cases'} | "
            f"Cases: {len(grouped)} | Teilereignisse: {len(rows)}",
            ParagraphStyle("Summary", parent=body, alignment=TA_CENTER),
        ),
        Spacer(1, 6 * mm),
    ]
    if not grouped:
        story.append(Paragraph("Keine passenden Cases vorhanden.", body))
    for case_index, (case_id, case_rows) in enumerate(grouped.items()):
        first = case_rows[0]
        if case_index:
            story.append(PageBreak())
        story.append(Paragraph(f"Case #{case_id}: {_text(first['Case-Titel'])}", heading))
        metadata = [
            ["Status", "Beginn", "Ende", "Dauer", "Historie"],
            [
                _text(first["Status"]),
                _text(first["Case-Beginn"]),
                _text(first["Case-Ende"]),
                f"{first['Case-Dauer (s)']:.1f} s",
                _text(first["Historie intakt"]),
            ],
        ]
        metadata_table = Table(metadata, colWidths=[35 * mm, 58 * mm, 58 * mm, 30 * mm, 32 * mm])
        metadata_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94A3B8")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.extend([metadata_table, Spacer(1, 3 * mm)])
        if first["Notizen"]:
            story.extend(
                [
                    Paragraph(
                        "Notizen",
                        ParagraphStyle("NoteHead", parent=body, fontName="Helvetica-Bold"),
                    ),
                    Paragraph(_text(first["Notizen"]), body),
                    Spacer(1, 3 * mm),
                ]
            )
        table_data = [
            [
                "Pos.",
                "Ereignis",
                "Kategorie",
                "Zeitbereich",
                "Dauer",
                "Seg.",
                "Peak",
                "Mittel",
                "Personen",
            ]
        ]
        for row in case_rows:
            table_data.append(
                [
                    row["Position"],
                    f"#{row['Ereignis-ID']}",
                    Paragraph(_text(row["Kategorie"]), small),
                    f"{row['Ereignis-Beginn (s)']:.1f} - {row['Ereignis-Ende (s)']:.1f} s",
                    f"{row['Ereignis-Dauer (s)']:.1f} s",
                    row["Segmente"],
                    "-" if row["Peak dB(A)"] is None else f"{row['Peak dB(A)']:.1f}",
                    "-" if row["Mittel dB(A)"] is None else f"{row['Mittel dB(A)']:.1f}",
                    Paragraph(_text(row["Personen"]), small),
                ]
            )
        event_table = Table(
            table_data,
            repeatRows=1,
            colWidths=[
                12 * mm,
                18 * mm,
                45 * mm,
                42 * mm,
                22 * mm,
                14 * mm,
                18 * mm,
                18 * mm,
                43 * mm,
            ],
        )
        event_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.2),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F8FAFC")],
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ]
            )
        )
        story.append(event_table)
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()
