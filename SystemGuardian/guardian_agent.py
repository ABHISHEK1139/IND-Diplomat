"""Main controller for Layer-0 environment diagnostics and repair."""

from __future__ import annotations

from typing import Any, Dict, List

from SystemGuardian.health_check import full_health_report
from SystemGuardian.repair_actions import (
    fix_ddgs,
    install_python_package,
    instructions_for_tesseract,
)


def run_guardian(*, apply_repairs: bool = False) -> Dict[str, Any]:
    health_before = full_health_report()
    fixes: List[str] = []
    pending_repairs: List[str] = []

    if apply_repairs:
        # Repair missing Python packages using allowlisted actions only.
        for pkg, ok in health_before["python_packages"].items():
            if ok:
                continue
            if pkg == "ddgs":
                fixes.append(fix_ddgs())
            else:
                fixes.append(install_python_package(pkg))
    else:
        for pkg, ok in health_before["python_packages"].items():
            if not ok:
                pending_repairs.append(f"python_package_missing:{pkg}")

    health_after = full_health_report() if apply_repairs else health_before

    # OS-level tools are never auto-installed by the agent.
    if not health_after["binaries"].get("tesseract", False):
        if apply_repairs:
            fixes.append(instructions_for_tesseract())
        else:
            pending_repairs.append("binary_missing:tesseract")

    return {
        "mode": "repair" if apply_repairs else "report_only",
        "health_before": health_before,
        "health_after": health_after,
        "fixes": fixes,
        "pending_repairs": pending_repairs,
    }
