"""
Contradiction Engine
=====================
Uses DeBERTa NLI (Natural Language Inference) to compare claims 
and detect whether they entail, contradict, or are neutral to each other.
"""

import logging
from typing import Tuple

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

logger = logging.getLogger("Layer3.ContradictionEngine")


class ContradictionEngine:
    """
    Detects contradictions between pieces of evidence or claims.
    """

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-xsmall"):
        self.model_name = model_name
        self._classifier = None

    def _load_model(self):
        if not pipeline:
            logger.warning("transformers not installed. Contradiction engine skipped.")
            return

        if self._classifier is None:
            logger.info(f"Loading NLI Model for Contradiction Detection: {self.model_name}")
            try:
                # NLI models output: entailment, neutral, contradiction
                self._classifier = pipeline(
                    "zero-shot-classification", 
                    model=self.model_name
                )
            except Exception as e:
                logger.error(f"Failed to load NLI model: {e}")
                self._classifier = None

    def compare(self, premise: str, hypothesis: str) -> Tuple[str, float]:
        """
        Compare a hypothesis against a premise.
        Returns the dominant label (Entailment, Contradiction, Neutral) and confidence.
        """
        self._load_model()
        if self._classifier is None:
            return ("Neutral", 0.0)
            
        try:
            # We use zero-shot pipeline mapping to NLI concepts
            result = self._classifier(
                premise,
                candidate_labels=["entailment", "contradiction", "neutral"],
                hypothesis_template=f"This text means that {hypothesis}."
            )
            
            best_label = result["labels"][0].capitalize()
            score = result["scores"][0]
            
            logger.debug(f"NLI comparison: {best_label} ({score:.2f})")
            return best_label, score
            
        except Exception as e:
            logger.error(f"Contradiction detection failed: {e}")
            return ("Neutral", 0.0)
