"""
Provider health telemetry helpers.
"""

from __future__ import annotations

from typing import Any, Dict


STANDARD_STATUS_KEYS = (
    "loaded",
    "dataset_path",
    "rows_read",
    "rows_kept",
    "coverage_count",
    "warnings",
    "error",
)


def _to_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return 0


def _normalize_status(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict(payload or {})
    normalized = {
        "loaded": bool(raw.get("loaded", False)),
        "dataset_path": str(raw.get("dataset_path", "") or ""),
        "rows_read": _to_int(raw.get("rows_read", 0)),
        "rows_kept": _to_int(raw.get("rows_kept", 0)),
        "coverage_count": _to_int(raw.get("coverage_count", 0)),
        "warnings": list(raw.get("warnings", []) or []),
        "error": raw.get("error"),
    }
    for key, value in raw.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


def collect_provider_health(providers: Dict[str, Any], *, force_load: bool = True) -> Dict[str, Dict[str, Any]]:
    """
    Collect standardized health for provider instances.
    """
    report: Dict[str, Dict[str, Any]] = {}
    for name, provider in providers.items():
        status: Dict[str, Any] = {}
        try:
            if force_load and hasattr(provider, "load_index"):
                provider.load_index()
        except Exception as exc:
            status = {"loaded": False, "error": str(exc), "warnings": []}

        if hasattr(provider, "get_status"):
            try:
                status = provider.get_status()
            except Exception as exc:
                status = {"loaded": False, "error": str(exc), "warnings": []}
        elif not status:
            index_obj = getattr(provider, "_index", None)
            coverage = len(index_obj) if hasattr(index_obj, "__len__") else 0
            status = {
                "loaded": bool(getattr(provider, "_loaded", False)),
                "dataset_path": "",
                "rows_read": 0,
                "rows_kept": 0,
                "coverage_count": int(coverage),
                "warnings": [],
                "error": None,
            }
        report[name] = _normalize_status(status)
    return report


def summarize_provider_health(report: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    total = len(report)
    loaded = 0
    failed = 0
    skipped = 0
    warnings = 0
    coverage_total = 0
    for status in report.values():
        if status.get("loaded"):
            loaded += 1
        if status.get("error"):
            failed += 1
        if status.get("status") in {"skipped_invalid_dataset", "no_snapshot_data"}:
            skipped += 1
        warnings += len(status.get("warnings", []) or [])
        coverage_total += _to_int(status.get("coverage_count", 0))
    return {
        "provider_count": total,
        "loaded_count": loaded,
        "failed_count": failed,
        "skipped_count": skipped,
        "warning_count": warnings,
        "coverage_total": coverage_total,
    }

