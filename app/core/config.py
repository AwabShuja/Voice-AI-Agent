from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_key: SecretStr
    vapi_webhook_secret: SecretStr
    database_url: str = "sqlite:///./data/patients.db"
    log_level: str = "INFO"
    draft_ttl_seconds: int = Field(default=1800, ge=60)
    max_drafts: int = Field(default=1000, ge=1)

    @model_validator(mode="after")
    def check_secrets(self):
        keys = [self.api_key.get_secret_value(), self.vapi_webhook_secret.get_secret_value()]
        if any(len(key) < 32 or key.startswith("replace-") for key in keys):
            raise ValueError("Generate distinct secrets of at least 32 characters in .env")
        if keys[0] == keys[1]:
            raise ValueError("API and webhook credentials must be different")
        return self
