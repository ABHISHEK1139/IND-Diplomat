from dip.Config.config import config
"""
Prompt Optimizer (Layer 4)
==========================
Uses DSPy to mathematically tune the Ministers' prompts against the historical
backtesting registry (e.g. Ukraine 2022).
"""

import logging
from typing import List

try:
    import dspy
except ImportError:
    dspy = None

from dip.layer6_backtesting.crisis_registry import CRISIS_DATABASE
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("Layer4.optimizer")


# Define the DSPy Signature for a Hypothesis Tester
if dspy:
    class HypothesisGeneration(dspy.Signature):
        """Generate expected observable signals based on a geopolitical hypothesis."""
        context = dspy.InputField(desc="Current geopolitical state and historical context.")
        hypothesis = dspy.InputField(desc="The core hypothesis being tested (e.g. 'Is this a genuine military threat?').")
        expected_signals = dspy.OutputField(desc="A JSON array of short, specific observable signals we should expect to see if the hypothesis is true.")
else:
    HypothesisGeneration = None


if dspy:
    class MinisterDSPyModule(dspy.Module):
        def __init__(self):
            super().__init__()
            self.generate_signals = dspy.ChainOfThought(HypothesisGeneration)
            
        def forward(self, context: str, hypothesis: str) -> dspy.Prediction:
            return self.generate_signals(context=context, hypothesis=hypothesis)
else:
    MinisterDSPyModule = None


def setup_dspy_environment():
    """Configure DSPy to use the OpenRouter LLM."""
    if dspy is None:
        logger.error("DSPy not installed.")
        return False
        
    api_key = config.OPENROUTER_API_KEY
    model_name = config.LLM_MODEL
    
    # Map litellm/openrouter format to DSPy LM format if needed
    # (DSPy supports litellm under the hood via dspy.LiteLLM)
    try:
        lm = dspy.LM(f"openai/{model_name}", api_key=api_key, api_base="https://openrouter.ai/api/v1")
        dspy.settings.configure(lm=lm)
        return True
    except Exception as e:
        logger.error(f"Failed to configure DSPy: {e}")
        return False


def create_training_dataset():
    """Extract historical crises from Layer 6 to train the prompts."""
    if dspy is None: return []
    
    dataset = []
    # For example, use the Ukraine timeline to teach the LLM what signals to expect
    # when a real military escalation is happening.
    ukraine = CRISIS_DATABASE.get("UKRAINE_2022", {})
    
    for day in ukraine.get("timeline", []):
        context = f"Tensions escalating. Day {day['day']} relative to peak."
        hypothesis = "Is this a genuine military threat?"
        signals = day["signals"]
        
        # DSPy Example object
        ex = dspy.Example(context=context, hypothesis=hypothesis, expected_signals=str(signals)).with_inputs("context", "hypothesis")
        dataset.append(ex)
        
    return dataset


def optimize_prompts():
    """Run the DSPy Teleprompter to optimize the Minister module."""
    if not setup_dspy_environment():
        return
        
    dataset = create_training_dataset()
    if not dataset:
        logger.warning("No dataset generated for DSPy.")
        return
        
    logger.info(f"Starting DSPy optimization with {len(dataset)} examples...")
    
    # We would use a teleprompter here like BootstrapFewShot
    # teleprompter = dspy.BootstrapFewShot(metric=custom_signal_match_metric)
    # optimized_module = teleprompter.compile(MinisterDSPyModule(), trainset=dataset)
    # optimized_module.save("optimized_minister.json")
    
    logger.info("DSPy scaffolding complete. Ready for prompt optimization runs.")

if __name__ == "__main__":
    optimize_prompts()
