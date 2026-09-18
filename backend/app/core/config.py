from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "机床售后技术支持工作台 API"
    app_env: str = os.getenv("APP_ENV", "development")
    app_secret: str = os.getenv("APP_SECRET", "development-only-change-me-32-characters")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./machine_service.db")
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "../data/uploads"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "30"))
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "local-development-only-password")
    login_max_failures: int = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
    login_lock_minutes: int = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
    seed_demo_data: bool = _bool(
        "SEED_DEMO_DATA", os.getenv("APP_ENV", "development") != "production"
    )
    neo4j_enabled: bool = _bool("NEO4J_ENABLED", False)
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "")
    llm_enabled: bool = _bool("LLM_ENABLED", False)
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings


def validate_runtime_settings(settings: Settings) -> None:
    if settings.app_env != "production":
        return
    problems: list[str] = []
    placeholder_markers = ("change", "replace", "example", "placeholder", "dev-password")

    def is_placeholder(value: str) -> bool:
        normalized = value.lower()
        return not value or any(marker in normalized for marker in placeholder_markers)

    if len(settings.app_secret) < 32 or is_placeholder(settings.app_secret):
        problems.append("APP_SECRET must be a non-default secret of at least 32 characters")
    if len(settings.admin_password) < 12 or is_placeholder(settings.admin_password):
        problems.append("ADMIN_PASSWORD must be replaced with a stronger initial password")
    if settings.database_url.startswith("postgresql") and is_placeholder(settings.database_url):
        problems.append("DATABASE_URL must not contain a placeholder password")
    if settings.neo4j_enabled and is_placeholder(settings.neo4j_password):
        problems.append("NEO4J_PASSWORD must be replaced")
    if not 3 <= settings.login_max_failures <= 20:
        problems.append("LOGIN_MAX_FAILURES must be between 3 and 20")
    if not 1 <= settings.login_lock_minutes <= 1440:
        problems.append("LOGIN_LOCK_MINUTES must be between 1 and 1440")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
