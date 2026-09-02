"""
DIP 2.0 — Centralized Configuration
=====================================

SINGLE SOURCE OF TRUTH for all settings, API keys, and configuration.
Import from anywhere: `from Config import config`

Usage:
    from dip.core.Config import config
    model = config.LLM_MODEL          # "gpt-4o"
    key = config.OPENROUTER_API_KEY   # "sk-..."
    enabled = config.DIP_OTEL_ENABLED # False

All values loaded from environment variables with sensible defaults.
For local development, copy .env.example to .env and fill in secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Load .env file at module level
try:
    from dotenv import load_dotenv
    # Root dir is 4 levels up from config.py: src/dip/core/Config -> src/dip/core -> src/dip -> src -> project_root
    _env_path = Path(__file__).resolve().parent.parent.parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

# Project root
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"


@dataclass
class Config:
    """Central configuration loaded from environment variables."""

    # ═══════════════════════════════════════════════════════════════
    # LLM Configuration
    # ═══════════════════════════════════════════════════════════════
    LLM_MODEL: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o"))
    LLM_PROVIDER: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    OPENROUTER_API_KEY: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    OPENROUTER_MODEL: str = field(default_factory=lambda: os.getenv("OPENROUTER_MODEL", ""))
    OPENROUTER_URL: str = field(default_factory=lambda: os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions"))
    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    DEEPSEEK_API_KEY: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    OLLAMA_BASE_URL: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))

    # ═══════════════════════════════════════════════════════════════
    # Server Configuration
    # ═══════════════════════════════════════════════════════════════
    API_PORT: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    API_HOST: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    ENVIRONMENT: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    CORS_ALLOWED_ORIGINS: list = field(default_factory=lambda: os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","))

    # ═══════════════════════════════════════════════════════════════
    # API Keys — Data Providers
    # ═══════════════════════════════════════════════════════════════
    ACLED_API_KEY: str = field(default_factory=lambda: os.getenv("ACLED_API_KEY", ""))
    ACLED_EMAIL: str = field(default_factory=lambda: os.getenv("ACLED_EMAIL", ""))
    GDELT_API_KEY: str = field(default_factory=lambda: os.getenv("GDELT_API_KEY", ""))

    # ═══════════════════════════════════════════════════════════════
    # Storage Paths
    # ═══════════════════════════════════════════════════════════════
    DIP_JOB_STORE: str = field(default_factory=lambda: os.getenv("DIP_JOB_STORE", str(DATA_DIR / "jobs.json")))
    CHECKPOINT_DIR: str = field(default_factory=lambda: os.getenv("CHECKPOINT_DIR", str(DATA_DIR / "checkpoints")))
    CHROMA_DATA_DIR: str = field(default_factory=lambda: os.getenv("CHROMA_DATA_DIR", str(DATA_DIR / "chroma")))
    MLFLOW_TRACKING_URI: str = field(default_factory=lambda: os.getenv("MLFLOW_TRACKING_URI", f"file:{DATA_DIR / 'mlruns'}"))
    DIP_MLFLOW_EXPERIMENT: str = field(default_factory=lambda: os.getenv("DIP_MLFLOW_EXPERIMENT", "dip2-assessments"))

    # ═══════════════════════════════════════════════════════════════
    # Feature Flags — OSS Integration
    # ═══════════════════════════════════════════════════════════════
    DIP_OTEL_ENABLED: bool = field(default_factory=lambda: os.getenv("DIP_OTEL_ENABLED", "0") == "1")
    DIP_MLFLOW_ENABLED: bool = field(default_factory=lambda: os.getenv("DIP_MLFLOW_ENABLED", "0") == "1")
    DIP_LANGGRAPH_ENABLED: bool = field(default_factory=lambda: os.getenv("DIP_LANGGRAPH_ENABLED", "0") == "1")
    DIP_PREFECT_ENABLED: bool = field(default_factory=lambda: os.getenv("DIP_PREFECT_ENABLED", "0") == "1")
    DIP_STIX2_ENABLED: bool = field(default_factory=lambda: os.getenv("DIP_STIX2_ENABLED", "0") == "1")
    DIP_NETWORKX_ENABLED: bool = field(default_factory=lambda: os.getenv("DIP_NETWORKX_ENABLED", "0") != "0")


    # ═══════════════════════════════════════════════════════════════
    # Feature Flags — Runtime Behavior
    # ═══════════════════════════════════════════════════════════════

    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    LLM_TRACE_ENABLED: bool = field(default_factory=lambda: os.getenv("LLM_TRACE_ENABLED", "0") == "1")

    # ═══════════════════════════════════════════════════════════════
    # Database (optional — for production with PostgreSQL)
    # ═══════════════════════════════════════════════════════════════
    DATABASE_URL: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    POSTGRES_USER: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "diplomat"))
    POSTGRES_PASSWORD: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", ""))
    POSTGRES_DB: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "diplomat_db"))
    POSTGRES_PORT: str = field(default_factory=lambda: os.getenv("POSTGRES_PORT", "5432"))
    REDIS_URL: str = field(default_factory=lambda: os.getenv("REDIS_URL", ""))

    @property
    def FORCE_MINISTER_HEURISTIC(self) -> bool:
        """Read this runtime switch dynamically so test and benchmark modes work."""
        return os.getenv("FORCE_MINISTER_HEURISTIC", "0") == "1"

    def validate_runtime_credentials(self) -> None:
        """Fail early when a production LLM deployment has no usable credential."""
        if self.FORCE_MINISTER_HEURISTIC or self.LLM_PROVIDER.lower() == "ollama":
            return

        provider_keys = {
            "openai": self.OPENAI_API_KEY,
            "openrouter": self.OPENROUTER_API_KEY,
            "deepseek": self.DEEPSEEK_API_KEY,
        }
        key = provider_keys.get(self.LLM_PROVIDER.lower())
        if key is None:
            raise ValueError(f"Unsupported LLM_PROVIDER: {self.LLM_PROVIDER!r}")
        if not key:
            raise ValueError(
                f"{self.LLM_PROVIDER.upper()} API key is required when LLM mode is enabled"
            )

    def __repr__(self) -> str:
        """Safe repr — masks API keys."""
        d = self.__dict__.copy()
        for k in list(d):
            if "KEY" in k or "PASSWORD" in k or "SECRET" in k:
                d[k] = "***" if d[k] else "(not set)"
        return f"Config({d})"


# Singleton instance — import this everywhere
config = Config()
