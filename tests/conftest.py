import pytest

from karakeep_opds.config import Settings, get_settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        KARAKEEP_BASE_URL="https://karakeep.test",
        KARAKEEP_API_TOKEN="karakeep-token",
        OPDS_USERNAME="reader",
        OPDS_PASSWORD="password123",
        OPDS_PAGE_SIZE=2,
        SERVICE_BASE_URL="https://opds.test",
    )


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KARAKEEP_BASE_URL", "https://karakeep.test")
    monkeypatch.setenv("KARAKEEP_API_TOKEN", "karakeep-token")
    monkeypatch.setenv("KARAKEEP_API_PATH", "")
    monkeypatch.setenv("OPDS_USERNAME", "reader")
    monkeypatch.setenv("OPDS_PASSWORD", "password123")
    monkeypatch.setenv("OPDS_PAGE_SIZE", "2")
    monkeypatch.setenv("SERVICE_BASE_URL", "https://opds.test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
