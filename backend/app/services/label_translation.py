LABEL_TRANSLATIONS: dict[str, tuple[str, str]] = {
    # Stille und Umgebung
    "Silence": ("Stille", "SILENCE"),
    "Inside, small room": ("Innenraum", "AMBIENT"),
    "White noise": ("Weißes Rauschen", "AMBIENT"),
    "Outside, rural or natural": ("Ländliche oder natürliche Umgebung", "AMBIENT"),
    "Wind": ("Wind", "AMBIENT"),
    "Mains hum": ("Netzbrummen", "AMBIENT"),
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
    "Burping, eructation": ("Aufstoßen", "HUMAN_SOUND"),
    "Fart": ("Darmgeräusch", "HUMAN_SOUND"),
    "Heart sounds, heartbeat": ("Herzschlag", "HUMAN_SOUND"),
    "Hiccup": ("Schluckauf", "HUMAN_SOUND"),
    "Stomach rumble": ("Magenknurren", "HUMAN_SOUND"),
    "Walk, footsteps": ("Gehen und Schritte", "HUMAN_SOUND"),
    "Beatboxing": ("Beatboxen", "HUMAN_SOUND"),
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
    "Basketball bounce": ("Aufprall eines Basketballs", "IMPACT"),
    "Crackle": ("Knistern", "IMPACT"),
    "Creak": ("Knarren", "IMPACT"),
    "Patter": ("Prasseln", "IMPACT"),
    "Tick": ("Ticken", "IMPACT"),
    # Geräte und Tastatur
    "Typing": ("Tippen", "DEVICE"),
    "Computer keyboard": ("Tastatur", "DEVICE"),
    "Alarm": ("Alarm", "DEVICE"),
    "Alarm clock": ("Wecker", "DEVICE"),
    "Arrow": ("Pfeilgeräusch", "DEVICE"),
    "Beep, bleep": ("Piepton", "DEVICE"),
    "Blender": ("Mixer", "DEVICE"),
    "Camera": ("Kamera", "DEVICE"),
    "Cash register": ("Registrierkasse", "DEVICE"),
    "Chime": ("Glockenspiel", "DEVICE"),
    "Clock": ("Uhr", "DEVICE"),
    "Filing (rasp)": ("Feilen und Raspeln", "DEVICE"),
    "Gears": ("Zahnräder", "DEVICE"),
    "Mechanical fan": ("Mechanischer Ventilator", "DEVICE"),
    "Mechanisms": ("Mechanismus", "DEVICE"),
    "Printer": ("Drucker", "DEVICE"),
    "Pump (liquid)": ("Flüssigkeitspumpe", "DEVICE"),
    "Sewing machine": ("Nähmaschine", "DEVICE"),
    "Telephone": ("Telefon", "DEVICE"),
    "Tools": ("Werkzeug", "DEVICE"),
    "Toothbrush": ("Zahnbürste", "DEVICE"),
    "Tuning fork": ("Stimmgabel", "DEVICE"),
    "Vacuum cleaner": ("Staubsauger", "DEVICE"),
    "Writing": ("Schreiben", "DEVICE"),
    # Tiere
    "Animal": ("Unklares Ruf-/Stimmgeräusch", "VOCALIZATION"),
    "Dog": ("Hund", "ANIMAL"),
    "Bark": ("Hundegebell", "ANIMAL"),
    "Cat": ("Katze", "ANIMAL"),
    "Domestic animals, pets": ("Unklares Ruf-/Tiergeräusch", "VOCALIZATION"),
    "Livestock, farm animals, working animals": ("Unklares Ruf-/Tiergeräusch", "VOCALIZATION"),
    "Bird": ("Vogel", "ANIMAL"),
    "Goat": ("Ziege", "ANIMAL"),
    "Horse": ("Pferd", "ANIMAL"),
    "Insect": ("Insekt", "ANIMAL"),
    "Pig": ("Schwein", "ANIMAL"),
    "Purr": ("Schnurren", "ANIMAL"),
    "Rodents, rats, mice": ("Nagetiere, Ratten oder Mäuse", "ANIMAL"),
    # Verkehr
    "Vehicle": ("Fahrzeug", "VEHICLE"),
    "Car": ("Auto", "VEHICLE"),
    "Vehicle horn, car horn, honking": ("Fahrzeughupe", "VEHICLE"),
    "Helicopter": ("Hubschrauber", "VEHICLE"),
    "Rail transport": ("Schienenverkehr", "VEHICLE"),
    "Skateboard": ("Skateboard", "VEHICLE"),
    # Haushalt und Materialien
    "Crumpling, crinkling": ("Zerknüllen und Rascheln", "HOUSEHOLD"),
    "Cupboard open or close": ("Schrank öffnen oder schließen", "HOUSEHOLD"),
    "Cutlery, silverware": ("Besteck", "HOUSEHOLD"),
    "Dishes, pots, and pans": ("Geschirr, Töpfe und Pfannen", "HOUSEHOLD"),
    "Door": ("Tür", "HOUSEHOLD"),
    "Glass": ("Glas", "HOUSEHOLD"),
    "Hiss": ("Zischen", "HOUSEHOLD"),
    "Pour": ("Eingießen", "HOUSEHOLD"),
    "Rustle": ("Rascheln", "HOUSEHOLD"),
    "Sliding door": ("Schiebetür", "HOUSEHOLD"),
    "Spray": ("Sprühen", "HOUSEHOLD"),
    "Wind chime": ("Windspiel", "HOUSEHOLD"),
    "Zipper (clothing)": ("Reißverschluss", "HOUSEHOLD"),
    # Musik
    "Music": ("Musik", "MUSIC"),
}


DEVICE_LABEL_OVERRIDES: dict[
    str,
    dict[str, tuple[str, str]],
] = {
    "ESP32-Garden": {
        "Animal": (
            "Lautes Schreien/Rufen",
            "VOICE",
        ),
    },
}


def translate_label(
    label: str,
    device: str | None = None,
) -> tuple[str, str]:
    normalized_label = label.strip()

    if device:
        device_overrides = DEVICE_LABEL_OVERRIDES.get(
            device,
            {},
        )

        if normalized_label in device_overrides:
            return device_overrides[normalized_label]

    return LABEL_TRANSLATIONS.get(
        normalized_label,
        ("Nicht zugeordnetes Geräusch", "OTHER"),
    )
