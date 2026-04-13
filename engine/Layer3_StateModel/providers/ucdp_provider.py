"""
UCDP Conflict Data Provider.
"""

import csv
import math
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.providers.base_provider import BaseProvider
from engine.Layer3_StateModel.providers.country_resolver import map_cow_to_iso3, resolve_country_to_iso3
from engine.Layer3_StateModel.providers.dataset_catalog import resolve_dataset_path

class UCDPProvider(BaseProvider):
    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        self._index: Dict[str, Dict[int, Dict[str, float]]] = {}
    
    def load_index(self):
        if self._loaded:
            return
        
        self._reset_status()
        path = resolve_dataset_path("ucdp_ged", self.data_dir)
        if path is None:
            self._set_error("UCDP GED dataset not found")
            self._warn("ucdp_missing")
            self._finalize_status(loaded=False)
            return
        self._set_dataset_path(path)
        rows_read = 0
        rows_kept = 0
        unresolved = 0
        
        try:
            with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows_read += 1
                    year = self._safe_int(row.get("year"))
                    if year is None:
                        continue
                    
                    location = (row.get("country") or row.get("side_a") or row.get("side_b") or "").strip()
                    country_key = resolve_country_to_iso3(location)
                    if not country_key:
                        country_key = map_cow_to_iso3(row.get("country_id")) or map_cow_to_iso3(row.get("gwnoa"))
                    if not country_key:
                        unresolved += 1
                        continue
                    
                    fatalities = self._safe_float(row.get("best"))
                    if fatalities is None:
                        fatalities = self._safe_float(row.get("deaths_best"))
                    fatalities = float(fatalities or 0.0)
                    
                    try:
                        violence_type = int(float(row.get("type_of_violence") or 0))
                    except:
                        violence_type = 0
                        
                    if country_key not in self._index:
                        self._index[country_key] = {}
                    
                    year_bucket = self._index[country_key].setdefault(
                        year,
                        {"fatalities": 0.0, "event_count": 0.0, "state_based_count": 0.0},
                    )
                    year_bucket["fatalities"] += fatalities
                    year_bucket["event_count"] += 1.0
                    if violence_type == 1:
                        year_bucket["state_based_count"] += 1.0
                    rows_kept += 1
                        
            if unresolved:
                self._warn(f"ucdp_unresolved_rows={unresolved}")
            self._set_status_counts(
                rows_read=rows_read,
                rows_kept=rows_kept,
                coverage_count=len(self._index),
            )
            self._finalize_status(loaded=len(self._index) > 0)
        except Exception as exc:
            self._index = {}
            self._set_error(exc)
            self._set_status_counts(rows_read=rows_read, rows_kept=rows_kept, coverage_count=0)
            self._finalize_status(loaded=False)

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        iso3 = resolve_country_to_iso3(country_code) or country_code.upper()
        by_year = self._index.get(iso3)
        if not by_year:
            return None
        
        target_year = self._target_year(date)
        valid_years = [year for year in by_year if year <= target_year]
        if not valid_years:
            return None
        
        latest_year = max(valid_years)
        recent_years = [year for year in valid_years if year >= (target_year - 2)]
        
        fatalities_3y = sum(by_year[year]["fatalities"] for year in recent_years)
        events_3y = sum(by_year[year]["event_count"] for year in recent_years)
        state_based_3y = sum(by_year[year]["state_based_count"] for year in recent_years)
        
        conflict_index = max(0.0, min(1.0, math.log1p(fatalities_3y) / math.log1p(20000.0)))
        event_index = max(0.0, min(1.0, events_3y / 150.0))
        state_based_share = max(0.0, min(1.0, state_based_3y / max(events_3y, 1.0)))
        
        previous_years = [year for year in valid_years if year < latest_year]
        prev_fatalities = by_year[max(previous_years)]["fatalities"] if previous_years else 0.0
        trend_delta = by_year[latest_year]["fatalities"] - prev_fatalities
        
        return {
            "event_count_3y": int(events_3y),
            "fatalities_3y": round(float(fatalities_3y), 2),
            "state_based_share": round(state_based_share, 4),
            "conflict_index": round((conflict_index * 0.75) + (event_index * 0.25), 4),
            "trend_delta": round(float(trend_delta), 2),
            "year": latest_year,
            "date": f"{latest_year}-12-31",
        }

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
