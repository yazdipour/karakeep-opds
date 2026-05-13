from karakeep_opds.config import Settings


def test_empty_service_base_url_is_unset() -> None:
    settings = Settings(
        KARAKEEP_BASE_URL="https://karakeep.test",
        KARAKEEP_API_TOKEN="karakeep-token",
        OPDS_USERNAME="reader",
        OPDS_PASSWORD="password123",
        SERVICE_BASE_URL="",
    )

    assert settings.service_origin is None


def test_karakeep_origin_uses_api_v1_by_default(monkeypatch) -> None:
    monkeypatch.delenv("KARAKEEP_API_PATH", raising=False)
    settings = Settings(
        KARAKEEP_BASE_URL="https://karakeep.test",
        KARAKEEP_API_TOKEN="karakeep-token",
        OPDS_USERNAME="reader",
        OPDS_PASSWORD="password123",
    )

    assert settings.karakeep_origin == "https://karakeep.test/api/v1"


def test_karakeep_api_path_can_be_disabled() -> None:
    settings = Settings(
        KARAKEEP_BASE_URL="https://karakeep.test",
        KARAKEEP_API_TOKEN="karakeep-token",
        OPDS_USERNAME="reader",
        OPDS_PASSWORD="password123",
        KARAKEEP_API_PATH="",
    )

    assert settings.karakeep_origin == "https://karakeep.test"


def test_short_opds_password_is_allowed() -> None:
    settings = Settings(
        KARAKEEP_BASE_URL="https://karakeep.test",
        KARAKEEP_API_TOKEN="karakeep-token",
        OPDS_USERNAME="reader",
        OPDS_PASSWORD="123",
    )

    assert settings.opds_password == "123"
