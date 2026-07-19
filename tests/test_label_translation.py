from backend.app.services.label_translation import translate_label


def test_yell_is_translated_to_screaming() -> None:
    label, category = translate_label("Yell", "test-device")
    assert label == "Schreien"
    assert category == "VOICE"


def test_unknown_label_is_preserved() -> None:
    label, category = translate_label("Unknown custom sound", "test-device")
    assert label
    assert category
