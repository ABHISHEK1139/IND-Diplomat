"""
World Bank Economic Data Provider.
"""

import csv
import os
from typing import Any, Dict, List, Optional, Tuple

from engine.Layer3_StateModel.providers.base_provider import BaseProvider

class WorldBankProvider(BaseProvider):
    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        # Structure: code -> {series_code: [(year, val)]}
        self._index: Dict[str, Dict[str, List[Tuple[int, float]]]] = {}

    def load_index(self):
        if self._loaded:
            return
            
        path = os.path.join(self.data_dir, "WorldBank_Economy_Data.csv")
        if not os.path.exists(path):
            return
            
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Support both legacy WB export schema and current local schema.
                country = (
                    row.get("Country Code")
                    or row.get("economy")
                    or row.get("country_code")
                    or ""
                ).strip().upper()
                series = (
                    row.get("Series Code")
                    or row.get("series")
                    or row.get("series_code")
                    or ""
                ).strip()
                if not country or not series:
                    continue
                
                points = []
                for key, val in row.items():
                    if not key:
                        continue
                    year = None
                    # Legacy WB schema: "2020 [YR2020]"
                    if " [YR" in key:
                        year_str = key.split(" [")[0]
                        try:
                            year = int(year_str)
                        except ValueError:
                            year = None
                    # Current local schema: "YR2020"
                    elif key.upper().startswith("YR"):
                        suffix = key[2:]
                        if suffix.isdigit():
                            year = int(suffix)

                    if year is None:
                        continue

                    v = self._safe_float(val)
                    if v is not None:
                        points.append((year, v))
                
                points.sort(key=lambda x: x[0])
                if country not in self._index:
                    self._index[country] = {}
                self._index[country][series] = points
        
        self._loaded = True

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        series_map = self._index.get(country_code.upper())
        if not series_map:
            return None

        target_year = self._target_year(date)
        
        # Series codes
        # GDP: NY.GDP.MKTP.CD
        # CPI Inflation: FP.CPI.TOTL.ZG
        # Debt % GDP: GC.DOD.TOTL.GD.ZS
        
        gdp_point = self._latest_series_point(series_map.get("NY.GDP.MKTP.CD", []), target_year)
        inf_point = self._latest_series_point(series_map.get("FP.CPI.TOTL.ZG", []), target_year)
        debt_point = self._latest_series_point(series_map.get("GC.DOD.TOTL.GD.ZS", []), target_year)

        if not any((gdp_point, inf_point, debt_point)):
            return None

        # Calculate GDP Growth
        gdp_growth = None
        gdp_series = series_map.get("NY.GDP.MKTP.CD", [])
        if gdp_point:
            # Find previous point
            prev = self._latest_series_point(gdp_series, gdp_point[0] - 1)
            # Ensure it's actually the previous year? Or just previous avail? Builder checked point[0]-1 specifically.
            # Logic: `self._latest_series_point(gdp_series, gdp_point[0] - 1)`
            if prev and prev[1] and prev[1] != 0:
                gdp_growth = ((gdp_point[1] - prev[1]) / abs(prev[1])) * 100.0

        latest_year = max(
            p[0]
            for p in (gdp_point, inf_point, debt_point)
            if p is not None
        )
        
        result = {
            "gdp": gdp_point[1] if gdp_point else None,
            "gdp_year": gdp_point[0] if gdp_point else None,
            "inflation": inf_point[1] if inf_point else None,
            "inflation_year": inf_point[0] if inf_point else None,
            "debt_to_gdp": debt_point[1] if debt_point else None,
            "debt_year": debt_point[0] if debt_point else None,
            "gdp_growth": gdp_growth,
            "date": f"{latest_year}-12-31",
        }
        record_count = int(bool(gdp_point)) + int(bool(inf_point)) + int(bool(debt_point))
        return result

    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None: return None
        text = str(value).strip()
        if not text or text == "..": return None # WorldBank uses ".." for missing
        try: return float(text)
        except: return None
        
    def _latest_series_point(self, series: List[Tuple[int, float]], target_year: int) -> Optional[Tuple[int, float]]:
        valid = [p for p in series if p[0] <= target_year]
        return valid[-1] if valid else None
