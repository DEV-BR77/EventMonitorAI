from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    assessment_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    assessment_exclusion_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    primary_learning_approved: Mapped[bool] = mapped_column(Boolean, default=True)
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

    secondary_classifications: Mapped[list["EventSecondaryClassification"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def secondary_class_codes(self) -> list[str]:
        return [item.class_code for item in self.secondary_classifications]

    @property
    def secondary_learning_approved_codes(self) -> list[str]:
        return [item.class_code for item in self.secondary_classifications if item.learning_approved]


class EventSecondaryClassification(TenantScopedMixin, Base):
    __tablename__ = "event_secondary_classifications"
    __table_args__ = (UniqueConstraint("event_id", "class_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    class_code: Mapped[str] = mapped_column(String(80), index=True)
    learning_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_by: Mapped[str] = mapped_column(String(80))
    assigned_at: Mapped[str] = mapped_column(String)
    event: Mapped[Event] = relationship(back_populates="secondary_classifications")
