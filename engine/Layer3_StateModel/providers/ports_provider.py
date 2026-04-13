"""
World Ports Data Provider.
"""

import csv
import os
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.providers.base_provider import BaseProvider
from Core.orchestrator.knowledge_port import knowledge_port

class PortsProvider(BaseProvider):
    CHOKEPOINT_KEYWORDS = (
        "strait", "canal", "hormuz", "malacca", "bab el mandeb",
        "red sea", "persian gulf", "suez", "bosporus", "dardanelles", "south china sea",
    )

    def __init__(self, data_dir: str):
        super().__init__(data_dir)
        self._index: Dict[str, Dict[str, Any]] = {}

    def load_index(self):
        if self._loaded: return
        
        path = os.path.join(self.data_dir, "UpdatedPub150.csv")
        if not os.path.exists(path): return

        tmp: Dict[str, Dict[str, float]] = {}
        try:
            with open(path, "r", encoding="utf-8", errors="ignore", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    country_name = (row.get("Country Code") or "").strip()
                    if not country_name: continue
                    
                    canonical = knowledge_port.resolve_entity(country_name)
                    if canonical:
                        iso = canonical.upper()
                    else:
                        iso_guess = country_name.upper()
                        iso = iso_guess if len(iso_guess) == 3 and iso_guess.isalpha() else None
                    if not iso: continue

                    water_body = (row.get("World Water Body") or "").strip().lower()
                    channel_depth = self._safe_float(row.get("Channel Depth (m)")) or 0.0

                    bucket = tmp.setdefault(
                        iso,
                        {"total_ports": 0.0, "chokepoint_ports": 0.0, "total_channel_depth_m": 0.0},
                    )
                    bucket["total_ports"] += 1.0
                    bucket["total_channel_depth_m"] += channel_depth
                    if any(keyword in water_body for keyword in self.CHOKEPOINT_KEYWORDS):
                        bucket["chokepoint_ports"] += 1.0

            for iso, bucket in tmp.items():
                total_ports = max(bucket["total_ports"], 1.0)
                self._index[iso] = {
                    "total_ports": int(bucket["total_ports"]),
                    "chokepoint_ports": int(bucket["chokepoint_ports"]),
                    "avg_channel_depth_m": float(bucket["total_channel_depth_m"] / total_ports),
                }
            self._loaded = True
        except Exception:
            self._index = {}

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        record = self._index.get(country_code.upper())
        if not record: return None

        total_ports = int(record.get("total_ports", 0))
        if total_ports <= 0: return None

        chokepoint_ports = int(record.get("chokepoint_ports", 0))
        chokepoint_ratio = chokepoint_ports / max(total_ports, 1)
        exposure_index = max(0.0, min(1.0, (chokepoint_ratio * 0.65) + (min(1.0, total_ports / 150.0) * 0.35)))
        
        return {
            "total_ports": total_ports,
            "chokepoint_ports": chokepoint_ports,
            "avg_channel_depth_m": round(float(record.get("avg_channel_depth_m", 0.0)), 2),
            "chokepoint_index": round(exposure_index, 4),
            "date": "2025-01-01",
        }

    def _safe_float(self, value: Any) -> Optional[float]:
        try: return float(value)
        except: return None
