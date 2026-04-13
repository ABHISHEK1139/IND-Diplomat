from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import threading
import time
from typing import Any, AsyncIterator, Dict, List, Tuple

import requests
from Config.config import (
    CLOUD_LLM_MAX_TOKENS,
    L4_CLASSIFICATION_INPUT_BUDGET,
    L4_CLASSIFICATION_OUTPUT_BUDGET,
    L4_MINISTER_INPUT_BUDGET,
    L4_MINISTER_OUTPUT_BUDGET,
    L4_REDTEAM_INPUT_BUDGET,
    L4_REDTEAM_OUTPUT_BUDGET,
    L4_SYNTHESIS_INPUT_BUDGET,
    L4_SYNTHESIS_OUTPUT_BUDGET,
    LLM_OVERFLOW_POLICY,
    LOCAL_LLM_MAX_TOKENS,
    LLM_REQUEST_TIMEOUT_SEC,
    LLM_CONTEXT_WINDOW,
    LLM_MODEL as CONFIG_LLM_MODEL,
    LLM_PROVIDER as CONFIG_LLM_PROVIDER,
    OLLAMA_LAYER4_ENABLED as CONFIG_OLLAMA_LAYER4_ENABLED,
    OLLAMA_URL as CONFIG_OLLAMA_URL,
    OLLAMA_FALLBACK_ONLY as CONFIG_OLLAMA_FALLBACK_ONLY,
    OPENROUTER_API_KEY as CONFIG_OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME as CONFIG_OPENROUTER_APP_NAME,
    OPENROUTER_ENABLE_FALLBACK_CHAIN as CONFIG_OPENROUTER_ENABLE_FALLBACK_CHAIN,
    OPENROUTER_MODEL as CONFIG_OPENROUTER_MODEL,
    OPENROUTER_REASONING_EFFORT as CONFIG_OPENROUTER_REASONING_EFFORT,
    OPENROUTER_REASONING_ENABLED as CONFIG_OPENROUTER_REASONING_ENABLED,
    OPENROUTER_REASONING_EXCLUDE as CONFIG_OPENROUTER_REASONING_EXCLUDE,
    OPENROUTER_REASONING_MAX_TOKENS as CONFIG_OPENROUTER_REASONING_MAX_TOKENS,
    OPENROUTER_SITE_URL as CONFIG_OPENROUTER_SITE_URL,
    OPENROUTER_URL as CONFIG_OPENROUTER_URL,
)


LLM_PROVIDER = str(os.getenv("LLM_PROVIDER", CONFIG_LLM_PROVIDER or "ollama")).strip().lower() or "ollama"
OLLAMA_URL = str(os.getenv("OLLAMA_URL", CONFIG_OLLAMA_URL or "http://localhost:11434/api/generate")).strip()
OPENROUTER_URL = str(
    os.getenv("OPENROUTER_URL", CONFIG_OPENROUTER_URL or "https://openrouter.ai/api/v1/chat/completions")
).strip()
MODEL_NAME = str(
    os.getenv("LAYER4_MODEL", os.getenv("LLM_MODEL", CONFIG_LLM_MODEL or "deepseek-r1:8b"))
).strip() or "deepseek-r1:8b"
OPENROUTER_MODEL = str(os.getenv("OPENROUTER_MODEL", CONFIG_OPENROUTER_MODEL or MODEL_NAME)).strip() or MODEL_NAME

# Prioritised fallback chain of free OpenRouter models.
# If the primary model fails (429, timeout, error), try each in order.
# The list is ordered for reasoning-first Layer-4 work, with Qwen 3.6 first.
OPENROUTER_FALLBACK_CHAIN: List[str] = [
    "qwen/qwen3.6-plus-preview:free",                # primary reasoning choice
    "nvidia/nemotron-3-super-120b-a12b:free",        # 262k ctx
    "qwen/qwen3-next-80b-a3b-instruct:free",         # 262k ctx, strong general backup
    "nousresearch/hermes-3-llama-3.1-405b:free",    # 131k ctx
    "google/gemma-3-27b-it:free",                    # 131k ctx
    "stepfun/step-3.5-flash:free",                   # 256k ctx, fast fallback
    "meta-llama/llama-3.3-70b-instruct:free",        # 65k ctx
]
LOCAL_FALLBACK_CHAIN: List[str] = [
    "deepseek-r1:14b",
    "qwen3.5:9b",
    "deepseek-r1:8b",
]
OPENROUTER_CONTEXT_LIMITS: Dict[str, int] = {
    "qwen/qwen3.6-plus-preview:free": 262000,
    "nousresearch/hermes-3-llama-3.1-405b:free": 131000,
    "qwen/qwen3-coder:free": 262000,
    "nvidia/nemotron-3-super-120b-a12b:free": 262000,
    "stepfun/step-3.5-flash:free": 256000,
    "qwen/qwen3-next-80b-a3b-instruct:free": 262000,
    "google/gemma-3-27b-it:free": 131000,
    "meta-llama/llama-3.3-70b-instruct:free": 65000,
}

_fallback_logger = logging.getLogger("llm_fallback")
logger = logging.getLogger(__name__)
_runtime_stats_lock = threading.Lock()
_runtime_stats: Dict[str, int] = {
    "openrouter_empty_responses": 0,
    "openrouter_rate_limit_hits": 0,
    "openrouter_backoff_retries": 0,
    "openrouter_backup_attempts": 0,
    "openrouter_backup_successes": 0,
    "llm_deterministic_fallbacks": 0,
    "llm_prompt_overflow_events": 0,
    "llm_context_pack_events": 0,
    "llm_context_pack_drop_events": 0,
    "llm_context_pack_overflow_events": 0,
    "llm_over_verbose_responses": 0,
}
_cache_lock = threading.Lock()
_response_cache: Dict[str, str] = {}
_openrouter_semaphore_lock = threading.Lock()
_openrouter_semaphore: threading.BoundedSemaphore | None = None
_openrouter_semaphore_size = 0
_openrouter_degraded_lock = threading.Lock()
_openrouter_degraded_until_ts = 0.0
_openrouter_degraded_reason = ""
_provider_bootstrap_lock = threading.Lock()
_provider_bootstrap_done = False
_provider_bootstrap_candidates: List[Tuple[str, str]] = []
_provider_bootstrap_reason = "uninitialized"
_provider_active_index = 0


def _llm_trace_enabled() -> bool:
    token = str(os.getenv("LLM_TRACE_ENABLED", "0")).strip().lower()
    return token in {"1", "true", "yes", "on"}


def _openrouter_response_format_enabled() -> bool:
    token = str(os.getenv("OPENROUTER_USE_RESPONSE_FORMAT", "0")).strip().lower()
    return token in {"1", "true", "yes", "on"}


def _openrouter_fallback_chain_enabled() -> bool:
    token = str(
        os.getenv(
            "OPENROUTER_ENABLE_FALLBACK_CHAIN",
            "true" if CONFIG_OPENROUTER_ENABLE_FALLBACK_CHAIN else "false",
        )
    ).strip().lower()
    return token in {"1", "true", "yes", "on"}


def _response_cache_enabled() -> bool:
    token = str(os.getenv("LLM_RESPONSE_CACHE_ENABLED", "1")).strip().lower()
    return token in {"1", "true", "yes", "on"}


