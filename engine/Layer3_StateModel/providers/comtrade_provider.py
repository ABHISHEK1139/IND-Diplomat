"""
UN Comtrade Data Provider.
"""

import json
import os
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.providers.base_provider import BaseProvider
from engine.Layer3_StateModel.providers.country_resolver import resolve_country_to_iso3
from engine.Layer3_StateModel.providers.dataset_catalog import resolve_dataset_paths

class ComtradeProvider(BaseProvider):
    # Dirs for snapshots
    SNAPSHOT_DIRS = ["comtrade_snapshots", "data/comtrade"]

    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        self._index: Dict[str, List[Dict[str, Any]]] = {}

    def load_index(self):
        if self._loaded:
            return

        self._reset_status()
        found_dirs = []
        for path in resolve_dataset_paths("comtrade_snapshots", self.data_dir):
            if path.is_dir():
                found_dirs.append(str(path))
        for d in self.SNAPSHOT_DIRS:
            p = os.path.join(self.data_dir, d)
            if os.path.isdir(p) and p not in found_dirs:
                found_dirs.append(p)

        rows_read = 0
        rows_kept = 0
        self._set_dataset_path(found_dirs[0] if found_dirs else "")

        if not found_dirs:
            self._status["status"] = "no_snapshot_data"
            self._warn("comtrade_snapshot_dirs_missing")
            self._set_status_counts(rows_read=0, rows_kept=0, coverage_count=0)
            self._finalize_status(loaded=False)
            return

        for snapshot_dir in found_dirs:
            try:
                for filename in os.listdir(snapshot_dir):
                    if not filename.lower().endswith(".json"):
                        continue
                    path = os.path.join(snapshot_dir, filename)
                    rows_read += 1
                    try:
                        with open(path, "r", encoding="utf-8") as handle:
                            payload = json.load(handle)
                    except Exception:
                        continue
                    if not isinstance(payload, dict):
                        continue

                    reporter = str(payload.get("reporter", "") or "").strip().upper()
                    reporter_iso = resolve_country_to_iso3(reporter) or reporter
                    if not reporter_iso:
                        continue
                    
                    year = self._safe_int(payload.get("year"))
                    if year is None:
                        timestamp = str(payload.get("timestamp", "") or "")
                        if len(timestamp) >= 4 and timestamp[:4].isdigit():
                            year = int(timestamp[:4])
                    if year is None:
                        continue

                    leverage = self._safe_float(payload.get("leverage_score"))
                    if leverage is None:
                        leverage = self._safe_float(payload.get("leverage_index"))
                    leverage = float(leverage or 0.0)

                    deps = payload.get("critical_dependencies")
                    if not isinstance(deps, list):
                        deps = payload.get("dependencies") if isinstance(payload.get("dependencies"), list) else []

                    self._index.setdefault(reporter_iso, []).append({
                        "year": year,
                        "partner": resolve_country_to_iso3(payload.get("partner")) or str(payload.get("partner", "") or "").strip().upper(),
                        "leverage_index": leverage,
                        "critical_dependency_count": len(deps),
                        "trade_balance": float(self._safe_float(payload.get("trade_balance")) or 0.0),
                        "timestamp": str(payload.get("timestamp", "") or ""),
                        "proxy": False
                    })
                    rows_kept += 1
            except Exception:
                continue

        for reporter in self._index:
            self._index[reporter].sort(key=lambda row: (row["year"], row.get("timestamp", "")))
        self._set_status_counts(
            rows_read=rows_read,
            rows_kept=rows_kept,
            coverage_count=len(self._index),
        )
        if self._index:
            self._status["status"] = "loaded"
            self._finalize_status(loaded=True)
        else:
            self._status["status"] = "no_snapshot_data"
            self._warn("comtrade_no_json_records")
            self._finalize_status(loaded=False)

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        iso3 = resolve_country_to_iso3(country_code) or country_code.upper()
        records = [r for r in self._index.get(iso3, []) if r["year"] <= self._target_year(date)]
        if not records:
            return None

        latest = max(records, key=lambda r: (r["year"], r.get("timestamp", "")))
        leverage = self._clamp(float(latest.get("leverage_index", 0.0)))
        
        result = {
            "leverage_index": round(leverage, 4),
            "critical_dependency_count": int(latest.get("critical_dependency_count", 0)),
            "trade_balance": float(latest.get("trade_balance", 0.0)),
            "partner": latest.get("partner", ""),
            "proxy": False,
            "date": f"{latest['year']}-12-31",
        }
        return result

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            return float(value)
        except Exception:
            return None
        
    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            return int(float(str(value)))
        except Exception:
            return None
