"""
Source Validator — Zero-Shot Credibility Scoring
==================================================

Replaces heuristic credibility scoring with a small NLP model (MiniLM)
to assess text credibility and bias.
"""

import logging
from datetime import datetime, timezone
from typing import List

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

from pydantic import BaseModel
from dip.core.schema import RawObservation

logger = logging.getLogger("Layer1.Validator")


class ValidatedObservation(BaseModel):
    """A RawObservation with credibility and quality metadata."""
    observation: RawObservation
    credibility_score: float
    bias_indicator: str
    freshness_score: float
    is_duplicate: bool = False
    passes_threshold: bool = True


class SourceValidator:
    """
    Scores observations for credibility using an OSS zero-shot classification model.
    """

    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold
        self._classifier = None

    def _load_model(self):
        if not pipeline:
            logger.warning("transformers not installed. Using heuristic credibility.")
            return

        if self._classifier is None:
            logger.info("Loading Zero-Shot Classifier (MiniLM)")
            try:
                # Using a small zero-shot classifier to detect bias/credibility
                self._classifier = pipeline(
                    "zero-shot-classification", 
                    model="cross-encoder/nli-deberta-v3-xsmall"
                )
            except Exception as e:
                logger.error(f"Failed to load classifier: {e}")
                self._classifier = None

    def validate(self, observation: RawObservation) -> ValidatedObservation:
        """Score a single observation."""
        self._load_model()
        
        freshness = self._compute_freshness(observation.timestamp)
        
        credibility = 0.5
        bias = "Medium"
        
        if self._classifier:
            try:
                # Zero-shot classification for bias
                res = self._classifier(
                    observation.content[:500], # limit length
                    candidate_labels=["objective reporting", "highly biased opinion", "propaganda"],
                )
                top_label = res["labels"][0]
                top_score = res["scores"][0]
                
                if top_label == "highly biased opinion" and top_score > 0.6:
                    bias = "High"
                    credibility = 0.2
                elif top_label == "propaganda" and top_score > 0.5:
                    bias = "High"
                    credibility = 0.1
                else:
                    bias = "Low"
                    credibility = 0.8
                    
            except Exception as e:
                logger.debug(f"Classification failed: {e}")
        else:
            # Fallback heuristic
            if observation.source_type == "DATASET": credibility = 0.9
            elif observation.source_type == "NEWS": credibility = 0.6
            elif observation.source_type == "SOCIAL": credibility = 0.3
            
        passes = credibility >= self.threshold

        return ValidatedObservation(
            observation=observation,
            credibility_score=credibility,
            bias_indicator=bias,
            freshness_score=freshness,
            passes_threshold=passes,
        )

    def validate_batch(self, observations: List[RawObservation]) -> List[ValidatedObservation]:
        """Validate and filter a batch of observations."""
        validated = [self.validate(obs) for obs in observations]
        passed = [v for v in validated if v.passes_threshold]
        rejected = len(validated) - len(passed)
        if rejected > 0:
            logger.info(f"Validator: {rejected}/{len(validated)} observations rejected.")
        return passed

    def _compute_freshness(self, timestamp_str: str) -> float:
        """Compute freshness score: 1.0 = brand new, decays with age."""
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_hours = (now - ts).total_seconds() / 3600
            if age_hours < 24:
                return 1.0
            elif age_hours < 168:
                return 0.8
            else:
                return 0.5
        except Exception:
            return 0.5