def _estimate_tokens(text: Any) -> int:
    token = str(text or "").strip()
    if not token:
        return 0
    return max(1, (len(token) + 3) // 4)


def _stage_key(task_type: str | None) -> str:
    token = str(task_type or "default").strip().lower().replace("-", "_").replace(" ", "_")
    return token or "default"


def _record_stage_metric(task_type: str | None, metric: str, delta: int) -> None:
    stage = _stage_key(task_type)
    _record_runtime_stat(f"stage_{stage}_{metric}", delta)


def _budget_for_task(task_type: str | None) -> Dict[str, int]:
    stage = _stage_key(task_type)
    if stage == "classification":
        return {
            "input": int(L4_CLASSIFICATION_INPUT_BUDGET),
            "output": int(L4_CLASSIFICATION_OUTPUT_BUDGET),
        }
    if stage in {"minister_reasoning", "round2_reasoning"}:
        return {
            "input": int(L4_MINISTER_INPUT_BUDGET),
            "output": int(L4_MINISTER_OUTPUT_BUDGET),
        }
    if stage in {"red_team", "red_team_refine", "debate"}:
        return {
            "input": int(L4_REDTEAM_INPUT_BUDGET),
            "output": int(L4_REDTEAM_OUTPUT_BUDGET),
        }
    if stage == "final_synthesis":
        return {
            "input": int(L4_SYNTHESIS_INPUT_BUDGET),
            "output": int(L4_SYNTHESIS_OUTPUT_BUDGET),
        }
    return {
        "input": 0,
        "output": 0,
    }


def _is_layer4_reasoning_stage(task_type: str | None) -> bool:
    return _stage_key(task_type) in {
        "classification",
        "minister_reasoning",
        "round2_reasoning",
        "red_team",
        "red_team_refine",
        "debate",
        "final_synthesis",
    }


def _overflow_policy() -> str:
    return str(os.getenv("LLM_OVERFLOW_POLICY", str(LLM_OVERFLOW_POLICY))).strip().lower() or "pack_then_fail"


def _ollama_layer4_enabled() -> bool:
    token = str(
        os.getenv(
            "OLLAMA_LAYER4_ENABLED",
            "true" if CONFIG_OLLAMA_LAYER4_ENABLED else "false",
        )
    ).strip().lower()
    return token in {"1", "true", "yes", "on"}


def _ollama_fallback_only() -> bool:
    token = str(
        os.getenv(
            "OLLAMA_FALLBACK_ONLY",
            "true" if CONFIG_OLLAMA_FALLBACK_ONLY else "false",
        )
    ).strip().lower()
    return token in {"1", "true", "yes", "on"}


def _strip_reasoning_blocks(text: Any) -> str:
    token = str(text or "")
    return re.sub(r"<think>.*?</think>", "", token, flags=re.DOTALL).strip()


def _safe_positive_int(value: Any, default: int) -> int:
    try:
        token = int(value)
        if token > 0:
            return token
    except Exception:
        pass
    return int(default)


def _safe_nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        token = int(value)
        if token >= 0:
            return token
    except Exception:
        pass
    return int(default)


def _safe_positive_float(value: Any, default: float) -> float:
    try:
        token = float(value)
        if token > 0:
            return token
    except Exception:
        pass
    return float(default)


def _record_runtime_stat(name: str, delta: int = 1) -> None:
    with _runtime_stats_lock:
        _runtime_stats[name] = int(_runtime_stats.get(name, 0)) + int(delta)


def reset_llm_runtime_stats() -> None:
    with _runtime_stats_lock:
        for key in list(_runtime_stats.keys()):
            _runtime_stats[key] = 0


def get_llm_runtime_stats() -> Dict[str, int]:
    with _runtime_stats_lock:
        return dict(_runtime_stats)


def note_llm_deterministic_fallback(label: str = "") -> None:
    _record_runtime_stat("llm_deterministic_fallbacks", 1)
    if label:
        _fallback_logger.warning("[DEGRADED] Deterministic fallback used for %s", label)


def _default_max_tokens(provider: str) -> int:
    if provider == "openrouter":
        env_default = os.getenv("CLOUD_LLM_MAX_TOKENS", str(CLOUD_LLM_MAX_TOKENS))
        return _safe_positive_int(env_default, CLOUD_LLM_MAX_TOKENS)
    env_default = os.getenv("LOCAL_LLM_MAX_TOKENS", str(LOCAL_LLM_MAX_TOKENS))
    return _safe_positive_int(env_default, LOCAL_LLM_MAX_TOKENS)


def _resolve_max_tokens(provider: str, value: int | None) -> int:
    if value is None:
        return _default_max_tokens(provider)
    return _safe_positive_int(value, _default_max_tokens(provider))


def _default_timeout_seconds() -> int:
    env_default = os.getenv("LLM_REQUEST_TIMEOUT_SEC", str(LLM_REQUEST_TIMEOUT_SEC))
    return _safe_positive_int(env_default, LLM_REQUEST_TIMEOUT_SEC)


def _resolve_timeout_seconds(value: int | None) -> int:
    if value is None:
        return _default_timeout_seconds()
    return _safe_positive_int(value, _default_timeout_seconds())


def _openrouter_model_max_tokens_map() -> Dict[str, int]:
    """
    Parse per-model output caps from env.
    Format:
      OPENROUTER_MODEL_MAX_TOKENS="nvidia/nemotron-3-super-120b-a12b:free=8000,stepfun/step-3.5-flash:free=3200,*=6000"
    Matching precedence:
      1) exact model id
      2) prefix wildcard ending with '*'
      3) '*' global default
    """
    raw = str(os.getenv("OPENROUTER_MODEL_MAX_TOKENS", "")).strip()
    if not raw:
        return {}
    out: Dict[str, int] = {}
    parts = [p.strip() for p in re.split(r"[\n,]+", raw) if p and p.strip()]
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = str(key).strip()
        cap = _safe_positive_int(value, 0)
        if key and cap > 0:
            out[key] = cap
    return out


def _resolve_openrouter_model_max_tokens(model: str, requested: int) -> int:
    req = max(256, int(requested))
    model_key = str(model or "").strip()
    mapping = _openrouter_model_max_tokens_map()

    if model_key in mapping:
        return max(256, min(req, int(mapping[model_key])))

    # Prefix wildcard entries, e.g. "stepfun/*=3200"
    for pattern, cap in mapping.items():
        if pattern.endswith("*") and pattern != "*":
            prefix = pattern[:-1]
            if prefix and model_key.startswith(prefix):
                return max(256, min(req, int(cap)))

    if "*" in mapping:
        return max(256, min(req, int(mapping["*"])))

    # Backward compatibility for older env setup
    legacy_stepfun = _safe_positive_int(os.getenv("STEPFUN_LIGHT_MAX_TOKENS", "0"), 0)
    if legacy_stepfun > 0 and model_key == "stepfun/step-3.5-flash:free":
        return max(256, min(req, int(legacy_stepfun)))

    return req


def _prompt_control_enabled() -> bool:
    token = str(os.getenv("LLM_PROMPT_CONTROL_ENABLED", "true")).strip().lower()
    return token in {"1", "true", "yes", "on"}


def _openrouter_failfast_on_429() -> bool:
    token = str(os.getenv("OPENROUTER_FAILFAST_ON_429", "true")).strip().lower()
    return token in {"1", "true", "yes", "on"}


def _openrouter_failfast_on_network_error() -> bool:
    token = str(os.getenv("OPENROUTER_FAILFAST_ON_NETWORK_ERROR", "true")).strip().lower()
    return token in {"1", "true", "yes", "on"}


def _openrouter_degraded_ttl_seconds() -> int:
    return _safe_positive_int(os.getenv("OPENROUTER_DEGRADED_TTL_SEC", "1800"), 1800)


def _mark_openrouter_temporarily_degraded(reason: str, ttl_seconds: int | None = None) -> None:
    global _openrouter_degraded_until_ts, _openrouter_degraded_reason
    ttl = max(60, int(ttl_seconds if ttl_seconds is not None else _openrouter_degraded_ttl_seconds()))
    until_ts = time.time() + float(ttl)
    with _openrouter_degraded_lock:
        _openrouter_degraded_until_ts = max(float(_openrouter_degraded_until_ts), until_ts)
        _openrouter_degraded_reason = str(reason or "unknown").strip()[:200]
    _fallback_logger.warning(
        "[OPENROUTER-DEGRADED] Cloud path paused for %ds due to: %s",
        ttl,
        str(reason or "unknown")[:160],
    )


def _openrouter_degraded_remaining_seconds() -> int:
    with _openrouter_degraded_lock:
        remaining = int(max(0.0, float(_openrouter_degraded_until_ts) - time.time()))
    return max(0, remaining)


def _openrouter_temporarily_degraded() -> bool:
    return _openrouter_degraded_remaining_seconds() > 0


def _prompt_control_instruction(json_mode: bool) -> str:
    custom = str(os.getenv("LLM_PROMPT_CONTROL_TEXT", "")).strip()
    if custom:
        return custom
    if json_mode:
        return (
            "Return one complete JSON object only. Put the structured output first, "
            "keep rationale concise, and avoid unnecessary verbosity."
        )
    return "Keep the answer concise, decision-focused, and avoid unnecessary verbosity."


def _apply_prompt_control(system_prompt: str, json_mode: bool) -> str:
    base = str(system_prompt or "").strip()
    if not _prompt_control_enabled():
        return base
    control = _prompt_control_instruction(json_mode)
    if not control:
        return base
    return f"{base}\n\n{control}".strip()


def _local_fallback_models() -> List[str]:
    raw = str(os.getenv("OLLAMA_FALLBACK_MODELS", "")).strip()
    if raw:
        candidates = [part.strip() for part in re.split(r"[\n,]+", raw) if part and part.strip()]
    else:
        candidates = list(LOCAL_FALLBACK_CHAIN)
    deduped: List[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _ordered_mixed_candidates(primary_model: str) -> List[Tuple[str, str]]:
    cloud_order: List[str] = []
    if primary_model:
        cloud_order.append(str(primary_model).strip())
    for model in OPENROUTER_FALLBACK_CHAIN:
        if model and model not in cloud_order:
            cloud_order.append(model)
    ordered: List[Tuple[str, str]] = []
    for model in cloud_order:
        ordered.append(("openrouter", model))
    # Local models are always last-resort after all cloud attempts.
    for model in _local_fallback_models():
        ordered.append(("ollama", model))

    deduped: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    for provider, model in ordered:
        key = (str(provider).strip().lower(), str(model).strip())
        if key[1] and key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped


def _openrouter_models_url() -> str:
    base = str(OPENROUTER_URL or "").strip()
    if "/chat/completions" in base:
        return base.replace("/chat/completions", "/models")
    if base.endswith("/models"):
        return base
    if base.endswith("/api/v1"):
        return f"{base}/models"
    return "https://openrouter.ai/api/v1/models"


def _startup_probe_timeout_seconds() -> float:
    return max(1.0, min(10.0, _safe_positive_float(os.getenv("LLM_STARTUP_PROBE_TIMEOUT_SEC", "3"), 3.0)))


def _openrouter_startup_available(api_key: str) -> bool:
    if not str(api_key or "").strip():
        return False
    if str(os.getenv("OPENROUTER_STARTUP_PROBE", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
        return True
    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    url = _openrouter_models_url()
    try:
        response = requests.get(url, headers=headers, timeout=_startup_probe_timeout_seconds())
        if response.status_code < 400:
            return True
        _fallback_logger.warning(
            "[BOOTSTRAP] OpenRouter probe failed status=%s url=%s",
            response.status_code,
            url,
        )
        return False
    except Exception as exc:
        _fallback_logger.warning("[BOOTSTRAP] OpenRouter probe error: %s", exc)
        return False


def _ollama_startup_available() -> bool:
    if str(os.getenv("OLLAMA_STARTUP_PROBE", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
        return True
    generate_url = str(OLLAMA_URL or "").strip() or "http://localhost:11434/api/generate"
    base = generate_url
    marker = "/api/"
    if marker in generate_url:
        base = generate_url.split(marker, 1)[0]
    tags_url = f"{base}/api/tags"
    try:
        response = requests.get(tags_url, timeout=_startup_probe_timeout_seconds())
        return response.status_code < 400
    except Exception:
        return False


def _ensure_provider_bootstrap(primary_model: str) -> None:
    global _provider_bootstrap_done, _provider_bootstrap_candidates, _provider_bootstrap_reason, _provider_active_index
    with _provider_bootstrap_lock:
        if _provider_bootstrap_done:
            return

        ordered = _ordered_mixed_candidates(primary_model)
        cloud = [c for c in ordered if c[0] == "openrouter"]
        local = [c for c in ordered if c[0] == "ollama"]

        openrouter_ok = _openrouter_startup_available(str(CONFIG_OPENROUTER_API_KEY or "").strip())
        ollama_ok = _ollama_startup_available()

        if openrouter_ok:
            bootstrap = cloud + local
            reason = "openrouter_available_on_startup"
        elif ollama_ok:
            bootstrap = local + cloud
            reason = "ollama_only_on_startup"
        else:
            bootstrap = ordered
            reason = "no_provider_probe_success_using_default_chain"

        deduped: List[Tuple[str, str]] = []
        seen: set[Tuple[str, str]] = set()
        for provider, model in bootstrap:
            key = (str(provider).strip().lower(), str(model).strip())
            if key[1] and key not in seen:
                seen.add(key)
                deduped.append(key)

        _provider_bootstrap_candidates = deduped or ordered
        _provider_bootstrap_reason = reason
        _provider_active_index = 0
        _provider_bootstrap_done = True

        head = _provider_bootstrap_candidates[0] if _provider_bootstrap_candidates else ("none", "none")
        _fallback_logger.info(
            "[BOOTSTRAP] Provider routing initialized: reason=%s active=%s/%s chain_size=%d",
            _provider_bootstrap_reason,
            head[0],
            head[1],
            len(_provider_bootstrap_candidates),
        )


def _candidate_chain_for_call(primary_model: str, allow_local_fallback: bool) -> Tuple[List[Tuple[str, str]], int]:
    _ensure_provider_bootstrap(primary_model)
    with _provider_bootstrap_lock:
        all_candidates = list(_provider_bootstrap_candidates or _ordered_mixed_candidates(primary_model))
        start_idx = int(max(0, min(_provider_active_index, max(0, len(all_candidates) - 1)))) if all_candidates else 0

    if allow_local_fallback:
        filtered = list(all_candidates)
    else:
        filtered = [candidate for candidate in all_candidates if candidate[0] != "ollama"]
        if not filtered:
            filtered = [candidate for candidate in all_candidates if candidate[0] == "openrouter"]

    if not filtered:
        return [], 0

    try:
        start_candidate = all_candidates[start_idx]
    except Exception:
        return filtered, 0

    if start_candidate in filtered:
        filtered_start_idx = filtered.index(start_candidate)
    else:
        filtered_start_idx = 0
    return filtered, filtered_start_idx


def _set_active_candidate(provider: str, model: str, candidates: List[Tuple[str, str]], idx: int) -> None:
    global _provider_active_index
    with _provider_bootstrap_lock:
        target = (str(provider).strip().lower(), str(model).strip())
        bootstrap = list(_provider_bootstrap_candidates or [])
        if target in bootstrap:
            _provider_active_index = bootstrap.index(target)
            return
        try:
            if target in candidates:
                _provider_active_index = max(0, candidates.index(target))
            else:
                _provider_active_index = max(0, int(idx))
        except Exception:
            _provider_active_index = 0


def _response_cache_limit() -> int:
    return _safe_positive_int(os.getenv("LLM_RESPONSE_CACHE_SIZE", "128"), 128)


def _build_cache_key(
    *,
    provider: str,
    model: str,
    task_type: str | None,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    json_mode: bool,
    max_tokens: int,
    reasoning: Dict[str, Any] | None,
) -> str:
    fingerprint = "\n".join(
        [
            str(provider),
            str(model),
            _stage_key(task_type),
            f"{float(temperature):.4f}",
            "json" if json_mode else "text",
            str(int(max_tokens)),
            str(reasoning or {}),
            str(system_prompt or ""),
            str(user_prompt or ""),
        ]
    )
    return hashlib.sha256(fingerprint.encode("utf-8", errors="ignore")).hexdigest()


def _cache_get(key: str) -> str | None:
    if not _response_cache_enabled():
        return None
    with _cache_lock:
        return _response_cache.get(str(key))


def _cache_put(key: str, value: str) -> None:
    if not _response_cache_enabled():
        return
    if not str(value or "").strip():
        return
    with _cache_lock:
        _response_cache[str(key)] = str(value)
        while len(_response_cache) > _response_cache_limit():
            oldest_key = next(iter(_response_cache))
            _response_cache.pop(oldest_key, None)


def _openrouter_retry_limit() -> int:
    default_retries = 0 if _openrouter_failfast_on_429() else 2
    return _safe_nonnegative_int(os.getenv("OPENROUTER_429_MAX_RETRIES", str(default_retries)), default_retries)


def _openrouter_backoff_base_seconds() -> float:
    return _safe_positive_float(os.getenv("OPENROUTER_429_BASE_DELAY_SEC", "2.0"), 2.0)


def _openrouter_backoff_max_seconds() -> float:
    return _safe_positive_float(os.getenv("OPENROUTER_429_MAX_DELAY_SEC", "12.0"), 12.0)


def _openrouter_backoff_jitter_seconds() -> float:
    return max(0.0, _safe_positive_float(os.getenv("OPENROUTER_429_JITTER_SEC", "0.5"), 0.5))


def _extract_retry_after_seconds(response: requests.Response) -> float | None:
    raw = str(response.headers.get("Retry-After", "") or "").strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except Exception:
        return None


def _openrouter_max_concurrency() -> int:
    return _safe_positive_int(os.getenv("OPENROUTER_MAX_CONCURRENCY", "2"), 2)


def _get_openrouter_semaphore() -> threading.BoundedSemaphore:
    global _openrouter_semaphore, _openrouter_semaphore_size
    desired_size = _openrouter_max_concurrency()
    with _openrouter_semaphore_lock:
        if _openrouter_semaphore is None or _openrouter_semaphore_size != desired_size:
            _openrouter_semaphore = threading.BoundedSemaphore(desired_size)
            _openrouter_semaphore_size = desired_size
        return _openrouter_semaphore


def _build_openrouter_reasoning() -> Dict[str, Any] | None:
    enabled = str(
        os.getenv(
            "OPENROUTER_REASONING_ENABLED",
            "true" if CONFIG_OPENROUTER_REASONING_ENABLED else "false",
        )
    ).strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None

    reasoning: Dict[str, Any] = {
        "enabled": True,
        "exclude": str(
            os.getenv(
                "OPENROUTER_REASONING_EXCLUDE",
                "true" if CONFIG_OPENROUTER_REASONING_EXCLUDE else "false",
            )
        ).strip().lower() in {"1", "true", "yes", "on"},
    }

    effort = str(
        os.getenv("OPENROUTER_REASONING_EFFORT", CONFIG_OPENROUTER_REASONING_EFFORT or "medium")
    ).strip().lower()
    if effort and effort not in {"none", "off", "false", "0"}:
        reasoning["effort"] = effort

    max_reasoning_tokens = _safe_nonnegative_int(
        os.getenv(
            "OPENROUTER_REASONING_MAX_TOKENS",
            str(CONFIG_OPENROUTER_REASONING_MAX_TOKENS),
        ),
        CONFIG_OPENROUTER_REASONING_MAX_TOKENS,
    )
    if max_reasoning_tokens > 0:
        reasoning.pop("effort", None)
        reasoning["max_tokens"] = max_reasoning_tokens

    return reasoning


def _resolve_model(provider: str, model: str | None) -> str:
    candidate = str(model or "").strip()
    if candidate:
        return candidate
    if provider == "openrouter":
        return OPENROUTER_MODEL
    return MODEL_NAME


def _resolve_url(provider: str, url: str | None) -> str:
    candidate = str(url or "").strip()
    if candidate:
        return candidate
    if provider == "openrouter":
        return OPENROUTER_URL
    return OLLAMA_URL


def _provider_profile(provider: str, model: str, max_tokens: int) -> Dict[str, int]:
    if provider == "openrouter":
        model_limit = int(OPENROUTER_CONTEXT_LIMITS.get(str(model or "").strip(), 64000))
        safe_total = max(4096, model_limit - 2048)
        max_input = max(2048, safe_total - max(256, int(max_tokens)))
        return {
            "max_input_tokens": max_input,
            "max_output_tokens": max(256, min(int(max_tokens), safe_total)),
            "safe_total_tokens": safe_total,
        }

    safe_total = max(4096, int(LLM_CONTEXT_WINDOW) - 1024)
    max_input = max(2048, safe_total - max(256, int(max_tokens)))
    return {
        "max_input_tokens": max_input,
        "max_output_tokens": max(256, min(int(max_tokens), safe_total)),
        "safe_total_tokens": safe_total,
    }


def _extract_structured_json_text(raw: Any) -> str:
    text = _strip_reasoning_blocks(raw)
    if not text:
        return ""

    candidates = [text]
    start_obj = text.find("{")
    end_obj = text.rfind("}")
    if start_obj != -1 and end_obj > start_obj:
        candidates.append(text[start_obj : end_obj + 1])
    start_arr = text.find("[")
    end_arr = text.rfind("]")
    if start_arr != -1 and end_arr > start_arr:
        candidates.append(text[start_arr : end_arr + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    return ""


def _extract_openrouter_text(data: Dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        text_parts: List[str] = []
        for part in content:
            if isinstance(part, dict) and str(part.get("type", "")).lower() == "text":
                text_parts.append(str(part.get("text", "")))
            else:
                text_parts.append(str(part))
        return "".join(text_parts).strip()
    return str(content or "").strip()


def _append_trace(trace_entry: str) -> None:
    try:
        default_trace_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "llm_trace.txt",
        )
        trace_path = str(os.getenv("LLM_TRACE_PATH", default_trace_path) or default_trace_path)
        with open(trace_path, "a", encoding="utf-8") as handle:
            handle.write(trace_entry)
    except Exception:
        pass


class LocalLLM:
    """
    Shared text-generation gateway for either local Ollama or OpenRouter.
    """

    def __init__(
        self,
        model: str | None = None,
        url: str | None = None,
        provider: str | None = None,
    ):
        self.provider = str(provider or LLM_PROVIDER or "ollama").strip().lower() or "ollama"
        self.model = _resolve_model(self.provider, model)
        self.url = _resolve_url(self.provider, url)
        self.openrouter_api_key = str(CONFIG_OPENROUTER_API_KEY or "").strip()
        self.openrouter_site_url = str(
            os.getenv("OPENROUTER_SITE_URL", CONFIG_OPENROUTER_SITE_URL or "")
        ).strip()
        self.openrouter_app_name = str(
            os.getenv("OPENROUTER_APP_NAME", CONFIG_OPENROUTER_APP_NAME or "IND-Diplomat")
        ).strip()
        self.openrouter_reasoning = _build_openrouter_reasoning()
        self.last_response_meta: Dict[str, Any] = {}

    def _clear_last_response_meta(self) -> None:
        self.last_response_meta = {}

    def _set_last_response_meta(self, **kwargs: Any) -> None:
        self.last_response_meta = {str(key): value for key, value in kwargs.items() if value is not None}

    def _effective_provider(self, task_type: str | None) -> str:
        if self.provider == "openrouter":
            return "openrouter"
        if _is_layer4_reasoning_stage(task_type) and self.openrouter_api_key:
            if _ollama_fallback_only() or not _ollama_layer4_enabled():
                return "openrouter"
        return self.provider

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        timeout: int | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
        task_type: str | None = None,
        context_pack: Any | None = None,
        allow_local_fallback: bool | None = None,
    ) -> str:
        effective_provider = self._effective_provider(task_type)
        self._clear_last_response_meta()
        resolved_timeout = _resolve_timeout_seconds(timeout)
        budget = _budget_for_task(task_type)
        budget_output = int(budget.get("output", 0) or 0)
        if budget_output > 0:
            resolved_max_tokens = min(_resolve_max_tokens(effective_provider, max_tokens), budget_output)
        else:
            resolved_max_tokens = _resolve_max_tokens(effective_provider, max_tokens)

        prompt_text = str(user_prompt or "")
        if context_pack is not None:
            try:
                prompt_text = str(getattr(context_pack, "rendered_prompt", "") or prompt_text or "")
                if not prompt_text and hasattr(context_pack, "render"):
                    prompt_text = str(context_pack.render() or "")
            except Exception:
                prompt_text = str(user_prompt or "")

            _record_runtime_stat("llm_context_pack_events", 1)
            _record_stage_metric(task_type, "context_pack_events", 1)
            dropped = list(getattr(context_pack, "dropped_sections", []) or [])
            if dropped:
                _record_runtime_stat("llm_context_pack_drop_events", len(dropped))
                _record_stage_metric(task_type, "context_pack_drop_events", len(dropped))
            if bool(getattr(context_pack, "overflow", False)):
                _record_runtime_stat("llm_context_pack_overflow_events", 1)
                _record_stage_metric(task_type, "context_pack_overflow_events", 1)

        input_tokens = _estimate_tokens(system_prompt) + _estimate_tokens(prompt_text)
        budget_input = int(budget.get("input", 0) or 0)
        if budget_input > 0 and input_tokens > budget_input:
            _record_runtime_stat("llm_prompt_overflow_events", 1)
            _record_stage_metric(task_type, "prompt_overflow_events", 1)
            return (
                f"LLM_ERROR: INPUT_BUDGET_EXCEEDED stage={_stage_key(task_type)} "
                f"tokens={input_tokens} limit={budget_input} policy={_overflow_policy()}"
            )

        cache_key = _build_cache_key(
            provider=effective_provider,
            model=_resolve_model(effective_provider, self.model if effective_provider == self.provider else None),
            task_type=task_type,
            system_prompt=system_prompt,
            user_prompt=prompt_text,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=resolved_max_tokens,
            reasoning=self.openrouter_reasoning if effective_provider == "openrouter" else None,
        )
        cached = _cache_get(cache_key)
        if cached is not None:
            return str(cached)

        original_provider = self.provider
        original_model = self.model
        original_url = self.url
        if allow_local_fallback is None:
            if _is_layer4_reasoning_stage(task_type):
                allow_local_fallback = bool(_ollama_fallback_only() or _ollama_layer4_enabled())
            else:
                allow_local_fallback = True

        try:
            self.provider = effective_provider
            if effective_provider != original_provider:
                self.model = _resolve_model(effective_provider, None)
                self.url = _resolve_url(effective_provider, None)

            if effective_provider == "openrouter":
                if _openrouter_fallback_chain_enabled():
                    result = self._generate_openrouter_with_fallback(
                        system_prompt=system_prompt,
                        user_prompt=prompt_text,
                        temperature=temperature,
                        timeout=resolved_timeout,
                        json_mode=json_mode,
                        max_tokens=resolved_max_tokens,
                        allow_local_fallback=bool(allow_local_fallback),
                    )
                else:
                    result = self._generate_openrouter_with_backup_models(
                        system_prompt=system_prompt,
                        user_prompt=prompt_text,
                        temperature=temperature,
                        timeout=resolved_timeout,
                        json_mode=json_mode,
                        max_tokens=resolved_max_tokens,
                        allow_local_fallback=bool(allow_local_fallback),
                    )
            else:
                result = self._generate_ollama(
                    system_prompt=system_prompt,
                    user_prompt=prompt_text,
                    temperature=temperature,
                    timeout=resolved_timeout,
                    json_mode=json_mode,
                    max_tokens=resolved_max_tokens,
                )

            if json_mode and not str(result).startswith("LLM_ERROR:"):
                normalized_json = _extract_structured_json_text(result)
                if normalized_json:
                    result = normalized_json
                else:
                    result = self._repair_json_response(
                        system_prompt=system_prompt,
                        user_prompt=prompt_text,
                        temperature=temperature,
                        timeout=resolved_timeout,
                        max_tokens=resolved_max_tokens,
                    )
        finally:
            self.provider = original_provider
            self.model = original_model
            self.url = original_url

        if not str(result).startswith("LLM_ERROR:"):
            _record_stage_metric(task_type, "calls", 1)
            _record_stage_metric(task_type, "input_tokens", input_tokens)
            output_tokens = _estimate_tokens(result)
            _record_stage_metric(task_type, "output_tokens", output_tokens)
            response_meta = dict(getattr(self, "last_response_meta", {}) or {})
            finish_reason = str(response_meta.get("finish_reason", "") or "").strip().lower()
            if finish_reason:
                _record_stage_metric(task_type, f"finish_reason_{finish_reason}", 1)
            reported_prompt_tokens = _safe_nonnegative_int(response_meta.get("prompt_tokens", 0), 0)
            reported_completion_tokens = _safe_nonnegative_int(response_meta.get("completion_tokens", 0), 0)
            reported_total_tokens = _safe_nonnegative_int(response_meta.get("total_tokens", 0), 0)
            if reported_prompt_tokens > 0:
                _record_stage_metric(task_type, "reported_prompt_tokens", reported_prompt_tokens)
            if reported_completion_tokens > 0:
                _record_stage_metric(task_type, "reported_completion_tokens", reported_completion_tokens)
            if reported_total_tokens > 0:
                _record_stage_metric(task_type, "reported_total_tokens", reported_total_tokens)
            effective_output_tokens = reported_completion_tokens or output_tokens
            if resolved_max_tokens > 0 and effective_output_tokens >= max(64, int(resolved_max_tokens * 0.85)):
                _record_runtime_stat("llm_over_verbose_responses", 1)
                _record_stage_metric(task_type, "over_verbose_responses", 1)
            elif resolved_max_tokens > 0 and effective_output_tokens > 0 and effective_output_tokens <= int(resolved_max_tokens * 0.5):
                _record_stage_metric(task_type, "under_budget_responses", 1)
            logger.info(
                "[LLM] stage=%s provider=%s model=%s finish=%s prompt=%d completion=%d total=%d budget=%d",
                _stage_key(task_type),
                effective_provider,
                _resolve_model(effective_provider, self.model if effective_provider == self.provider else None),
                finish_reason or "unknown",
                reported_prompt_tokens or input_tokens,
                effective_output_tokens,
                reported_total_tokens or (input_tokens + effective_output_tokens),
                resolved_max_tokens,
            )
            _cache_put(cache_key, str(result))
        return str(result)

    # â”€â”€ Resilient OpenRouter fallback chain â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _generate_current_provider_once(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: int,
        json_mode: bool,
        max_tokens: int,
    ) -> str:
        if self.provider == "openrouter":
            return self._generate_openrouter(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                timeout=timeout,
                json_mode=json_mode,
                max_tokens=max_tokens,
            )
        return self._generate_ollama(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            timeout=timeout,
            json_mode=json_mode,
            max_tokens=max_tokens,
        )

    def _repair_json_response(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: int,
        max_tokens: int,
    ) -> str:
        repair_system = (
            str(system_prompt or "").rstrip()
            + "\n\nRetry mode: return only the complete JSON object. "
              "Put all reasoning inside JSON fields only. No prose before or after JSON."
        ).strip()
        repair_user = (
            str(user_prompt or "").rstrip()
            + "\n\nReturn the complete structured JSON now. "
              "If space is limited, keep rationale brief but complete."
        ).strip()
        retry_max_tokens = max(256, min(int(max_tokens), 1024))
        repaired = self._generate_current_provider_once(
            system_prompt=repair_system,
            user_prompt=repair_user,
            temperature=min(float(temperature), 0.1),
            timeout=timeout,
            json_mode=True,
            max_tokens=retry_max_tokens,
        )
        normalized = _extract_structured_json_text(repaired)
        if normalized:
            return normalized
        return str(repaired)

    def _generate_openrouter_with_backup_models(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: int,
        json_mode: bool,
        max_tokens: int,
        allow_local_fallback: bool,
    ) -> str:
        # Keep backward compatibility for callers using the old entrypoint,
        # but route through the mixed fallback executor for consistent ordering.
        return self._generate_openrouter_with_fallback(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            timeout=timeout,
            json_mode=json_mode,
            max_tokens=max_tokens,
            allow_local_fallback=allow_local_fallback,
        )

    def _generate_ollama(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: int,
        json_mode: bool,
        max_tokens: int,
    ) -> str:
        effective_system_prompt = _apply_prompt_control(system_prompt, json_mode)
        payload = {
            "model": self.model,
            "prompt": f"[SYSTEM]\n{effective_system_prompt}\n\n[USER]\n{user_prompt}",
            "stream": False,
            "options": {
                "temperature": float(temperature),
                "num_ctx": LLM_CONTEXT_WINDOW,
                "num_predict": max(128, int(max_tokens)),
            },
        }
        if json_mode:
            payload["format"] = "json"

        try:
            trace_enabled = _llm_trace_enabled()
            trace_entry = ""
            if trace_enabled:
                trace_entry = "========== LLM CALL ==========\n"
                trace_entry += f"PROVIDER: {self.provider} | MODEL: {self.model} | JSON: {json_mode}\n\n"
                trace_entry += f"--- SYSTEM PROMPT ---\n{effective_system_prompt}\n\n"
                trace_entry += f"--- USER PROMPT ---\n{user_prompt}\n\n"

            response = requests.post(self.url, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            result_text = _strip_reasoning_blocks(data.get("response", ""))
            self._set_last_response_meta(
                provider="ollama",
                model=self.model,
                finish_reason=str(data.get("done_reason", "stop") or "stop").strip().lower(),
                prompt_tokens=_safe_nonnegative_int(data.get("prompt_eval_count", 0), 0),
                completion_tokens=_safe_nonnegative_int(data.get("eval_count", 0), 0),
                total_tokens=(
                    _safe_nonnegative_int(data.get("prompt_eval_count", 0), 0)
                    + _safe_nonnegative_int(data.get("eval_count", 0), 0)
                ),
            )

            if trace_enabled:
                trace_entry += f"--- RESPONSE ---\n{result_text}\n"
                trace_entry += "==============================\n\n"
                _append_trace(trace_entry)

            return result_text
        except Exception as exc:
            return f"LLM_ERROR: {exc}"

    def _generate_openrouter_with_fallback(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: int,
        json_mode: bool,
        max_tokens: int,
        allow_local_fallback: bool,
    ) -> str:
        """
        Online-first fallback order, then local last-resort:
        1) Nemotron, 2) Qwen3 Next, 3) Hermes,
        4) Gemma, 5) StepFun(light-only), 6) Llama 70B,
        7) local DeepSeek-R1 14B, 8) local Qwen3.5 9B, 9) local DeepSeek-R1 8B.
        """
        original_provider = self.provider
        original_model = self.model
        original_url = self.url
        errors: List[str] = []
        candidates, start_index = _candidate_chain_for_call(original_model, bool(allow_local_fallback))
        if not candidates:
            return "LLM_ERROR: No fallback candidates available after startup routing."
        degraded_logged = False
        try:
            # Pass 1: sticky provider first, then later candidates.
            # Pass 2: only if all later candidates fail, wrap to earlier ones.
            visit_order: List[int] = list(range(start_index, len(candidates)))
            if start_index > 0:
                visit_order.extend(range(0, start_index))

            for visit_pos, idx in enumerate(visit_order):
                candidate_provider, candidate_model = candidates[idx]
                if candidate_provider == "openrouter" and _openrouter_temporarily_degraded():
                    if not degraded_logged:
                        degraded_logged = True
                        _fallback_logger.warning(
                            "[OPENROUTER-DEGRADED] Skipping cloud candidates for %ds and using local fallback path.",
                            _openrouter_degraded_remaining_seconds(),
                        )
                    continue

                self.provider = candidate_provider
                self.model = candidate_model
                self.url = _resolve_url(candidate_provider, None)

                label = "PRIMARY" if visit_pos == 0 else f"FALLBACK-{visit_pos}"
                _fallback_logger.info("[%s] Trying %s model: %s", label, candidate_provider, candidate_model)

                candidate_max_tokens = int(max_tokens)
                if candidate_provider == "openrouter":
                    candidate_max_tokens = _resolve_openrouter_model_max_tokens(
                        candidate_model,
                        candidate_max_tokens,
                    )

                if candidate_provider == "openrouter":
                    result = self._generate_openrouter(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=temperature,
                        timeout=timeout,
                        json_mode=json_mode,
                        max_tokens=candidate_max_tokens,
                    )
                else:
                    local_max_tokens = _resolve_max_tokens("ollama", min(candidate_max_tokens, LOCAL_LLM_MAX_TOKENS))
                    result = self._generate_ollama(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=temperature,
                        timeout=timeout,
                        json_mode=json_mode,
                        max_tokens=local_max_tokens,
                    )

                if not str(result).startswith("LLM_ERROR:"):
                    _set_active_candidate(candidate_provider, candidate_model, candidates, idx)
                    if visit_pos > 0:
                        _fallback_logger.warning(
                            "[FALLBACK] Active model '%s' failed. "
                            "Succeeded with %s model '%s' (attempt %d/%d).",
                            candidates[start_index][1] if 0 <= start_index < len(candidates) else original_model,
                            candidate_provider,
                            candidate_model,
                            visit_pos + 1,
                            len(visit_order),
                        )
                    return result

                error_msg = str(result)
                errors.append(f"{candidate_provider}:{candidate_model}: {error_msg}")
                _fallback_logger.warning(
                    "[%s] %s model '%s' failed: %s",
                    label,
                    candidate_provider,
                    candidate_model,
                    error_msg[:200],
                )
                if visit_pos < len(visit_order) - 1:
                    time.sleep(1.0)

            _fallback_logger.error(
                "[TOTAL-FAILURE] All %d configured fallback candidates failed. Errors: %s",
                len(visit_order),
                "; ".join(e[:120] for e in errors[-3:]),
            )
            return (
                f"LLM_ERROR: All {len(visit_order)} fallback candidates failed. "
                f"Last: {errors[-1][:200] if errors else 'unknown'}"
            )
        finally:
            self.provider = original_provider
            self.model = original_model
            self.url = original_url

    def _generate_openrouter(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: int,
        json_mode: bool,
        max_tokens: int,
    ) -> str:
        """
        Override legacy character-based compaction. The caller must provide a
        curated prompt that fits stage budgets; if the provider window would be
        exceeded we fail explicitly instead of trimming the middle.
        """
        if not self.openrouter_api_key:
            return "LLM_ERROR: OPENROUTER_API_KEY is not configured"

        effective_system_prompt = _apply_prompt_control(system_prompt, json_mode)
        if json_mode:
            effective_system_prompt = (
                effective_system_prompt.rstrip()
                + "\n\nReturn exactly one valid JSON object and no markdown fences. "
                  "Put the structured answer first and keep it complete."
            ).strip()

        prompt_tokens = _estimate_tokens(effective_system_prompt) + _estimate_tokens(user_prompt)
        provider_profile = _provider_profile("openrouter", self.model, max_tokens)
        if prompt_tokens > int(provider_profile["max_input_tokens"]):
            _record_runtime_stat("llm_prompt_overflow_events", 1)
            return (
                f"LLM_ERROR: PROVIDER_WINDOW_EXCEEDED model={self.model} "
                f"tokens={prompt_tokens} limit={provider_profile['max_input_tokens']}"
            )

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": effective_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(temperature),
            "max_tokens": max(128, min(int(max_tokens), int(provider_profile["max_output_tokens"]))),
        }
        if json_mode and _openrouter_response_format_enabled():
            payload["response_format"] = {"type": "json_object"}
        if self.openrouter_reasoning:
            payload["reasoning"] = dict(self.openrouter_reasoning)

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        if self.openrouter_site_url:
            headers["HTTP-Referer"] = self.openrouter_site_url
        if self.openrouter_app_name:
            headers["X-Title"] = self.openrouter_app_name

        trace_enabled = _llm_trace_enabled()
        trace_entry = ""
        if trace_enabled:
            trace_entry = "========== LLM CALL ==========\n"
            trace_entry += f"PROVIDER: {self.provider} | MODEL: {self.model} | JSON: {json_mode}\n\n"
            if self.openrouter_reasoning:
                trace_entry += f"--- REASONING CONFIG ---\n{self.openrouter_reasoning}\n\n"
            trace_entry += f"--- SYSTEM PROMPT ---\n{effective_system_prompt}\n\n"
            trace_entry += f"--- USER PROMPT ---\n{user_prompt}\n\n"

        max_retries = _openrouter_retry_limit()
        last_error = "LLM_ERROR: OpenRouter request did not complete"

        for attempt_idx in range(max_retries + 1):
            response = None
            try:
                semaphore = _get_openrouter_semaphore()
                semaphore.acquire()
                try:
                    response = requests.post(
                        self.url,
                        headers=headers,
                        json=payload,
                        timeout=timeout,
                    )
                finally:
                    semaphore.release()

                if response.status_code == 429:
                    _record_runtime_stat("openrouter_rate_limit_hits", 1)
                    detail = response.text[:200]
                    last_error = f"LLM_ERROR: 429 Client Error: Too Many Requests for url: {self.url}"
                    if detail:
                        last_error += f" :: {detail}"
                    detail_l = str(detail or "").lower()
                    if "free-models-per-day" in detail_l or "rate limit exceeded" in detail_l:
                        _mark_openrouter_temporarily_degraded(
                            reason="OpenRouter quota/rate-limit reached",
                            ttl_seconds=_openrouter_degraded_ttl_seconds(),
                        )
                    if _openrouter_failfast_on_429():
                        if trace_enabled:
                            _append_trace(trace_entry + f"--- ERROR ---\n{last_error}\n==============================\n\n")
                        return last_error
                    if attempt_idx >= max_retries:
                        if trace_enabled:
                            _append_trace(trace_entry + f"--- ERROR ---\n{last_error}\n==============================\n\n")
                        return last_error

                    retry_after = _extract_retry_after_seconds(response)
                    base_delay = min(
                        _openrouter_backoff_max_seconds(),
                        _openrouter_backoff_base_seconds() * (2 ** attempt_idx),
                    )
                    delay = retry_after if retry_after is not None else base_delay
                    delay = min(_openrouter_backoff_max_seconds(), float(delay))
                    delay += random.uniform(0.0, _openrouter_backoff_jitter_seconds())
                    _record_runtime_stat("openrouter_backoff_retries", 1)
                    _fallback_logger.warning(
                        "[RATE-LIMIT] Model '%s' hit 429. Backing off %.2fs before retry %d/%d.",
                        self.model,
                        delay,
                        attempt_idx + 1,
                        max_retries,
                    )
                    time.sleep(delay)
                    continue

                if response.status_code in {400, 401, 402, 403, 404}:
                    detail = response.text[:200]
                    last_error = f"LLM_ERROR: {response.status_code} Client Error for url: {self.url}"
                    if detail:
                        last_error += f" :: {detail}"
                    if response.status_code in {401, 402, 403}:
                        _mark_openrouter_temporarily_degraded(
                            reason=f"OpenRouter auth/billing error ({response.status_code})",
                            ttl_seconds=600,
                        )
                    if trace_enabled:
                        _append_trace(trace_entry + f"--- ERROR ---\n{last_error}\n==============================\n\n")
                    return last_error

                response.raise_for_status()
                data = response.json()
                result_text = _strip_reasoning_blocks(_extract_openrouter_text(data))
                finish_reason = str(((data.get("choices") or [{}])[0]).get("finish_reason", "") or "").strip().lower()
                usage = data.get("usage") or {}
                self._set_last_response_meta(
                    provider="openrouter",
                    model=self.model,
                    finish_reason=finish_reason or "stop",
                    prompt_tokens=_safe_nonnegative_int(usage.get("prompt_tokens", 0), 0),
                    completion_tokens=_safe_nonnegative_int(usage.get("completion_tokens", 0), 0),
                    total_tokens=_safe_nonnegative_int(usage.get("total_tokens", 0), 0),
                )

                if not str(result_text or "").strip():
                    _record_runtime_stat("openrouter_empty_responses", 1)
                    last_error = "LLM_ERROR: Empty response from OpenRouter"
                    if attempt_idx >= max_retries:
                        if trace_enabled:
                            _append_trace(trace_entry + f"--- ERROR ---\n{last_error}\n==============================\n\n")
                        return last_error

                    delay = min(
                        _openrouter_backoff_max_seconds(),
                        _openrouter_backoff_base_seconds() * (2 ** attempt_idx),
                    )
                    delay += random.uniform(0.0, _openrouter_backoff_jitter_seconds())
                    _record_runtime_stat("openrouter_backoff_retries", 1)
                    _fallback_logger.warning(
                        "[OPENROUTER-EMPTY] Model '%s' returned an empty response. "
                        "Backing off %.2fs before retry %d/%d.",
                        self.model,
                        delay,
                        attempt_idx + 1,
                        max_retries,
                    )
                    time.sleep(delay)
                    continue

                if finish_reason == "length" and json_mode and not str(result_text).strip().startswith("{"):
                    _record_runtime_stat("llm_over_verbose_responses", 1)
                    last_error = "LLM_ERROR: STRUCTURED_OUTPUT_TRUNCATED"
                    if attempt_idx >= max_retries:
                        if trace_enabled:
                            _append_trace(trace_entry + f"--- ERROR ---\n{last_error}\n==============================\n\n")
                        return last_error
                    delay = min(
                        _openrouter_backoff_max_seconds(),
                        _openrouter_backoff_base_seconds() * (2 ** attempt_idx),
                    )
                    delay += random.uniform(0.0, _openrouter_backoff_jitter_seconds())
                    _record_runtime_stat("openrouter_backoff_retries", 1)
                    time.sleep(delay)
                    continue

                if trace_enabled:
                    trace_entry += f"--- RESPONSE ---\n{result_text}\n"
                    if finish_reason:
                        trace_entry += f"--- FINISH REASON ---\n{finish_reason}\n"
                    trace_entry += "==============================\n\n"
                    _append_trace(trace_entry)

                return result_text
            except requests.Timeout as exc:
                last_error = f"LLM_ERROR: {exc}"
            except Exception as exc:
                last_error = f"LLM_ERROR: {exc}"
                err_l = str(exc).lower()
                if any(
                    token in err_l
                    for token in [
                        "nameresolutionerror",
                        "temporary failure in name resolution",
                        "failed to establish a new connection",
                        "max retries exceeded with url",
                        "dns",
                    ]
                ):
                    _mark_openrouter_temporarily_degraded(
                        reason="OpenRouter network/DNS instability",
                        ttl_seconds=300,
                    )
                    if _openrouter_failfast_on_network_error():
                        if trace_enabled:
                            _append_trace(trace_entry + f"--- ERROR ---\n{last_error}\n==============================\n\n")
                        return last_error

            if attempt_idx >= max_retries:
                if trace_enabled:
                    _append_trace(trace_entry + f"--- ERROR ---\n{last_error}\n==============================\n\n")
                return last_error

            delay = min(
                _openrouter_backoff_max_seconds(),
                _openrouter_backoff_base_seconds() * (2 ** attempt_idx),
            )
            delay += random.uniform(0.0, _openrouter_backoff_jitter_seconds())
            _record_runtime_stat("openrouter_backoff_retries", 1)
            _fallback_logger.warning(
                "[OPENROUTER-RETRY] Model '%s' failed with '%s'. Backing off %.2fs before retry %d/%d.",
                self.model,
                last_error[:160],
                delay,
                attempt_idx + 1,
                max_retries,
            )
            time.sleep(delay)

        if trace_enabled:
            _append_trace(trace_entry + f"--- ERROR ---\n{last_error}\n==============================\n\n")
        return last_error


class AsyncLLMClient:
    """
    Backward-compatible async interface used across Layer-4.
    """

    def __init__(self, model: str | None = None, provider: str | None = None):
        self.local = LocalLLM(model=model, provider=provider)
        self.is_available = True
        self.temperature_map = {
            "factual": 0.1,
            "strategic": 0.3,
            "creative": 0.6,
        }

    def _temperature_for_query(self, query_type: str | None) -> float:
        return float(self.temperature_map.get(str(query_type or "factual"), 0.2))

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        query_type: str | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
        task_type: str | None = None,
        context_pack: Any | None = None,
        allow_local_fallback: bool | None = None,
    ) -> str:
        temperature = self._temperature_for_query(query_type)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.local.generate(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
                task_type=task_type,
                context_pack=context_pack,
                allow_local_fallback=allow_local_fallback,
            ),
        )
        self.is_available = not str(response).startswith("LLM_ERROR:")
        return str(response)

    async def generate_with_tlm(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        n_samples: int = 3,
    ) -> Tuple[str, float]:
        samples = []
        for _ in range(max(1, int(n_samples))):
            text = await self.generate(prompt, system_prompt=system_prompt, query_type="factual")
            samples.append(text)

        unique = len(set(samples))
        confidence = 0.0 if not samples else 1.0 / max(1, unique)
        return str(samples[0] if samples else ""), float(confidence)

    async def stream(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        query_type: str | None = None,
        chunk_size: int = 256,
    ) -> AsyncIterator[str]:
        text = await self.generate(prompt, system_prompt=system_prompt, query_type=query_type)
        for idx in range(0, len(text), max(1, int(chunk_size))):
            yield text[idx : idx + chunk_size]

    def health(self) -> Dict[str, str]:
        _ensure_provider_bootstrap(self.local.model)
        with _provider_bootstrap_lock:
            chain = list(_provider_bootstrap_candidates or [])
            active = chain[_provider_active_index] if chain and 0 <= _provider_active_index < len(chain) else (
                self.local.provider,
                self.local.model,
            )
            reason = str(_provider_bootstrap_reason or "unknown")
        return {
            "provider": self.local.provider,
            "model": self.local.model,
            "url": self.local.url,
            "active_provider": str(active[0]),
            "active_model": str(active[1]),
            "routing_reason": reason,
            "status": "available" if self.is_available else "degraded",
        }


# Backward-compatible aliases.
ModelInterface = AsyncLLMClient
llm_client = AsyncLLMClient()


__all__ = [
    "LocalLLM",
    "AsyncLLMClient",
    "ModelInterface",
    "llm_client",
    "get_llm_runtime_stats",
    "LLM_PROVIDER",
    "OLLAMA_URL",
    "OPENROUTER_URL",
    "MODEL_NAME",
    "note_llm_deterministic_fallback",
    "reset_llm_runtime_stats",
]
