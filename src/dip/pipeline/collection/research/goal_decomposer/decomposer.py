import logging
from pydantic import BaseModel

try:
    import dspy
except ImportError:  # optional dependency; fail only on actual use
    dspy = None

logger = logging.getLogger("DIP3.Layer11.Decomposer")

if dspy is not None:
    class DecomposerSignature(dspy.Signature):
        """Breaks down a broad research goal into actionable academic search queries."""
        goal = dspy.InputField(desc="The broad executive goal.")
        queries = dspy.OutputField(desc="Comma separated list of specific boolean search queries.")
else:  # pragma: no cover - minimal installs without dspy
    DecomposerSignature = None

class GoalDecomposer:
    def __init__(self):
        if dspy is None or DecomposerSignature is None:
            raise ImportError("dspy is not installed. pip install 'politiq-ai[reasoning]'")
        self.module = dspy.Predict(DecomposerSignature)
        
    def decompose(self, goal: str) -> list[str]:
        try:
            result = self.module(goal=goal)
            queries = [q.strip() for q in result.queries.split(",")]
            return queries
        except Exception as e:
            logger.error(f"Decomposition failed, using fallback. {e}")
            return [f"{goal} AND 'impact'"]
