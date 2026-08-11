from backend.app.services.label_translation import translate_label


def test_yell_is_translated_to_screaming() -> None:
    label, category = translate_label("Yell", "test-device")
    assert label == "Schreien"
    assert category == "VOICE"


def test_unknown_label_uses_german_fallback() -> None:
    label, category = translate_label("Unknown custom sound", "test-device")
    assert label == "Nicht zugeordnetes Geräusch"
    assert category == "OTHER"


def test_recent_yamnet_labels_are_translated() -> None:
    assert translate_label("Dishes, pots, and pans")[0] == "Geschirr, Töpfe und Pfannen"
    assert translate_label("Walk, footsteps")[0] == "Gehen und Schritte"
    assert translate_label("Alarm clock")[0] == "Wecker"
