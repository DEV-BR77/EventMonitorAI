from sqlalchemy import inspect, or_, select, text
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.session import engine
from app.models import Event
from app.services.label_translation import translate_label


def add_missing_event_columns() -> None:
    inspector = inspect(engine)

    if "events" not in inspector.get_table_names():
        return

    column_names = {
        column["name"]
        for column in inspector.get_columns("events")
    }

    statements: list[str] = []

    if "label_de" not in column_names:
        statements.append(
            "ALTER TABLE events "
            "ADD COLUMN label_de VARCHAR NOT NULL DEFAULT ''"
        )

    if "category" not in column_names:
        statements.append(
            "ALTER TABLE events "
            "ADD COLUMN category VARCHAR NOT NULL DEFAULT 'OTHER'"
        )

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def backfill_event_labels() -> None:
    with Session(engine) as db:
        statement = select(Event).where(
            or_(
                Event.label_de == "",
                Event.label_de.is_(None),
                Event.category == "",
                Event.category.is_(None),
            )
        )

        events = list(db.scalars(statement).all())

        for event in events:
            event.label_de, event.category = translate_label(event.label)

        if events:
            db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    add_missing_event_columns()
    backfill_event_labels()