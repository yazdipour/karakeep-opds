from functools import lru_cache
from typing import Any

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    karakeep_base_url: AnyHttpUrl = Field(alias="KARAKEEP_BASE_URL")
    karakeep_api_token: str = Field(alias="KARAKEEP_API_TOKEN", min_length=1)
    opds_username: str = Field(alias="OPDS_USERNAME", min_length=1)
    opds_password: str = Field(alias="OPDS_PASSWORD", min_length=1)
    opds_page_size: int = Field(default=50, alias="OPDS_PAGE_SIZE", ge=1, le=200)
    karakeep_api_path: str = Field(default="/api/v1", alias="KARAKEEP_API_PATH")
    service_base_url: AnyHttpUrl | None = Field(default=None, alias="SERVICE_BASE_URL")

    @field_validator("service_base_url", mode="before")
    @classmethod
    def empty_service_base_url_is_unset(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("karakeep_api_path", mode="before")
    @classmethod
    def normalize_api_path(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            return ""
        return "/" + value.strip().strip("/")

    @property
    def karakeep_origin(self) -> str:
        return f"{str(self.karakeep_base_url).rstrip('/')}{self.karakeep_api_path}"

    @property
    def service_origin(self) -> str | None:
        if self.service_base_url is None:
            return None
        return str(self.service_base_url).rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
