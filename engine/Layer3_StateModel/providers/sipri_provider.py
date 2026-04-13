"""
SIPRI Arms Transfer Data Provider.
"""

import csv
import math
from typing import Any, Dict, List, Optional, Tuple
from statistics import mean

from engine.Layer3_StateModel.providers.base_provider import BaseProvider
from engine.Layer3_StateModel.providers.country_resolver import resolve_country_to_iso3
from engine.Layer3_StateModel.providers.dataset_catalog import resolve_dataset_path

class SIPRIProvider(BaseProvider):
    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        self._import_index: Dict[str, Dict[str, Any]] = {}
        self._export_index: Dict[str, Dict[str, Any]] = {}

    def load_index(self):
        if self._loaded:
            return

        self._reset_status()
        import_path = resolve_dataset_path("sipri_import", self.data_dir)
        export_path = resolve_dataset_path("sipri_export", self.data_dir)

        if import_path is None:
            self._warn("sipri_import_not_found")
        if export_path is None:
            self._warn("sipri_export_not_found")
        if import_path is None and export_path is None:
            self._set_error("SIPRI dataset files not found")
            self._finalize_status(loaded=False)
            return

        rows_read_total = 0
        rows_kept_total = 0
        unresolved_total = 0

        if import_path is not None:
            self._set_dataset_path(import_path.parent)
            rows_read, rows_kept, unresolved = self._load_sipri_file(import_path, self._import_index)
            rows_read_total += rows_read
            rows_kept_total += rows_kept
            unresolved_total += unresolved
        if export_path is not None:
            if not self._status.get("dataset_path"):
                self._set_dataset_path(export_path.parent)
            rows_read, rows_kept, unresolved = self._load_sipri_file(export_path, self._export_index)
            rows_read_total += rows_read
            rows_kept_total += rows_kept
            unresolved_total += unresolved

        if unresolved_total:
            self._warn(f"unresolved_country_rows={unresolved_total}")

        combined_coverage = len(set(self._import_index.keys()) | set(self._export_index.keys()))
        self._set_status_counts(
            rows_read=rows_read_total,
            rows_kept=rows_kept_total,
            coverage_count=combined_coverage,
        )
        self._finalize_status(loaded=combined_coverage > 0)

    def _load_sipri_file(self, path, index: Dict[str, Any]) -> Tuple[int, int, int]:
        rows_read = 0
        rows_kept = 0
        unresolved = 0
        year_cols: Dict[int, int] = {}
        header_found = False

        with open(path, "r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
            reader = csv.reader(handle)
            for row in reader:
                rows_read += 1
                clean = [str(cell or "").strip() for cell in row]
                if not clean:
                    continue

                if not header_found:
                    lower = {cell.lower() for cell in clean if cell}
                    if (
                        "recipient" in lower
                        or "supplier" in lower
                        or "exports by" in lower
                        or "imports by" in lower
                    ):
                        header_found = True
                        for idx, col in enumerate(clean):
                            token = str(col).strip()
                            if token.isdigit():
                                year = int(token)
                                if 1900 <= year <= 2100:
                                    year_cols[year] = idx
                        if not year_cols:
                            self._warn(f"no_year_columns:{path.name}")
                        continue
                    continue

                country_raw = clean[0] if clean else ""
                iso3 = resolve_country_to_iso3(country_raw)
                if not iso3:
                    unresolved += 1
                    continue

                series: List[Tuple[int, float]] = []
                for year, idx in year_cols.items():
                    if idx >= len(clean):
                        continue
                    val = self._safe_float(clean[idx])
                    if val is not None:
                        series.append((year, val))
                if not series:
                    continue
                series.sort(key=lambda point: point[0])
                index[iso3] = {"series": series}
                rows_kept += 1

        if not header_found:
            self._warn(f"sipri_header_not_found:{path.name}")
        return rows_read, rows_kept, unresolved

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        target_year = self._target_year(date)
        key = resolve_country_to_iso3(country_code) or country_code.upper()

        import_record = self._import_index.get(key)
        export_record = self._export_index.get(key)

        if not import_record and not export_record:
            return None

        imp_latest = self._latest_series_point(import_record.get("series", []), target_year) if import_record else None
        exp_latest = self._latest_series_point(export_record.get("series", []), target_year) if export_record else None

        if not imp_latest and not exp_latest:
            return None

        imp_recent = (
            self._window_average(import_record.get("series", []), target_year - 4, target_year)
            if import_record
            else None
        )
        exp_recent = (
            self._window_average(export_record.get("series", []), target_year - 4, target_year)
            if export_record
            else None
        )
        
        # Fill None with latest specific value if window avg failed but point exists
        if imp_recent is None and imp_latest:
            imp_recent = imp_latest[1]
        if exp_recent is None and exp_latest:
            exp_recent = exp_latest[1]

        import_component = imp_recent or 0.0
        export_component = exp_recent or 0.0
        combined_recent = (import_component * 0.65) + (export_component * 0.35)
        # Logarithmic scaling
        combined_index = max(0.0, min(1.0, math.log1p(combined_recent) / math.log1p(4500.0)))

        latest_year = max(
            y
            for y in (
                imp_latest[0] if imp_latest else None,
                exp_latest[0] if exp_latest else None,
            )
            if y is not None
        )
        
        return {
            "import_tiv": imp_latest[1] if imp_latest else None,
            "export_tiv": exp_latest[1] if exp_latest else None,
            "import_recent_avg": imp_recent,
            "export_recent_avg": exp_recent,
            "combined_recent_tiv": combined_recent,
            "combined_index": round(combined_index, 4),
            "date": f"{latest_year}-12-31",
        }

    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        text = text.replace(",", "")
        try:
            return float(text)
        except Exception:
            return None

    def _latest_series_point(self, series: List[Tuple[int, float]], target_year: int) -> Optional[Tuple[int, float]]:
        valid = [p for p in series if p[0] <= target_year]
        return valid[-1] if valid else None

    def _window_average(self, series: List[Tuple[int, float]], start_year: int, end_year: int) -> Optional[float]:
        points = [p[1] for p in series if start_year <= p[0] <= end_year]
        return mean(points) if points else None
