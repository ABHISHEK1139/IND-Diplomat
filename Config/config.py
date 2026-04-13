"""
IND-Diplomat Configuration
===========================
All settings loaded from environment variables with safe defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _env_flag(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: str) -> list[str]:
    raw = str(os.getenv(name, default) or "").strip()
    values = [part.strip() for part in raw.split(",") if part.strip()]
    return values or ["http://localhost:3000"]

# ── Project Root ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = os.getenv("DATA_DIR", str(PROJECT_ROOT / "data"))

# ── ChromaDB (Vector Store) ──────────────────────────────────────
CHROMA_DATA_DIR = os.getenv("CHROMA_DATA_DIR", str(Path(DATA_DIR) / "chroma"))
CHROMA_HOST = os.getenv("CHROMA_HOST", "")        # empty = use local PersistentClient
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

# ── Neo4j (Graph DB — optional) ──────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_ENABLED = os.getenv("NEO4J_ENABLED", "false").lower() == "true"

# ── Redis (Cache — optional) ─────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"

# ── LLM / Ollama ─────────────────────────────────────────────────
_RAW_OPENROUTER_API_KEY = str(os.getenv("OPENROUTER_API_KEY", "")).strip()
_EXPLICIT_LLM_PROVIDER = str(os.getenv("LLM_PROVIDER", "")).strip().lower()
DEFAULT_OPENROUTER_MODEL = (
    str(os.getenv("DEFAULT_OPENROUTER_MODEL", "qwen/qwen3.6-plus-preview:free")).strip()
    or "qwen/qwen3.6-plus-preview:free"
)

LLM_PROVIDER = _EXPLICIT_LLM_PROVIDER or ("openrouter" if _RAW_OPENROUTER_API_KEY else "ollama")
LLM_MODEL = str(os.getenv("LLM_MODEL", "deepseek-r1:8b")).strip() or "deepseek-r1:8b"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_URL = os.getenv("OLLAMA_URL", f"{OLLAMA_BASE_URL}/api/generate")
LLM_CONTEXT_WINDOW = int(os.getenv("LLM_CONTEXT_WINDOW", "32768"))
LITELLM_PROXY_URL = os.getenv("LITELLM_PROXY_URL", "http://localhost:4000")
LOCAL_LLM_MAX_TOKENS = int(os.getenv("LOCAL_LLM_MAX_TOKENS", "1024"))
CLOUD_LLM_MAX_TOKENS = int(os.getenv("CLOUD_LLM_MAX_TOKENS", "8000"))
LLM_REQUEST_TIMEOUT_SEC = int(os.getenv("LLM_REQUEST_TIMEOUT_SEC", "600"))
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
_OPENROUTER_MODEL_DEFAULT = DEFAULT_OPENROUTER_MODEL if LLM_PROVIDER == "openrouter" else LLM_MODEL
OPENROUTER_MODEL = str(os.getenv("OPENROUTER_MODEL", _OPENROUTER_MODEL_DEFAULT)).strip() or _OPENROUTER_MODEL_DEFAULT
OPENROUTER_API_KEY = _RAW_OPENROUTER_API_KEY
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "IND-Diplomat")
OPENROUTER_ENABLE_FALLBACK_CHAIN = _env_flag("OPENROUTER_ENABLE_FALLBACK_CHAIN", "false")
OPENROUTER_REASONING_ENABLED = _env_flag("OPENROUTER_REASONING_ENABLED", "true")
OPENROUTER_REASONING_EXCLUDE = _env_flag("OPENROUTER_REASONING_EXCLUDE", "true")
OPENROUTER_REASONING_EFFORT = os.getenv("OPENROUTER_REASONING_EFFORT", "medium").strip().lower()
OPENROUTER_REASONING_MAX_TOKENS = int(os.getenv("OPENROUTER_REASONING_MAX_TOKENS", "0"))
LLM_OVERFLOW_POLICY = os.getenv("LLM_OVERFLOW_POLICY", "pack_then_fail").strip().lower() or "pack_then_fail"
OLLAMA_LAYER4_ENABLED = _env_flag("OLLAMA_LAYER4_ENABLED", "false")
OLLAMA_FALLBACK_ONLY = _env_flag("OLLAMA_FALLBACK_ONLY", "true")

L4_CLASSIFICATION_INPUT_BUDGET = int(os.getenv("L4_CLASSIFICATION_INPUT_BUDGET", "1200"))
L4_CLASSIFICATION_OUTPUT_BUDGET = int(os.getenv("L4_CLASSIFICATION_OUTPUT_BUDGET", "1200"))
L4_MINISTER_INPUT_BUDGET = int(os.getenv("L4_MINISTER_INPUT_BUDGET", "2200"))
L4_MINISTER_OUTPUT_BUDGET = int(os.getenv("L4_MINISTER_OUTPUT_BUDGET", "3000"))
L4_REDTEAM_INPUT_BUDGET = int(os.getenv("L4_REDTEAM_INPUT_BUDGET", "1800"))
L4_REDTEAM_OUTPUT_BUDGET = int(os.getenv("L4_REDTEAM_OUTPUT_BUDGET", "1800"))
L4_SYNTHESIS_INPUT_BUDGET = int(os.getenv("L4_SYNTHESIS_INPUT_BUDGET", "4000"))
L4_SYNTHESIS_OUTPUT_BUDGET = int(os.getenv("L4_SYNTHESIS_OUTPUT_BUDGET", "3600"))
SYSTEM_GUARDIAN_RUN_ON_IMPORT = _env_flag("SYSTEM_GUARDIAN_RUN_ON_IMPORT", "false")
GROUPTHINK_EMBEDDER_MODEL = os.getenv("GROUPTHINK_EMBEDDER_MODEL", "all-MiniLM-L6-v2").strip() or "all-MiniLM-L6-v2"
GROUPTHINK_ALLOW_REMOTE_EMBEDDER_DOWNLOAD = _env_flag("GROUPTHINK_ALLOW_REMOTE_EMBEDDER_DOWNLOAD", "false")
OPTIONAL_LLM_STAGE_MAX_RATE_LIMIT_HITS = int(os.getenv("OPTIONAL_LLM_STAGE_MAX_RATE_LIMIT_HITS", "1"))
OPTIONAL_LLM_STAGE_MAX_EMPTY_RESPONSES = int(os.getenv("OPTIONAL_LLM_STAGE_MAX_EMPTY_RESPONSES", "1"))

# ── Data Source APIs ──────────────────────────────────────────────
GDELT_API_URL = os.getenv("GDELT_API_URL", "https://api.gdeltproject.org/api/v2")
WORLDBANK_API_URL = os.getenv("WORLDBANK_API_URL", "https://api.worldbank.org/v2")
COMTRADE_API_URL = os.getenv("COMTRADE_API_URL", "https://comtradeapi.un.org")

# ── System ────────────────────────────────────────────────────────
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a diplomatic intelligence analyst."
)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
API_KEY = str(os.getenv("API_KEY", "") or "").strip()
API_KEY_CONFIG_MESSAGE = (
    "Set API_KEY (or IND_DIPLOMAT_API_KEY) in .env to enable X-API-Key auth."
)

# ── API Security / CORS ───────────────────────────────────────────
CORS_ALLOWED_ORIGINS = _env_csv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
)
CORS_ALLOW_CREDENTIALS = _env_flag("CORS_ALLOW_CREDENTIALS", "true")
if "*" in CORS_ALLOWED_ORIGINS and CORS_ALLOW_CREDENTIALS:
    # Browsers reject wildcard origins with credentials enabled.
    CORS_ALLOW_CREDENTIALS = False

# ── Phase-2 Isolation Flag ────────────────────────────────────────
# When False, the entire legal/normative module is skipped:
#   - No _apply_legal_reasoning in state provider
#   - No post-gate RAG retrieval
#   - No LLM legal reasoner
#   - Legal signals never enter state memory
# The SRE escalation score remains identical (firewall proven).
ENABLE_LEGAL_MODULE = os.getenv("ENABLE_LEGAL_MODULE", "false").lower() == "true"

# ── Phase 7: Global Model ────────────────────────────────────────
# Multi-theater strategic synchronization — escalation contagion.
ENABLE_GLOBAL_MODEL = os.getenv("ENABLE_GLOBAL_MODEL", "true").lower() == "true"
CONTAGION_DECAY_RATE = float(os.getenv("CONTAGION_DECAY_RATE", "0.25"))
SYSTEMIC_CASCADE_THRESHOLD = float(os.getenv("SYSTEMIC_CASCADE_THRESHOLD", "4.0"))
CROSS_THEATER_SPILLOVER_FACTOR = float(os.getenv("CROSS_THEATER_SPILLOVER_FACTOR", "0.20"))

# ── Phase 8: Council Shadow Mode ─────────────────────────────────
# When True, ministers compute reasoning (R1, R2, groupthink, adjustment)
# but do NOT apply their adjustment to weighted_confidence.
# Instead, hypothetical council-adjusted confidence is computed and logged
# alongside the actual (unmodified) confidence for offline comparison.
# Set to False to let ministers fully influence probability.
COUNCIL_SHADOW_MODE = os.getenv("COUNCIL_SHADOW_MODE", "true").lower() == "true"

# ── Phase 9: Backtesting Isolation ────────────────────────────────
# When True, the conflict state model DISABLES all disk persistence:
#   - Prior files are NOT saved (conflict_prior_{CC}.json)
#   - Transition matrix is NOT saved (transition_matrix.json)
#   - State history is NOT appended (conflict_state_history.jsonl)
# The replay engine sets this at runtime.  Default False (production).
BACKTEST_MODE = os.getenv("BACKTEST_MODE", "false").lower() == "true"

# When True, backtesting runs structural-only inference (no LLM, no ministers).
# This gives the pure Bayesian baseline without cognitive variance.
STRUCTURAL_ONLY = os.getenv("STRUCTURAL_ONLY", "true").lower() == "true"

# Default sliding window size for backtesting replay (1 = daily, 3 = 3-day rolling).
BACKTEST_WINDOW_SIZE = int(os.getenv("BACKTEST_WINDOW_SIZE", "3"))

# ── Runtime output settings ───────────────────────────────────────
# When True, run.py outputs the full intelligence briefing after every query.
SHOW_FULL_BRIEFING = os.getenv("SHOW_FULL_BRIEFING", "true").lower() == "true"
# Structured log format used by run.py's _setup_logging()
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s [%(name)s] %(levelname)s %(message)s")
LOG_DATE_FORMAT = os.getenv("LOG_DATE_FORMAT", "%H:%M:%S")


def print_config():
    """Print active configuration (safe — no secrets)."""
    print(f"[Config] PROJECT_ROOT   = {PROJECT_ROOT}")
    print(f"[Config] DATA_DIR       = {DATA_DIR}")
    print(f"[Config] LLM_PROVIDER   = {LLM_PROVIDER}")
    print(f"[Config] LLM_MODEL      = {LLM_MODEL}")
    print(f"[Config] OLLAMA_BASE_URL= {OLLAMA_BASE_URL}")
    print(f"[Config] OLLAMA_L4      = {OLLAMA_LAYER4_ENABLED}")
    print(f"[Config] CHROMA_DATA_DIR= {CHROMA_DATA_DIR}")
    print(f"[Config] NEO4J_ENABLED  = {NEO4J_ENABLED}")
    print(f"[Config] REDIS_ENABLED  = {REDIS_ENABLED}")
    print(f"[Config] CORS_ORIGINS   = {CORS_ALLOWED_ORIGINS}")
    print(f"[Config] CORS_CREDS     = {CORS_ALLOW_CREDENTIALS}")
    print(f"[Config] API_KEY_STATE  = {'configured' if API_KEY else API_KEY_CONFIG_MESSAGE}")
