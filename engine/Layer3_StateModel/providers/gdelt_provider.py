"""
GDELT Tension Data Provider.
"""

import json
import os
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.providers.base_provider import BaseProvider
from engine.Layer3_StateModel.temporal.temporal_reasoner import temporal_reasoner

# Import CAMEO country codes and regional filter from canonical config.
try:
    from engine.Layer1_Collection.sensors.cameo_config import (
        CAMEO_COUNTRY_CODES,
        CAMEO_REGIONAL_CODES as _CAMEO_REGIONAL_CODES,
    )
except (ImportError, ModuleNotFoundError):
    CAMEO_COUNTRY_CODES = {}
    _CAMEO_REGIONAL_CODES = set()

class GDELTProvider(BaseProvider):
    def __init__(self, data_dir: str, tension_history_path: str = None):
        super().__init__(data_dir)
        # Allow override for tension history path, default to standard location
        if tension_history_path:
            self.tension_path = tension_history_path
        else:
            # Reconstruct path relative to typical data_dir or root
            # Assuming data_dir is .../LAYER1_COLLECTION/data/global_risk_data
            # tension_history_path is usually .../data/tension_history.json (root data)
            # We'll need a way to pass this in or deduce it.
            # For now, let's assume it's passed or strict default.
            self.tension_path = "data/tension_history.json" 

        self._tension_cache: Dict[str, Any] = {}
        self.temporal = temporal_reasoner

    def set_tension_path(self, path: str):
        self.tension_path = path

    def load_index(self):
        if self._loaded:
            return

        # Register CAMEO country coverage (excluding regional codes).
        cameo_countries = {
            code: name
            for code, name in CAMEO_COUNTRY_CODES.items()
            if code not in _CAMEO_REGIONAL_CODES
        }
        self._index = cameo_countries

        self._set_dataset_path(self.tension_path)

        if not os.path.exists(self.tension_path):
            # GDELT provider is still valid — it knows 200+ countries even without tension data
            self._warn("tension_history_file_missing")
            self._finalize_status(loaded=True)
            return

        try:
            with open(self.tension_path, "r", encoding="utf-8") as f:
                self._tension_cache = json.load(f)
            # Count actual countries with data
            countries_with_data = set()
            for date_data in self._tension_cache.values():
                countries_with_data.update(date_data.keys())
            self._set_status_counts(
                rows_read=sum(
                    len(entries)
                    for date_data in self._tension_cache.values()
                    for entries in date_data.values()
                ),
                rows_kept=sum(
                    len(entries)
                    for date_data in self._tension_cache.values()
                    for entries in date_data.values()
                ),
            )
            self._finalize_status(loaded=True)
        except Exception as exc:
            self._tension_cache = {}
            self._set_error(str(exc))
            self._finalize_status(loaded=False)

    def get_signal(self, country_code: str, date: str) -> Optional[Dict[str, Any]]:
        self.load_index()
        
        country = country_code.upper()
        gdelt_scores: List[Dict[str, Any]] = []
        evidence_rows: List[Dict[str, Any]] = []
        
        # Structure of tension_cache: {date: {country: [entries]}}
        for data_date, date_data in self._tension_cache.items():
            country_entries = date_data.get(country, [])
            for entry in country_entries:
                source_name = str(entry.get("source_name") or "GDELT")
                url = str(entry.get("url") or "https://www.gdeltproject.org/")
                excerpt = str(
                    entry.get("summary")
                    or f"{country}: tension={entry.get('tension', 0.5)} "
                    f"conflict_count={entry.get('conflict_count', 0)} coop_count={entry.get('coop_count', 0)}"
                ).strip()
                gdelt_scores.append(
                    {
                        "value": entry.get("tension", 0.5),
                        "date": data_date,
                        "source": "GDELT",
                        "conflict_count": entry.get("conflict_count", 0),
                        "coop_count": entry.get("coop_count", 0),
                        "actors": entry.get("major_actors", []),
                        "url": url,
                        "source_name": source_name,
                        "excerpt": excerpt,
                    }
                )
                evidence_rows.append(
                    {
                        "source_id": f"GDELT_{country}_{data_date}",
                        "source": source_name,
                        "source_name": source_name,
                        "url": url,
                        "date": data_date,
                        "publication_date": data_date,
                        "excerpt": excerpt[:300],
                        "reliability": 0.7,
                        "confidence": 0.7,
                    }
                )

        if not gdelt_scores:
            return None

        decayed = self.temporal.apply_decay_to_scores(gdelt_scores, reference_date=date)
        if not decayed:
            return None

        total_weight = sum(d["weight"] for d in decayed)
        weighted_tension = sum(d["value"] * d["weight"] for d in decayed) / max(total_weight, 1e-9)
        total_conflict = sum(int(d.get("conflict_count", 0)) for d in decayed)
        total_coop = sum(int(d.get("coop_count", 0)) for d in decayed)
        freshest = max(decayed, key=lambda x: x["date"])

        actor_counts: Dict[str, int] = {}
        for d in decayed:
            for actor in d.get("actors", []):
                actor_counts[actor] = actor_counts.get(actor, 0) + 1
        top_actors = sorted(actor_counts, key=actor_counts.get, reverse=True)[:5]

        result = {
            "tension": round(weighted_tension, 4),
            "conflict_count": total_conflict,
            "coop_count": total_coop,
            "actors": top_actors,
            "date": freshest["date"],
            "num_datapoints": len(decayed),
            "freshest_weight": freshest["weight"],
            "oldest_days": max(int(d["days_ago"]) for d in decayed),
            "evidence": evidence_rows,
        }
        return result
