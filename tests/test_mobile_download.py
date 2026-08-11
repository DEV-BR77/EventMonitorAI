import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_PAGE = ROOT / "website" / "public" / "android-download.html"
INDEX_PAGE = ROOT / "website" / "public" / "index.html"


def test_android_preview_download_is_versioned_and_verifiable() -> None:
    page = DOWNLOAD_PAGE.read_text(encoding="utf-8")

    assert "mobile-preview-v0.1.0/eventmonitor-voice-preview-0.1.0.apk" in page
    assert "de.eventmonitor.eventmonitor_voice.preview" in page
    assert re.search(r"\b[A-F0-9]{64}\b", page)
    assert "noch nicht im Google Play Store" in page


def test_public_site_links_to_android_preview_instead_of_embedding_apk() -> None:
    index = INDEX_PAGE.read_text(encoding="utf-8")

    assert 'href="/android-download.html"' in index
    smartphone_card = index.split("02 · SMARTPHONE", 1)[1].split("</article>", 1)[0]
    assert "Eigenes Handy verwenden" in smartphone_card
    assert "Android Beta-Version herunterladen" in smartphone_card
    assert 'href="/android-download.html"' in smartphone_card
    assert not list((ROOT / "website").rglob("*.apk"))
