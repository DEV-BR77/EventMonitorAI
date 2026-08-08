from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.session import engine
from app.models import Event
from app.services.label_translation import translate_label


def add_missing_event_columns() -> None:
    inspector = inspect(engine)

    if "events" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("events")}

    statements: list[str] = []

    if "label_de" not in column_names:
        statements.append("ALTER TABLE events " "ADD COLUMN label_de VARCHAR NOT NULL DEFAULT ''")

    if "category" not in column_names:
        statements.append(
            "ALTER TABLE events " "ADD COLUMN category VARCHAR NOT NULL DEFAULT 'OTHER'"
        )

    if "end_timestamp" not in column_names:
        statements.append("ALTER TABLE events " "ADD COLUMN end_timestamp VARCHAR")

    if "duration_seconds" not in column_names:
        statements.append(
            "ALTER TABLE events " "ADD COLUMN duration_seconds FLOAT NOT NULL DEFAULT 0.975"
        )

    if "avg_db_level" not in column_names:
        statements.append("ALTER TABLE events " "ADD COLUMN avg_db_level FLOAT")

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def ensure_telemetry_counter_capacity() -> None:
    if engine.dialect.name != "postgresql":
        return
    inspector = inspect(engine)
    if "device_telemetry" not in inspector.get_table_names():
        return
    with engine.begin() as connection:
        for column in ("uptime_ms", "packets_received", "packets_lost"):
            connection.execute(
                text(f"ALTER TABLE device_telemetry ALTER COLUMN {column} TYPE BIGINT")
            )


def backfill_events() -> None:
    with Session(engine) as db:
        events = list(db.scalars(select(Event)).all())
        changed = False

        for event in events:
            translated_label, translated_category = translate_label(
                event.label,
                event.device,
            )

            if event.label_de != translated_label or event.category != translated_category:
                event.label_de = translated_label
                event.category = translated_category
                changed = True

            if event.end_timestamp is None:
                event.end_timestamp = event.timestamp
                changed = True

            if event.duration_seconds is None:
                event.duration_seconds = 0.975
                changed = True

            if event.avg_db_level is None:
                event.avg_db_level = event.db_level
                changed = True

        if changed:
            db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_telemetry_counter_capacity()
    add_missing_event_columns()
    backfill_events()
