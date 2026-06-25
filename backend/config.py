from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    mode: Literal["live", "mock"] = "mock"

    # Rithmic / Bookmap gateway
    rithmic_ws_url: str = "wss://localhost:443"
    rithmic_user: str = ""
    rithmic_password: str = ""
    rithmic_system_name: str = "Rithmic Paper Trading"

    # Symbol
    symbol: str = "GCQ6"
    exchange: str = "CME"

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Frontend
    api_base_url: str = "http://localhost:8000"
    refresh_interval_ms: int = 1000


settings = Settings()
