from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    timestamp: Mapped[str] = mapped_column(String)

    event_type: Mapped[str] = mapped_column(String)

    # Unveränderte Originalklasse des KI-Modells
    label: Mapped[str] = mapped_column(String)

    # Deutsche Anzeige und stabile Kategorie
    label_de: Mapped[str] = mapped_column(String, nullable=False, default="")

    category: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="OTHER",
    )

    confidence: Mapped[float] = mapped_column(Float)

    db_level: Mapped[float] = mapped_column(Float)

    device: Mapped[str] = mapped_column(String)