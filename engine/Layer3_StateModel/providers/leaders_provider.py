"""
Archigos Leaders Data Provider.
"""

import csv
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.providers.base_provider import BaseProvider
from engine.Layer3_StateModel.providers.country_resolver import map_cow_to_iso3, resolve_country_to_iso3
from engine.Layer3_StateModel.providers.dataset_catalog import resolve_dataset_path

class LeadersProvider(BaseProvider):
    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        self._index: Dict[str, List[int]] = {}

    def load_index(self):
        if self._loaded:
            return

        self._reset_status()
        path = resolve_dataset_path("leaders_archigos", self.data_dir)
        if path is None:
            self._set_error("Leaders dataset not found")
            self._warn("leaders_missing")
            self._status["status"] = "skipped_invalid_dataset"
            self._finalize_status(loaded=False)
            return
        self._set_dataset_path(path)

        try:
            with open(path, "rb") as probe:
                prefix = probe.read(256)
            if b"<stata_dta>" in prefix.lower():
                self._status["status"] = "skipped_invalid_dataset"
                self._warn("leaders_dataset_is_stata_not_archigos")
                self._set_status_counts(rows_read=0, rows_kept=0, coverage_count=0)
                self._finalize_status(loaded=False)
                return

            rows_read = 0
            rows_kept = 0
            with open(path, "r", encoding="utf-8", errors="ignore", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    self._status["status"] = "skipped_invalid_dataset"
                    self._warn("leaders_header_missing")
                    self._set_status_counts(rows_read=0, rows_kept=0, coverage_count=0)
                    self._finalize_status(loaded=False)
                    return

                country_fields = ["country", "country_name", "country_text_id", "iso3", "state", "ccode"]
                year_fields = ["startyear", "entry_year", "entry", "start", "year", "yrbeg"]
                fieldnames = {str(name or "").strip().lower() for name in reader.fieldnames}
                if not (fieldnames & set(country_fields)) or not (fieldnames & set(year_fields)):
                    self._status["status"] = "skipped_invalid_dataset"
                    self._warn("leaders_schema_mismatch")
                    self._set_status_counts(rows_read=0, rows_kept=0, coverage_count=0)
                    self._finalize_status(loaded=False)
                    return

                for row in reader:
                    rows_read += 1
                    country_value = ""
                    for key in country_fields:
                        if key in row and row[key]:
                            country_value = row[key]
                            break
                    if not country_value: continue

                    iso = None
                    ccode = self._safe_int(country_value)
                    if ccode is not None:
                        iso = map_cow_to_iso3(ccode) or self.COW_TO_ISO.get(ccode)
                    if not iso:
                        iso = resolve_country_to_iso3(country_value)
                    if not iso:
                        continue

                    year = None
                    for key in year_fields:
                        if key in row and row[key]:
                            year = self._safe_int(row[key])
                            if year is not None: break
                    if year is None:
                        continue

                    self._index.setdefault(iso, []).append(year)
                    rows_kept += 1

            for iso in list(self._index.keys()):
                self._index[iso] = sorted(set(self._index[iso]))
            self._set_status_counts(
                rows_read=rows_read,
                rows_kept=rows_kept,
                coverage_count=len(self._index),
            )
            self._status["status"] = "loaded" if self._index else "skipped_invalid_dataset"
            self._finalize_status(loaded=len(self._index) > 0)
        except Exception as exc:
            self._index = {}
            self._status["status"] = "skipped_invalid_dataset"
            self._set_error(exc)
            self._set_status_counts(rows_read=0, rows_kept=0, coverage_count=0)
            self._finalize_status(loaded=False)

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        iso3 = resolve_country_to_iso3(country_code) or country_code.upper()
        changes = self._index.get(iso3)
        if not changes:
            return None

        target_year = self._target_year(date)
        decade_changes = len([year for year in changes if (target_year - 9) <= year <= target_year])
        recent_changes = len([year for year in changes if (target_year - 2) <= year <= target_year])
        
        # Builder logic: _clamp((recent_changes / 4.0) * 0.7 + (decade_changes / 10.0) * 0.3)
        volatility = self._clamp((recent_changes / 4.0) * 0.7 + (decade_changes / 10.0) * 0.3)
        latest_year = max(changes) if changes else target_year
        
        return {
            "recent_changes_3y": recent_changes,
            "changes_10y": decade_changes,
            "volatility_index": round(volatility, 4),
            "date": f"{latest_year}-12-31",
        }

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            return int(float(str(value)))
        except Exception:
            return None
