"""
V-Dem Democracy Data Provider.
"""

import csv
import os
from typing import Any, Dict, List, Optional
from statistics import mean

from engine.Layer3_StateModel.providers.base_provider import BaseProvider

class VDemProvider(BaseProvider):
    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        # Structure: code -> [{year: int, polyarchy: float, libdem: float}]
        self._index: Dict[str, List[Dict[str, Any]]] = {}

    def load_index(self):
        if self._loaded:
            return
            
        path = os.path.join(
            self.data_dir,
            "V-Dem-CY-FullOthers-v15_csv",
            "V-Dem-CY-Full+Others-v15.csv",
        )
        if not os.path.exists(path):
            return

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                country = row.get("country_text_id", "").strip().upper()
                if not country: continue
                
                try:
                    year = int(row.get("year", 0))
                    polyarchy = self._safe_float(row.get("v2x_polyarchy"))
                    libdem = self._safe_float(row.get("v2x_libdem"))
                    
                    if country not in self._index:
                        self._index[country] = []
                        
                    self._index[country].append({
                        "year": year,
                        "polyarchy": polyarchy,
                        "libdem": libdem,
                        "raw": row
                    })
                except ValueError:
                    continue
        
        # Sort by year
        for k in self._index:
            self._index[k].sort(key=lambda x: x["year"])
            
        self._loaded = True

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        series = self._index.get(country_code.upper())
        if not series:
            return None

        target_year = self._target_year(date)
        current = None
        for item in series:
            if item["year"] <= target_year:
                current = item
        # If no data before target year, take oldest? Or return None?
        # Builder logic: "If current is None: current = series[-1]" (take latest available if target > all, or just last imported)
        # wait, loop goes through sorted series. If target=2025 and data ends 2023, loop sets current to 2023.
        # If target=1900 and data starts 1950, current stays None.
        # Builder logic:
        # if current is None: current = series[-1] (Fallback to LATEST if target is too early? Or too late?)
        # Let's assume fallback to latest available.
        if current is None and series:
            current = series[-1]
            
        if not current: return None

        idx_values = [v for v in (current.get("polyarchy"), current.get("libdem")) if v is not None]
        if not idx_values:
            return None
        vdem_index = mean(idx_values)

        past_window = [
            mean([v for v in (r.get("polyarchy"), r.get("libdem")) if v is not None])
            for r in series
            if (target_year - 5) <= r["year"] < current["year"]
        ]
        trend = vdem_index - mean(past_window) if past_window else 0.0

        return {
            "polyarchy": current.get("polyarchy"),
            "libdem": current.get("libdem"),
            "index": round(vdem_index, 4),
            "trend": round(trend, 4),
            "year": current["year"],
            "date": f"{current['year']}-12-31",
        }

    def _safe_float(self, value: Any) -> Optional[float]:
        try: return float(value)
        except: return None
