LABEL_TRANSLATIONS: dict[str, tuple[str, str]] = {
    # Stille und Umgebung
    "Silence": ("Stille", "SILENCE"),
    "Inside, small room": ("Innenraum", "AMBIENT"),
    "White noise": ("Weißes Rauschen", "AMBIENT"),

    # Sprache und menschliche Stimmen
    "Speech": ("Sprache", "VOICE"),
    "Conversation": ("Gespräch", "VOICE"),
    "Male speech, man speaking": ("Männliche Stimme", "VOICE"),
    "Female speech, woman speaking": ("Weibliche Stimme", "VOICE"),
    "Child speech, kid speaking": ("Kinderstimme", "VOICE"),
    "Shout": ("Rufen", "VOICE"),
    "Yell": ("Schreien", "VOICE"),
    "Whispering": ("Flüstern", "VOICE"),
    "Humming": ("Summen", "VOICE"),

    # Menschliche Geräusche
    "Cough": ("Husten", "HUMAN_SOUND"),
    "Sneeze": ("Niesen", "HUMAN_SOUND"),
    "Laughter": ("Lachen", "HUMAN_SOUND"),
    "Crying, sobbing": ("Weinen", "HUMAN_SOUND"),
    "Snoring": ("Schnarchen", "HUMAN_SOUND"),
    "Breathing": ("Atmen", "HUMAN_SOUND"),

    # Hand-, Schlag- und Impulsgeräusche
    "Hands": ("Handgeräusch", "IMPACT"),
    "Clapping": ("Klatschen", "IMPACT"),
    "Finger snapping": ("Fingerschnippen", "IMPACT"),
    "Knock": ("Klopfen", "IMPACT"),
    "Chop": ("Schlag-/Hackgeräusch", "IMPACT"),
    "Slam": ("Zuschlagen", "IMPACT"),
    "Explosion": ("Explosion/Knall", "IMPACT"),
    "Cap gun": ("Knall-/Impulsgeräusch", "IMPACT"),
    "Gunshot, gunfire": ("Schussgeräusch", "IMPACT"),
    "Fireworks": ("Feuerwerk", "IMPACT"),

    # Geräte und Tastatur
    "Typing": ("Tippen", "DEVICE"),
    "Computer keyboard": ("Tastatur", "DEVICE"),

    # Tiere
    "Animal": ("Tiergeräusch", "ANIMAL"),
    "Dog": ("Hund", "ANIMAL"),
    "Bark": ("Hundegebell", "ANIMAL"),
    "Cat": ("Katze", "ANIMAL"),

    # Verkehr
    "Vehicle": ("Fahrzeug", "VEHICLE"),
    "Car": ("Auto", "VEHICLE"),
    "Vehicle horn, car horn, honking": ("Fahrzeughupe", "VEHICLE"),

    # Musik
    "Music": ("Musik", "MUSIC"),
}


def translate_label(label: str) -> tuple[str, str]:
    normalized_label = label.strip()

    return LABEL_TRANSLATIONS.get(
        normalized_label,
        (normalized_label or "Unbekannt", "OTHER"),
    )