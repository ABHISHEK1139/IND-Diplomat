"""
EEZ Maritime Data Provider.
"""

import math
import os
import sqlite3
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.providers.base_provider import BaseProvider

class EEZProvider(BaseProvider):
    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        self._index: Dict[str, Dict[str, Any]] = {}

    def load_index(self):
        if self._loaded: return
        
        path = os.path.join(self.data_dir, "World_EEZ_v12_20231025_LR", "eez_v12_lowres.gpkg")
        if not os.path.exists(path): return

        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT ISO_SOV1, ISO_SOV2, ISO_SOV3, AREA_KM2 FROM eez_v12_lowres"
            )
            tmp: Dict[str, Dict[str, Any]] = {}
            for iso1, iso2, iso3, area_km2 in rows:
                countries = []
                for iso in (iso1, iso2, iso3):
                    iso_text = (str(iso).strip().upper() if iso else "")
                    if len(iso_text) == 3 and iso_text.isalpha():
                        countries.append(iso_text)
                countries = list(dict.fromkeys(countries))
                if len(countries) <= 1:
                    continue

                area = float(area_km2 or 0.0)
                share = area / max(len(countries), 1)
                for iso in countries:
                    bucket = tmp.setdefault(
                        iso,
                        {"overlap_count": 0, "shared_area_km2": 0.0, "counterparties": set()},
                    )
                    bucket["overlap_count"] += 1
                    bucket["shared_area_km2"] += share
                    for other in countries:
                        if other != iso:
                            bucket["counterparties"].add(other)

            for iso, bucket in tmp.items():
                self._index[iso] = {
                    "overlap_count": int(bucket["overlap_count"]),
                    "shared_area_km2": float(bucket["shared_area_km2"]),
                    "counterparty_count": len(bucket["counterparties"]),
                }
            conn.close()
            self._loaded = True
        except Exception:
            self._index = {}

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        record = self._index.get(country_code.upper())
        if not record: return None

        overlap_count = int(record.get("overlap_count", 0))
        shared_area = float(record.get("shared_area_km2", 0.0))
        if overlap_count <= 0 and shared_area <= 0.0:
            return None

        # Logic from Builder
        territorial_pressure = max(0.0, min(1.0,
            (math.log1p(shared_area) / math.log1p(1200000.0)) * 0.6
            + min(1.0, overlap_count / 120.0) * 0.4
        ))
        
        return {
            "overlap_count": overlap_count,
            "counterparty_count": int(record.get("counterparty_count", 0)),
            "shared_area_km2": round(shared_area, 2),
            "territorial_pressure_index": round(territorial_pressure, 4),
            "date": "2023-10-25", # Fixed date as per original logic? Or raw data date? Builder used explicit string.
        }
