"""
GLiNER Entity Extractor
=========================
Identifies and extracts named entities from text chunks without
needing a massive LLM.
"""

import logging
from typing import List, Dict, Any

try:
    from gliner import GLiNER
except ImportError:
    GLiNER = None

logger = logging.getLogger("Layer3.EntityExtractor")


class EntityExtractor:
    """
    Extracts core entities from textual evidence.
    """

    def __init__(self, model_name: str = "urchade/gliner_medium-v2.1"):
        self.model_name = model_name
        self._model = None
        self.labels = [
            "person", "organization", "company", "country", "city", 
            "technology", "policy", "disease", "weapon", "currency"
        ]

    def _load_model(self):
        if not GLiNER:
            logger.warning("GLiNER not installed. Entity extraction skipped.")
            return

        if self._model is None:
            logger.info(f"Loading GLiNER for World Model: {self.model_name}")
            try:
                self._model = GLiNER.from_pretrained(self.model_name)
            except Exception as e:
                logger.error(f"Failed to load GLiNER: {e}")
                self._model = None

    def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts entities from the given text.
        """
        self._load_model()
        if self._model is None:
            return []

        try:
            # GLiNER handles long texts better if chunked, but for now we pass directly
            entities = self._model.predict_entities(text, self.labels)
            
            # Format output
            results = []
            for ent in entities:
                results.append({
                    "text": ent["text"],
                    "label": ent["label"],
                    "score": ent.get("score", 1.0)
                })
            
            logger.debug(f"Extracted {len(results)} entities.")
            return results
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
