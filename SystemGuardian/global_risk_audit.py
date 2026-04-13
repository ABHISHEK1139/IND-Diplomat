"""
Global risk dataset and provider audit CLI.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Config.paths import PROJECT_ROOT
from engine.Layer3_StateModel.construction.country_state_builder import CountryStateBuilder
from engine.Layer3_StateModel.providers.provider_health import summarize_provider_health
from SystemGuardian.health_check import check_global_risk_data


def _recommendation(status: Dict[str, Any]) -> str:
    if status.get("status") == "no_snapshot_data":
        return "Add local Comtrade snapshot JSON files to enable this provider."
    if status.get("status") == "skipped_invalid_dataset":
        return "Replace dataset with expected schema or keep skipped."
    if status.get("error"):
        return "Inspect schema/path and parsing logic."
    if not status.get("loaded", False):
        return "Provider not loaded; verify dataset path and schema."
    if int(status.get("coverage_count", 0) or 0) <= 0:
        return "Loaded but no country coverage; inspect resolver mappings."
    return "OK"


def _render_text_report(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("GLOBAL RISK DATA AUDIT")
    lines.append(f"Generated: {payload['generated_at']}")
    lines.append("")

    dataset_root = payload.get("dataset_probe", {}).get("root_path", "")
    lines.append(f"Dataset root: {dataset_root}")
    lines.append("")
    lines.append("Provider Status")
    lines.append("----------------")
    providers = payload.get("providers", {})
    for name in sorted(providers.keys()):
        status = providers[name]
        lines.append(
            f"{name}: loaded={status.get('loaded')} "
            f"coverage={status.get('coverage_count', 0)} "
            f"rows={status.get('rows_kept', 0)}/{status.get('rows_read', 0)} "
            f"status={status.get('status', '')}"
        )
        if status.get("dataset_path"):
            lines.append(f"  dataset: {status['dataset_path']}")
        if status.get("warnings"):
            lines.append(f"  warnings: {', '.join(status['warnings'])}")
        if status.get("error"):
            lines.append(f"  error: {status['error']}")
        lines.append(f"  recommendation: {_recommendation(status)}")
    lines.append("")

    summary = payload.get("summary", {})
    lines.append("Summary")
    lines.append("-------")
    lines.append(
        "providers={provider_count} loaded={loaded_count} failed={failed_count} "
        "skipped={skipped_count} warnings={warning_count} coverage_total={coverage_total}".format(
            **summary
        )
    )
    return "\n".join(lines) + "\n"


def run_audit(output_dir: Path | None = None) -> Dict[str, Any]:
    builder = CountryStateBuilder()
    provider_health = builder.get_provider_health(refresh=True)
    dataset_probe = check_global_risk_data(include_provider_load=False)
    summary = summarize_provider_health(provider_health)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_probe": dataset_probe,
        "providers": provider_health,
        "summary": summary,
    }

    reports_dir = output_dir or (PROJECT_ROOT / "reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = reports_dir / f"global_risk_audit_{stamp}.json"
    txt_path = reports_dir / f"global_risk_audit_{stamp}.txt"
    latest_json = reports_dir / "global_risk_audit_latest.json"
    latest_txt = reports_dir / "global_risk_audit_latest.txt"

    json_blob = json.dumps(payload, indent=2, ensure_ascii=False)
    txt_blob = _render_text_report(payload)
    json_path.write_text(json_blob, encoding="utf-8")
    txt_path.write_text(txt_blob, encoding="utf-8")
    latest_json.write_text(json_blob, encoding="utf-8")
    latest_txt.write_text(txt_blob, encoding="utf-8")

    payload["report_paths"] = {
        "json": str(json_path),
        "txt": str(txt_path),
        "latest_json": str(latest_json),
        "latest_txt": str(latest_txt),
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Global risk provider audit report")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "reports"),
        help="Directory where audit reports are written.",
    )
    args = parser.parse_args()
    report = run_audit(output_dir=Path(args.output_dir))
    print(json.dumps(report.get("report_paths", {}), indent=2))


if __name__ == "__main__":
    main()
