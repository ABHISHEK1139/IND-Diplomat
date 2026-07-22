"""
Budget Manager — Collection Resource Constraints
==================================================

Manages collection budgets:
    - Max articles (prevent overwhelming downstream layers)
    - Max time (prevent long-running collections)
    - Max cost (for paid APIs)
"""

import logging
import time

logger = logging.getLogger("Layer1.BudgetManager")


class BudgetManager:
    """
    Tracks and enforces collection resource limits.

    Prevents runaway collection from consuming too many API calls,
    too much time, or too much money.
    """

    def __init__(
        self,
        max_articles: int = 200,
        max_time_seconds: float = 300.0,
        max_cost_usd: float = 2.0,
    ):
        self.max_articles = max_articles
        self.max_time_seconds = max_time_seconds
        self.max_cost_usd = max_cost_usd

        self.articles_collected = 0
        self.cost_spent = 0.0
        self.start_time = time.time()

    def can_collect(self) -> bool:
        """Check if we still have budget to collect more."""
        if self.articles_collected >= self.max_articles:
            return False
        if self.elapsed_seconds() >= self.max_time_seconds:
            return False
        if self.cost_spent >= self.max_cost_usd:
            return False
        return True

    def record_collection(
        self,
        articles_count: int,
        time_seconds: float = 0.0,
        cost_usd: float = 0.0,
    ) -> None:
        """Record resources consumed by a collection operation."""
        self.articles_collected += articles_count
        self.cost_spent += cost_usd
        # Time is tracked automatically via start_time

    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    def remaining(self) -> dict:
        """Return remaining budget as a dictionary."""
        return {
            "articles_remaining": max(0, self.max_articles - self.articles_collected),
            "time_remaining_seconds": max(0, self.max_time_seconds - self.elapsed_seconds()),
            "cost_remaining_usd": max(0, self.max_cost_usd - self.cost_spent),
        }

    def summary(self) -> str:
        """Human-readable budget summary."""
        r = self.remaining()
        return (
            f"Budget: {self.articles_collected}/{self.max_articles} articles, "
            f"{self.elapsed_seconds():.1f}/{self.max_time_seconds:.0f}s elapsed, "
            f"${self.cost_spent:.3f}/${self.max_cost_usd:.2f} spent"
        )
