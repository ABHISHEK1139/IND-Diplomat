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

# Load .env file at module level
try:
    from dotenv import load_dotenv
    # Root dir is 4 levels up from config.py: src/dip/core/Config -> src/dip/core -> src/dip -> src -> project_root
    _env_path = Path(__file__).resolve().parent.parent.parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

# Source checkout root; installed distributions default to the working directory.
_source_root = Path(__file__).resolve().parents[4]
ROOT_DIR = _source_root if (_source_root / "pyproject.toml").is_file() else Path.cwd()
# A relative DIP_DATA_DIR anchors at ROOT_DIR (not the working directory),
# so `./data` always means the checkout's data/ no matter where started from.
_raw_data_dir = Path(os.getenv("DIP_DATA_DIR", str(ROOT_DIR / "data"))).expanduser()
DATA_DIR = (_raw_data_dir if _raw_data_dir.is_absolute() else (ROOT_DIR / _raw_data_dir)).resolve()


def resolve_data_path(raw: str | Path, default_name: str | None = None) -> str:
    """Resolve a storage path against DATA_DIR.

    Relative paths (e.g. ``data/jobs.json`` from a copied .env) are anchored
    at DATA_DIR so results never depend on the process working directory.
    Absolute paths and URIs (``file:``, ``sqlite:///``, ``http``) pass
    through untouched.
    """
    text = str(raw or "").strip()
    if not text and default_name:
        return str(DATA_DIR / default_name)
    if not text:
        return text
    lowered = text.lower()
    if lowered.startswith(("file:", "sqlite:", "http://", "https://")) or os.path.isabs(text):
        return text
    # Strip a leading ./ or .\ for tidiness, then anchor.
    cleaned = text[2:] if text[:2] in ("./", ".\\") else text
    parts = Path(cleaned).parts
    if parts and parts[0].lower() == "data":
        # Legacy repo-root-relative form (e.g. .env's data/jobs.json).
        rest = Path(*parts[1:]) if len(parts) > 1 else Path()
        return str((ROOT_DIR / rest).resolve()) if str(rest) not in ("", ".") else str(DATA_DIR)
    return str(DATA_DIR / cleaned)


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
    # Loopback by default: a bare-metal run should not expose the API on every
    # interface. Container/server deployments opt in explicitly (Dockerfiles pass
    # --host 0.0.0.0 or set API_HOST=0.0.0.0).
    API_HOST: str = field(default_factory=lambda: os.getenv("API_HOST", "127.0.0.1"))
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
    DIP_JOB_STORE: str = field(default_factory=lambda: resolve_data_path(os.getenv("DIP_JOB_STORE", ""), "jobs.json"))
    CHECKPOINT_DIR: str = field(default_factory=lambda: resolve_data_path(os.getenv("CHECKPOINT_DIR", ""), "checkpoints"))
    CHROMA_DATA_DIR: str = field(default_factory=lambda: resolve_data_path(os.getenv("CHROMA_DATA_DIR", ""), "chroma"))
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

    def validate_production_settings(self) -> None:
        """Fail fast on unsafe production exposure (wildcard CORS).

        In production a wildcard CORS origin lets any site drive the API from a
        victim's browser. Credentials are already disabled for '*', but the
        endpoint is still reachable cross-origin, so require an explicit list.
        """
        if self.ENVIRONMENT.lower() not in ("production", "prod"):
            return
        origins = [o.strip() for o in self.CORS_ALLOWED_ORIGINS if o.strip()]
        if "*" in origins:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must list explicit origins in production "
                "(wildcard '*' is not permitted)"
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
