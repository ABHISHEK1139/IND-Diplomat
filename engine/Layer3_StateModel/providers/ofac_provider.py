"""
OFAC Sanctions Data Provider.
"""

import csv
import math
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.providers.base_provider import BaseProvider
from engine.Layer3_StateModel.providers.country_resolver import (
    resolve_country_to_iso3,
    resolve_iso3_candidates_from_text,
)
from engine.Layer3_StateModel.providers.dataset_catalog import resolve_dataset_path

class OFACProvider(BaseProvider):
    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        self._index: Dict[str, Dict[str, Any]] = {}

    def load_index(self):
        if self._loaded:
            return

        self._reset_status()
        path = resolve_dataset_path("ofac_sdn", self.data_dir)
        if path is None:
            self._set_error("OFAC dataset not found")
            self._warn("ofac_missing")
            self._finalize_status(loaded=False)
            return
        self._set_dataset_path(path)

        rows_read = 0
        rows_kept = 0
        unresolved = 0
        tmp: Dict[str, Dict[str, Any]] = {}
        try:
            with open(path, "r", encoding="utf-8", errors="ignore", newline="") as handle:
                reader = csv.reader(handle)
                header: Optional[List[str]] = None
                for row in reader:
                    rows_read += 1
                    if not row:
                        continue
                    if header is None and self._looks_like_header(row):
                        header = [str(col or "").strip().lower() for col in row]
                        continue

                    countries = self._extract_countries(row, header=header)
                    if not countries:
                        unresolved += 1
                        continue

                    row_map = self._row_to_map(row, header)
                    entity_type = str(
                        row_map.get("sdn_type")
                        or row_map.get("type")
                        or row_map.get("entry_type")
                        or (row[2] if len(row) > 2 else "")
                    ).strip().lower()
                    program = str(
                        row_map.get("program")
                        or row_map.get("programs")
                        or row_map.get("sanction_program")
                        or (row[3] if len(row) > 3 else "")
                    ).strip()
                    for iso in countries:
                        bucket = tmp.setdefault(
                            iso,
                            {"count": 0, "vessel_count": 0, "aircraft_count": 0, "programs": set()},
                        )
                        bucket["count"] += 1
                        if "vessel" in entity_type:
                            bucket["vessel_count"] += 1
                        if "aircraft" in entity_type:
                            bucket["aircraft_count"] += 1
                        if program and program != "-0-":
                            bucket["programs"].add(program)
                    rows_kept += 1

            for iso, bucket in tmp.items():
                self._index[iso] = {
                    "count": int(bucket["count"]),
                    "vessel_count": int(bucket["vessel_count"]),
                    "aircraft_count": int(bucket["aircraft_count"]),
                    "program_count": len(bucket["programs"]),
                }
            if unresolved:
                self._warn(f"unresolved_ofac_rows={unresolved}")
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
        key = resolve_country_to_iso3(country_code) or country_code.upper()
        record = self._index.get(key)
        if not record:
            return None

        count = int(record.get("count", 0))
        if count <= 0:
            return None

        vessel_count = int(record.get("vessel_count", 0))
        aircraft_count = int(record.get("aircraft_count", 0))
        pressure_index = self._clamp(
            (math.log1p(count) / math.log1p(4500.0)) * 0.8 
            + min(1.0, vessel_count / 700.0) * 0.2
        )
        
        return {
            "entry_count": count,
            "vessel_count": vessel_count,
            "aircraft_count": aircraft_count,
            "program_count": int(record.get("program_count", 0)),
            "pressure_index": round(pressure_index, 4),
            "date": "2026-01-01",
        }

    def _looks_like_header(self, row: List[str]) -> bool:
        lower = [str(cell or "").strip().lower() for cell in row]
        if not lower:
            return False
        header_hits = {"ent_num", "name", "program", "type", "remarks"} & set(lower)
        return len(header_hits) >= 2

    def _row_to_map(self, row: List[str], header: Optional[List[str]]) -> Dict[str, str]:
        if not header:
            return {}
        row_map: Dict[str, str] = {}
        for idx, name in enumerate(header):
            if idx < len(row):
                row_map[name] = str(row[idx] or "").strip()
        return row_map

    def _extract_countries(self, row: List[str], *, header: Optional[List[str]]) -> List[str]:
        countries: List[str] = []

        row_map = self._row_to_map(row, header)
        candidates = [
            row_map.get("country", ""),
            row_map.get("countries", ""),
            row_map.get("program", ""),
            row_map.get("programs", ""),
            row_map.get("remarks", ""),
        ]
        # Headerless OFAC format fallback.
        if len(row) >= 12:
            candidates.extend([row[3], row[9], row[10], row[11], row[1]])
        elif len(row) >= 4:
            candidates.extend([row[3], row[1]])

        for candidate in candidates:
            for iso in resolve_iso3_candidates_from_text(str(candidate or "")):
                if iso and iso not in countries:
                    countries.append(iso)

        if not countries and len(row) >= 4:
            direct = resolve_country_to_iso3(row[3])
            if direct:
                countries.append(direct)

        return list(dict.fromkeys(countries))
