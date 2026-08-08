from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dashboard import EventClass

DEFAULT_EVENT_CLASSES = (
    ("HORN", "Hupen", "base", None),
    ("VOICE_LOUD", "Rufen/Schreien", "base", None),
    ("IMPACT", "Schlag/Aufprall", "base", None),
    ("MUSIC", "Musik", "base", None),
    ("DOG", "Hund", "base", None),
    ("ENGINE", "Motor", "base", None),
    ("SIREN", "Sirene", "base", None),
    ("BIRDS", "Vögel", "base", None),
    ("MACHINERY", "Maschinen", "base", None),
    ("VEHICLE", "Fahrzeuge", "base", None),
    ("BALL_CONCRETE", "Fußball gegen Beton", "fine", "IMPACT"),
    ("BALL_METAL", "Fußball gegen Metall", "fine", "IMPACT"),
    ("HIT_LAMPPOST", "Schlagen gegen Laterne", "fine", "IMPACT"),
    ("VOICE_SUSTAINED", "Anhaltendes Rufen", "fine", "VOICE_LOUD"),
    ("VEHICLE_HORN", "Fahrzeughupen", "fine", "HORN"),
    ("OTHER_NOISE", "Sonstiger Lärm", "fine", None),
)


def seed_event_classes(db: Session) -> None:
    existing = set(db.scalars(select(EventClass.code)).all())
    for order, (code, name, level, parent_code) in enumerate(DEFAULT_EVENT_CLASSES, start=1):
        if code not in existing:
            db.add(
                EventClass(
                    code=code,
                    name=name,
                    level=level,
                    parent_code=parent_code,
                    sort_order=order,
                )
            )
    db.commit()


def base_class_for_detection(label: str, category: str) -> str | None:
    normalized = label.casefold()
    if "horn" in normalized or "hupe" in normalized:
        return "HORN"
    if category == "IMPACT":
        return "IMPACT"
    if category == "VOICE":
        return "VOICE_LOUD"
    if category == "MUSIC":
        return "MUSIC"
    if category == "ANIMAL" and ("dog" in normalized or "hund" in normalized):
        return "DOG"
    if category == "VEHICLE":
        return "VEHICLE"
    if "siren" in normalized or "sirene" in normalized:
        return "SIREN"
    if "bird" in normalized or "vogel" in normalized:
        return "BIRDS"
    if "engine" in normalized or "motor" in normalized:
        return "ENGINE"
    if "machine" in normalized or "maschine" in normalized:
        return "MACHINERY"
    return None
