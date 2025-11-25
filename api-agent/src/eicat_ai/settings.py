from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    data_path: Path = Field(
        default=Path("../eicat_data"), description="Path to data directory"
    )
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to bind to")
    reload: bool = Field(default=False, description="Enable auto-reload")

    class Config:
        env_file = ".env"
        env_prefix = "EICAT_"
        case_sensitive = (False,)
        extra = "ignore"


settings = Settings()
