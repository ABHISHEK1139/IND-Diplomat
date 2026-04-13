"""
ATOP Alliance Data Provider.
"""

import csv
from typing import Any, Dict, List, Optional
from statistics import mean

from engine.Layer3_StateModel.providers.base_provider import BaseProvider
from engine.Layer3_StateModel.providers.country_resolver import map_cow_to_iso3, resolve_country_to_iso3
from engine.Layer3_StateModel.providers.dataset_catalog import resolve_dataset_path

class ATOPProvider(BaseProvider):
    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        self._index: Dict[str, List[Dict[str, Any]]] = {}

    def load_index(self):
        if self._loaded:
            return

        self._reset_status()
        path = resolve_dataset_path("atop", self.data_dir)
        if path is None:
            self._set_error("ATOP dataset not found")
            self._warn("atop_missing")
            self._finalize_status(loaded=False)
            return
        self._set_dataset_path(path)
        rows_read = 0
        rows_kept = 0
        unresolved_pairs = 0

        with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows_read += 1
                year = self._safe_int(row.get("year"))
                state_a = self._safe_int(row.get("stateA"))
                state_b = self._safe_int(row.get("stateB"))
                if year is None or state_a is None or state_b is None:
                    continue

                iso_a = map_cow_to_iso3(state_a) or self.COW_TO_ISO.get(state_a)
                iso_b = map_cow_to_iso3(state_b) or self.COW_TO_ISO.get(state_b)
                if not iso_a or not iso_b:
                    unresolved_pairs += 1
                    continue

                atopally = (self._safe_int(row.get("atopally")) or 0) == 1
                defense = (self._safe_int(row.get("defense")) or 0) == 1
                offense = (self._safe_int(row.get("offense")) or 0) == 1
                neutral = (self._safe_int(row.get("neutral")) or 0) == 1
                nonagg = (self._safe_int(row.get("nonagg")) or 0) == 1
                consul = (self._safe_int(row.get("consul")) or 0) == 1
                shareob = (self._safe_int(row.get("shareob")) or 0) == 1

                strength = max(0.0, min(1.0, 
                    (0.35 if defense else 0.0)
                    + (0.25 if offense else 0.0)
                    + (0.15 if nonagg else 0.0)
                    + (0.10 if consul else 0.0)
                    + (0.10 if shareob else 0.0)
                    + (0.05 if neutral else 0.0)
                ))
                military_commitment = max(0.0, min(1.0, (0.6 if offense else 0.0) + (0.4 if defense else 0.0)))

                rec_a = {
                    "year": year,
                    "partner": iso_b,
                    "atopally": atopally,
                    "strength": strength,
                    "military_commitment": military_commitment,
                }
                rec_b = {
                    "year": year,
                    "partner": iso_a,
                    "atopally": atopally,
                    "strength": strength,
                    "military_commitment": military_commitment,
                }
                self._index.setdefault(iso_a, []).append(rec_a)
                self._index.setdefault(iso_b, []).append(rec_b)
                rows_kept += 1
        
        if unresolved_pairs:
            self._warn(f"atop_unresolved_cow_pairs={unresolved_pairs}")
        self._set_status_counts(
            rows_read=rows_read,
            rows_kept=rows_kept,
            coverage_count=len(self._index),
        )
        self._status["unresolved_cow_pairs"] = int(unresolved_pairs)
        self._finalize_status(loaded=len(self._index) > 0)

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        key = resolve_country_to_iso3(country_code) or country_code.upper()
        records = self._index.get(key, [])
        if not records:
            return None

        target_year = self._target_year(date)
        in_scope = [r for r in records if r["year"] <= target_year]
        if not in_scope:
            return None

        current_year = max(r["year"] for r in in_scope)
        current = [r for r in in_scope if r["year"] == current_year]
        active = [r for r in current if r["atopally"]]

        partner_count = len({r["partner"] for r in active if r.get("partner")})
        mean_strength = mean([r["strength"] for r in active]) if active else 0.0
        military_commitment = mean([r["military_commitment"] for r in active]) if active else 0.0
        # Logic from Builder: _clamp((mean_strength * 0.7) + (min(1.0, partner_count / 12.0) * 0.3))
        support_index = max(0.0, min(1.0, (mean_strength * 0.7) + (min(1.0, partner_count / 12.0) * 0.3)))

        return {
            "active_alliance_count": len(active),
            "partner_count": partner_count,
            "alliance_support_index": round(support_index, 4),
            "military_commitment_index": round(military_commitment, 4),
            "year": current_year,
            "date": f"{current_year}-12-31",
        }

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            return int(float(str(value)))
        except Exception:
            return None
