from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Startzeit des Ereignisses
    timestamp: Mapped[str] = mapped_column(String)

    # Ende und Dauer des zusammengefassten Ereignisses
    end_timestamp: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    duration_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.975,
    )

    event_type: Mapped[str] = mapped_column(String)

    # Unveränderte Originalklasse des KI-Modells
    label: Mapped[str] = mapped_column(String)

    # Deutsche Anzeige und stabile Kategorie
    label_de: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="",
    )

    category: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="OTHER",
    )

    confidence: Mapped[float] = mapped_column(Float)

    # Höchster Pegel während des Ereignisses
    db_level: Mapped[float] = mapped_column(Float)

    # Durchschnittlicher Pegel aller Ereignisfenster
    avg_db_level: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    device: Mapped[str] = mapped_column(String)