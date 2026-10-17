import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> project root is three levels up
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"

_DEFAULT_DB = "sqlite:////tmp/career_coach.db" if os.environ.get("VERCEL") else "sqlite:///./career_coach.db"

class Settings(BaseSettings):
    PROJECT_NAME: str = "TrueSkill"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = _DEFAULT_DB
    
    # API Keys & Webhook Secrets
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    LLM_PROVIDER: str = "groq"
    # Gemini models
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GEMINI_FALLBACK_MODELS: str = "gemini-3-flash-preview,gemma-4-26b-a4b-it"
    # Groq models
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_FALLBACK_MODELS: str = "qwen/qwen3.8-27b,openai/gpt-oss-120b"
    LLM_MAX_RETRIES: int = 2
    GITHUB_TOKEN: str = ""
    GITHUB_WEBHOOK_SECRET: str = "test-webhook-secret-key-12345"
    YOUTUBE_API_KEY: str = ""

    # Job Source Providers (Naukri / Fallbacks)
    JOB_SOURCE: str = "naukri"
    NAUKRI_BASE_URL: str = "https://www.naukri.com"
    NAUKRI_APP_ID: str = "109"
    NAUKRI_SYSTEM_ID: str = "109"
    JOB_SEARCH_CACHE_TTL: int = 600  # 10 minutes
    JSEARCH_API_KEY: str = ""
    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:8755",
        "http://127.0.0.1:8755",
        "http://localhost:2222",
        "http://127.0.0.1:2222",
        "http://localhost:4444",
        "http://127.0.0.1:4444",
        "http://localhost:5459",
        "http://127.0.0.1:5459",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:1200",
        "http://127.0.0.1:1200",
    ]

    # Root .env is listed last so the key you edit there wins over backend/.env
    model_config = SettingsConfigDict(
        env_file=(str(_BACKEND_ENV), str(_ROOT_ENV)),
        extra="allow",
    )

settings = Settings()
