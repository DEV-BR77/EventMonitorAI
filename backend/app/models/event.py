from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.tenancy import TenantScopedMixin


class Event(TenantScopedMixin, Base):
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

    primary_class_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    subclass_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    classification_status: Mapped[str] = mapped_column(String(20), default="automatic")
    display_suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    person_monitoring_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    corrected_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    corrected_at: Mapped[str | None] = mapped_column(String, nullable=True)

    confidence: Mapped[float] = mapped_column(Float)

    # Höchster Pegel während des Ereignisses
    db_level: Mapped[float] = mapped_column(Float)

    # Durchschnittlicher Pegel aller Ereignisfenster
    avg_db_level: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    device: Mapped[str] = mapped_column(String)
