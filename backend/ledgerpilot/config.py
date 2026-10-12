from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


class AppConfig(BaseSettings):
    """Process configuration from environment variables / the repo-root .env file."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    ledgerpilot_data_dir: str | None = None
    ledgerpilot_db_url: str | None = None
    ledgerpilot_scheduler: bool = True
    ledgerpilot_mock_seed: int = 42
    anthropic_api_key: str | None = None
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def data_dir(self) -> Path:
        if self.ledgerpilot_data_dir:
            return Path(self.ledgerpilot_data_dir).expanduser().resolve()
        return REPO_ROOT / "data"

    @property
    def db_url(self) -> str:
        if self.ledgerpilot_db_url:
            return self.ledgerpilot_db_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.data_dir / 'ledgerpilot.db').as_posix()}"

    @property
    def ai_available(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_config() -> AppConfig:
    return AppConfig()
