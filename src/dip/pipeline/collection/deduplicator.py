"""
Deduplicator — Semantic Clustering
===================================

Replaces naive Jaccard shingling with SentenceTransformers and HDBSCAN
to semantically cluster articles and eliminate echo-chamber duplicates.
"""

import logging
from typing import List

try:
    from sentence_transformers import SentenceTransformer
    import hdbscan
    import numpy as np
except ImportError:
    SentenceTransformer = None
    hdbscan = None
    np = None

from dip.core.schema import RawObservation

logger = logging.getLogger("Layer1.SemanticDeduplicator")

# Source reliability for tie-breaking
_SOURCE_RELIABILITY = {
    "DATASET": 5,
    "GOV": 4,
    "RESEARCH": 3,
    "NEWS": 2,
    "OSINT": 1,
    "SOCIAL": 0,
}


class Deduplicator:
    """
    Uses dense embeddings and density-based clustering to find semantic duplicates.
    Keeps the most reliable source from each cluster.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", cluster_size: int = 2):
        self.model_name = model_name
        self.cluster_size = cluster_size
        self._model = None

    def _load_model(self):
        if not SentenceTransformer or not hdbscan:
            logger.warning("sentence-transformers or hdbscan not installed. Returning unique by exact match.")
            return

        if self._model is None:
            logger.info(f"Loading SentenceTransformer: {self.model_name}")
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                self._model = None

    def deduplicate(self, observations: List[RawObservation]) -> List[RawObservation]:
        """
        Embed all observations, cluster them, and pick the best representative for each.
        """
        if len(observations) <= 1:
            return observations

        self._load_model()
        
        # Fallback if libraries are missing
        if self._model is None or np is None or hdbscan is None:
            seen = set()
            kept = []
            for obs in observations:
                if obs.content not in seen:
                    kept.append(obs)
                    seen.add(obs.content)
            return kept

        # 1. Embed contents
        contents = [obs.content for obs in observations]
        try:
            embeddings = self._model.encode(contents, convert_to_numpy=True)
            
            # 2. Cluster using HDBSCAN
            # min_cluster_size of 2 means any 2 highly similar articles form a duplicate cluster
            clusterer = hdbscan.HDBSCAN(min_cluster_size=self.cluster_size, metric='euclidean')
            labels = clusterer.fit_predict(embeddings)
            
            # 3. Resolve clusters
            # labels >= 0 are clusters. label == -1 is noise (unique standalone articles)
            unique_kept = []
            clusters = {}
            
            for idx, label in enumerate(labels):
                if label == -1:
                    unique_kept.append(observations[idx])
                else:
                    if label not in clusters:
                        clusters[label] = []
                    clusters[label].append(observations[idx])
                    
            # For each cluster, keep the most reliable source
            for label, cluster_obs in clusters.items():
                best_obs = max(
                    cluster_obs,
                    key=lambda o: _SOURCE_RELIABILITY.get(o.source_type, 0)
                )
                unique_kept.append(best_obs)
                
            removed = len(observations) - len(unique_kept)
            logger.info(f"HDBSCAN Deduplicator: removed {removed} duplicates, kept {len(unique_kept)} unique.")
            
            return unique_kept

        except Exception as e:
            logger.error(f"Deduplication failed: {e}. Returning all observations.")
            return observations
