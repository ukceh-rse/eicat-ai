from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_url: str = Field(default="mongodb://localhost:27017")
    mongodb_db: str = Field(default="eicat_ai")
    grobid_url: str = Field(default="http://localhost:8070")
    tei_url: str = Field(default="http://localhost:8000")
    model: str = Field(default="bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    reload: bool = Field(default=False)

    model_config = {
        "env_file": ".env",
        "env_prefix": "EICAT_",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
