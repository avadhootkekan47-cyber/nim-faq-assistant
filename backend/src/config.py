"""
src/config.py
─────────────
Central settings loaded from environment variables (via .env).
All other modules import from here — never read os.environ directly.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── NVIDIA NIM ─────────────────────────────────────────────────────────────
    nim_base_url: str = Field("https://integrate.api.nvidia.com/v1", env="NIM_BASE_URL")
    nim_api_key: str = Field(..., env="NIM_API_KEY")
    nim_model: str = Field("meta/llama-3.1-8b-instruct", env="NIM_MODEL")

    # ── LLM generation params ──────────────────────────────────────────────────
    llm_temperature: float = Field(0.3, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(512, env="LLM_MAX_TOKENS")
    llm_top_p: float = Field(0.95, env="LLM_TOP_P")
    llm_timeout: int = Field(30, env="LLM_TIMEOUT")
    llm_max_retries: int = Field(3, env="LLM_MAX_RETRIES")

    # ── App ────────────────────────────────────────────────────────────────────
    app_host: str = Field("0.0.0.0", env="APP_HOST")
    app_port: int = Field(8000, env="APP_PORT")
    app_env: str = Field("development", env="APP_ENV")

    # ── CORS ───────────────────────────────────────────────────────────────────
    cors_origins: str = Field("http://localhost:3000", env="CORS_ORIGINS")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    # ── FAQ ────────────────────────────────────────────────────────────────────
    faq_file: str = Field("faq_data/faq.yml", env="FAQ_FILE")
    faq_top_k: int = Field(3, env="FAQ_TOP_K")

    model_config = {"env_file": ".env", "extra": "ignore"}


# Singleton — import this everywhere
settings = Settings()
