from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


@dataclass(frozen=True)
class CritiqueResult:
    issues_found: bool
    critical_issues: List[str] = field(default_factory=list)

    @property
    def should_retry(self) -> bool:
        return bool(self.issues_found and self.critical_issues)


def critique_minister_output(parsed: Dict[str, Any], report: Any, full_context: Any) -> CritiqueResult:
    issues: List[str] = []

    adjustment = str(parsed.get("risk_level_adjustment", "") or "").strip().lower()
    if adjustment not in {"increase", "decrease", "maintain"}:
        issues.append("risk_level_adjustment is invalid or missing")

    primary_drivers = [str(item).strip() for item in list(parsed.get("primary_drivers") or []) if str(item).strip()]
    if not primary_drivers:
        issues.append("primary_drivers is empty")

    counterarguments = [str(item).strip() for item in list(parsed.get("counterarguments") or []) if str(item).strip()]
    if not counterarguments:
        issues.append("counterarguments is empty")

    rationale = str(parsed.get("rationale", "") or "").strip()
    if not rationale:
        issues.append("rationale is missing")
    elif len(rationale.split()) > 160:
        issues.append("rationale is too long")

    justification_strength = _safe_float(parsed.get("justification_strength", 0.0), 0.0)
    if not (0.1 <= justification_strength <= 0.95):
        issues.append("justification_strength must be between 0.10 and 0.95")

    predicted_signals = list(getattr(report, "predicted_signals", []) or [])
    if predicted_signals and not primary_drivers:
        issues.append("predicted signals were present but not explained")

    if list(getattr(full_context, "gaps", []) or []) and not list(parsed.get("critical_gaps") or []):
        issues.append("critical_gaps omitted despite known context gaps")

    return CritiqueResult(issues_found=bool(issues), critical_issues=issues[:4])


def build_improvement_feedback(result: CritiqueResult) -> str:
    if not result.critical_issues:
        return ""
    lines = ["Previous output had issues:"]
    for item in list(result.critical_issues or [])[:4]:
        lines.append(f"- {item}")
    lines.append("Improve only these areas. Keep the JSON concise and complete.")
    return "\n".join(lines)


__all__ = [
    "CritiqueResult",
    "build_improvement_feedback",
    "critique_minister_output",
]
