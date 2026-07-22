"""
Query Expander — Search Term Generation
=========================================

Uses KeyBERT to expand a user query into a set of relevant
keywords without hitting an API LLM.
"""

import logging
from typing import List

try:
    from keybert import KeyBERT
except ImportError:
    KeyBERT = None

logger = logging.getLogger("Layer0.QueryExpander")


class QueryExpander:
    """
    Expands a base investigation query into specific keywords.
    Uses a local KeyBERT model for fast, free extraction.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._kw_model = None

    def _load_model(self):
        if not KeyBERT:
            logger.warning("KeyBERT not installed. Returning original query.")
            return

        if self._kw_model is None:
            logger.info(f"Loading KeyBERT model: {self.model_name}")
            try:
                self._kw_model = KeyBERT(model=self.model_name)
            except Exception as e:
                logger.error(f"Failed to load KeyBERT: {e}")
                self._kw_model = None

    def expand(self, text: str, top_n: int = 5) -> List[str]:
        """
        Extract top keywords from the text to serve as search queries.
        """
        self._load_model()
        
        if self._kw_model is None:
            return [text]

        try:
            # Extract keywords with unigrams and bigrams
            keywords = self._kw_model.extract_keywords(
                text, 
                keyphrase_ngram_range=(1, 2), 
                stop_words='english', 
                top_n=top_n
            )
            expanded = [kw[0] for kw in keywords]
            logger.info(f"Expanded queries: {expanded}")
            return expanded
        except Exception as e:
            logger.error(f"Error during query expansion: {e}")
            return [text]
