"""
Global Sanctions Data Provider.
"""

import csv
from typing import Any, Dict, List, Optional
from statistics import mean

from engine.Layer3_StateModel.providers.base_provider import BaseProvider
from engine.Layer3_StateModel.providers.country_resolver import resolve_country_to_iso3
from engine.Layer3_StateModel.providers.dataset_catalog import resolve_dataset_path

class SanctionsProvider(BaseProvider):
    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        self._index: Dict[str, List[Dict[str, Any]]] = {}

    def load_index(self):
        if self._loaded:
            return

        self._reset_status()
        path = resolve_dataset_path("sanctions_gsdb", self.data_dir)
        if path is None:
            self._set_error("GSDB dataset not found")
            self._warn("gsdb_missing")
            self._finalize_status(loaded=False)
            return
        self._set_dataset_path(path)

        rows_read = 0
        rows_kept = 0
        unresolved = 0
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows_read += 1
                target_iso = resolve_country_to_iso3(row.get("sanctioned_state") or row.get("target_state"))
                sender_iso = resolve_country_to_iso3(row.get("sanctioning_state") or row.get("sender_state"))
                if not target_iso:
                    unresolved += 1
                    continue

                begin = self._safe_int(row.get("begin"))
                end = self._safe_int(row.get("end"))
                severity = self._severity_from_dimensions(row)
                sender = sender_iso or str(row.get("sanctioning_state") or row.get("sender_state") or "Unknown")
                record = {
                    "begin": begin,
                    "end": end,
                    "severity": severity,
                    "sender": sender,
                    "raw": row,
                }
                self._index.setdefault(target_iso, []).append(record)
                rows_kept += 1

        if unresolved:
            self._warn(f"unresolved_sanction_targets={unresolved}")
        self._set_status_counts(
            rows_read=rows_read,
            rows_kept=rows_kept,
            coverage_count=len(self._index),
        )
        self._finalize_status(loaded=len(self._index) > 0)
    
    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        country = resolve_country_to_iso3(country_code) or country_code.upper()
        records = self._index.get(country, [])
        if not records:
            return None
            
        target_year = self._target_year(date)
        active = []
        for record in records:
            begin = record.get("begin")
            end = record.get("end")
            if begin is not None and begin > target_year:
                continue
            if end is not None and end < target_year:
                continue
            active.append(record)

        active_count = len(active)
        avg_severity = mean([r["severity"] for r in active]) if active else 0.0
        sender_count = len({r.get("sender") for r in active if r.get("sender")})

        pressure_index = max(0.0, min(1.0, min(1.0, active_count / 8.0) * 0.6 + avg_severity * 0.4))
        
        all_years = [
            y
            for r in records
            for y in (r.get("begin"), r.get("end"))
            if isinstance(y, int)
        ]
        latest_year = max(all_years) if all_years else target_year

        return {
            "active_count": active_count,
            "historical_count": len(records),
            "avg_severity": round(avg_severity, 4),
            "sender_count": sender_count,
            "pressure_index": round(pressure_index, 4),
            "date": f"{latest_year}-12-31",
        }

    def _severity_from_dimensions(self, row: Dict[str, Any]) -> float:
        components = {
            "trade": 1.00,
            "arms": 1.10,
            "military": 1.20,
            "financial": 1.00,
            "travel": 0.60,
            "other": 0.40,
        }
        score = 0.0
        max_score = sum(components.values())
        for field, weight in components.items():
            raw = self._safe_float(row.get(field))
            active = 1.0 if (raw is not None and raw > 0.0) else 0.0
            score += active * weight
        normalized = score / max(max_score, 1e-9)
        return self._clamp(normalized)

    def _safe_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(float(str(value)))
        except Exception:
            return None

    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(str(value).strip())
        except Exception:
            return None
