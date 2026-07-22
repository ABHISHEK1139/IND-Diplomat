"""
Scope Detector — Specialized Entity Extraction
==============================================

Uses GLiNER (Generalist and Lightweight INformation Extraction)
to extract investigation parameters like countries, organizations,
companies, time horizons, and domains without hitting an API LLM.
"""

import logging
from typing import List, Dict

try:
    from gliner import GLiNER
except ImportError:
    GLiNER = None

logger = logging.getLogger("Layer0.ScopeDetector")


class ScopeDetector:
    """
    Extracts entities from user queries to form the InvestigationScope.
    Uses a local GLiNER model for zero-cost, high-speed extraction.
    """

    def __init__(self, model_name: str = "urchade/gliner_medium-v2.1"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if not GLiNER:
            logger.warning("GLiNER not installed. Returning empty scope.")
            return

        if self._model is None:
            logger.info(f"Loading GLiNER model: {self.model_name}")
            try:
                self._model = GLiNER.from_pretrained(self.model_name)
            except Exception as e:
                logger.error(f"Failed to load GLiNER: {e}")
                self._model = None

    def detect(self, query: str) -> Dict[str, List[str]]:
        """
        Detect entities for the investigation scope.
        """
        self._load_model()
        
        scope_entities = {
            "countries": [],
            "organizations": [],
            "companies": [],
            "time_horizon": [],
            "domains": [],
            "key_actors": []
        }
        
        if self._model is None:
            return scope_entities

        # Define the labels we want GLiNER to find
        labels = ["country", "organization", "company", "date", "year", "domain", "topic", "person"]
        
        try:
            entities = self._model.predict_entities(query, labels)
            
            for ent in entities:
                text = ent["text"]
                label = ent["label"].lower()
                
                if label == "country":
                    if text not in scope_entities["countries"]:
                        scope_entities["countries"].append(text)
                elif label == "organization":
                    if text not in scope_entities["organizations"]:
                        scope_entities["organizations"].append(text)
                elif label == "company":
                    if text not in scope_entities["companies"]:
                        scope_entities["companies"].append(text)
                elif label in ["date", "year"]:
                    if text not in scope_entities["time_horizon"]:
                        scope_entities["time_horizon"].append(text)
                elif label in ["domain", "topic"]:
                    if text not in scope_entities["domains"]:
                        scope_entities["domains"].append(text)
                elif label == "person":
                    if text not in scope_entities["key_actors"]:
                        scope_entities["key_actors"].append(text)
                        
            logger.info(f"Detected scope entities: {scope_entities}")
        except Exception as e:
            logger.error(f"Error during scope detection: {e}")

        return scope_entities
