from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dashboard import EventClass

DEFAULT_EVENT_CLASSES = (
    ("NO_NOISE", "Kein Lärm / verwerfen", "base", None, True, False),
    ("WIND", "Wind", "base", None, True, True),
    ("AMBIENT", "Umgebung/Natur", "base", None, True, True),
    ("TECHNICAL", "Technisches Störgeräusch", "base", None, True, True),
    ("HORN", "Hupen", "base", None, False, True),
    ("VOICE_LOUD", "Rufen/Schreien", "base", None, False, True),
    ("IMPACT", "Schlag/Aufprall/Knall", "base", None, False, True),
    ("MUSIC", "Musik", "base", None, False, True),
    ("DOG", "Hund", "base", None, False, True),
    ("ENGINE", "Motor", "base", None, False, True),
    ("SIREN", "Sirene", "base", None, False, True),
    ("BIRDS", "Vögel", "base", None, False, True),
    ("MACHINERY", "Maschinen", "base", None, False, True),
    ("VEHICLE", "Fahrzeuge", "base", None, False, True),
    ("BALL_CONCRETE", "Fußball gegen Beton", "fine", "IMPACT", False, True),
    ("BALL_METAL", "Fußball gegen Metall", "fine", "IMPACT", False, True),
    ("HIT_LAMPPOST", "Schlagen gegen Laterne", "fine", "IMPACT", False, True),
    ("FIRECRACKER", "Knallkörper", "fine", "IMPACT", False, True),
    ("VOICE_SUSTAINED", "Anhaltendes Rufen", "fine", "VOICE_LOUD", False, True),
    ("LOUD_SCREAM", "Lautes Schreien", "fine", "VOICE_LOUD", False, True),
    ("ARGUMENT", "Streit / mehrere Personen", "fine", "VOICE_LOUD", False, True),
    ("VEHICLE_HORN", "Fahrzeughupen", "fine", "HORN", False, True),
    ("WIND_NOISE", "Windgeräusch", "fine", "WIND", True, True),
    ("RURAL_NATURE", "Ländliche/natürliche Umgebung", "fine", "AMBIENT", True, True),
    ("MAINS_HUM", "Netzbrummen", "fine", "TECHNICAL", True, True),
    ("TUNING_FORK", "Stimmgabel/Resonanz", "fine", "TECHNICAL", True, True),
    ("MODEL_ARTIFACT", "KI-Fehlklassifikation", "fine", "TECHNICAL", True, True),
    ("OTHER_NOISE", "Sonstiger Lärm", "fine", None, False, True),
)


def seed_event_classes(db: Session) -> None:
    existing = set(db.scalars(select(EventClass.code)).all())
    for order, (
        code,
        name,
        level,
        parent_code,
        hidden_by_default,
        trainable,
    ) in enumerate(DEFAULT_EVENT_CLASSES, start=1):
        if code not in existing:
            db.add(
                EventClass(
                    code=code,
                    name=name,
                    level=level,
                    parent_code=parent_code,
                    hidden_by_default=hidden_by_default,
                    trainable=trainable,
                    sort_order=order,
                )
            )
        elif code in {"NO_NOISE", "WIND", "AMBIENT", "TECHNICAL"}:
            event_class = db.scalar(select(EventClass).where(EventClass.code == code))
            if event_class is not None:
                event_class.hidden_by_default = hidden_by_default
                event_class.trainable = trainable
        elif code == "IMPACT":
            event_class = db.scalar(select(EventClass).where(EventClass.code == code))
            if event_class is not None:
                event_class.name = name
    db.commit()


def base_class_for_detection(label: str, category: str) -> str | None:
    normalized = label.casefold()
    if "wind" in normalized:
        return "WIND"
    if any(item in normalized for item in ("rural", "natural environment", "outside")):
        return "AMBIENT"
    if any(item in normalized for item in ("mains hum", "tuning fork", "heartbeat")):
        return "TECHNICAL"
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
