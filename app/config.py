from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
RESUME_DIR = BASE_DIR / "resumes"
UPLOAD_DIR = BASE_DIR / "uploads"

for directory in (STORAGE_DIR, RESUME_DIR, UPLOAD_DIR):
    directory.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    app_name: str = "Job Apply Assistant"
    app_base_url: str = Field(default="http://127.0.0.1:8000", alias="APP_BASE_URL")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    secret_key: str = Field(default="change_this_secret_key", alias="SECRET_KEY")
    job_check_interval_minutes: int = Field(default=30, alias="JOB_CHECK_INTERVAL_MINUTES")
    default_min_score: int = Field(default=45, alias="DEFAULT_MIN_SCORE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
