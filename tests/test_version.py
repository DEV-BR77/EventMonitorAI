from app.core.config import settings
from app.version import __version__


def test_settings_use_repository_version():
    assert settings.app_version == __version__


def test_version_is_exposed_by_health_endpoint():
    from app.api.health import health

    assert health()["version"] == __version__
