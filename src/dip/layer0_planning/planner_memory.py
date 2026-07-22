"""
Planner Memory — Reusing Investigation Plans
==============================================

Uses the Mem0 library to persist and recall previous investigation
structures so we don't plan the same thing from scratch twice.
"""

import logging
from typing import List, Dict

try:
    from mem0 import Memory
except ImportError:
    Memory = None

logger = logging.getLogger("Layer0.PlannerMemory")


class PlannerMemory:
    """
    Recalls previous investigation plans based on similarity to the
    current query, helping the planner bootstrap faster and more consistently.
    """

    def __init__(self, db_path: str = "./mem0_db"):
        self.db_path = db_path
        self._memory = None
        self._load_memory()

    def _load_memory(self):
        if not Memory:
            logger.warning("mem0ai not installed. Planner Memory disabled.")
            return

        try:
            # Configure Mem0 to use local storage
            config = {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "path": self.db_path,
                    }
                }
            }
            self._memory = Memory.from_config(config)
            logger.info("Mem0 Planner Memory initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Mem0: {e}")
            self._memory = None

    def search_similar_plans(self, query: str) -> List[Dict]:
        """
        Search for past plans that are similar to the current query.
        """
        if not self._memory:
            return []
            
        try:
            results = self._memory.search(query, user_id="system_planner", limit=3)
            # Mem0 returns a list of dictionaries with 'memory' key
            return [res for res in results]
        except Exception as e:
            logger.error(f"Mem0 search failed: {e}")
            return []

    def store_plan(self, query: str, plan_summary: str):
        """
        Store a successful plan into memory.
        """
        if not self._memory:
            return
            
        try:
            content = f"Investigation Query: '{query}'\nPlan Used: {plan_summary}"
            self._memory.add(content, user_id="system_planner")
            logger.info("Stored new plan in Mem0.")
        except Exception as e:
            logger.error(f"Mem0 add failed: {e}")
