import logging
from pydantic import BaseModel
import dspy

logger = logging.getLogger("DIP3.Layer11.Decomposer")

class DecomposerSignature(dspy.Signature):
    """Breaks down a broad research goal into actionable academic search queries."""
    goal = dspy.InputField(desc="The broad executive goal.")
    queries = dspy.OutputField(desc="Comma separated list of specific boolean search queries.")

class GoalDecomposer:
    def __init__(self):
        self.module = dspy.Predict(DecomposerSignature)
        
    def decompose(self, goal: str) -> list[str]:
        try:
            result = self.module(goal=goal)
            queries = [q.strip() for q in result.queries.split(",")]
            return queries
        except Exception as e:
            logger.error(f"Decomposition failed, using fallback. {e}")
            return [f"{goal} AND 'impact'"]
