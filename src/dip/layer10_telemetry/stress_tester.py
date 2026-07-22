import logging
import random
from typing import List
from dip.core.schema import Signal

logger = logging.getLogger("Layer10.StressTester")

class StressTester:
    """
    Adversarial engine to inject noise, duplicates, and conflicts into signals
    to test the resilience of the World Model (Layer 3).
    """
    def __init__(self, noise_ratio: float = 0.2):
        self.noise_ratio = noise_ratio
        
    def inject_noise(self, original_signals: List[Signal]) -> List[Signal]:
        if not original_signals:
            return []
            
        corrupted = original_signals.copy()
        num_injections = max(1, int(len(original_signals) * self.noise_ratio))
        
        for _ in range(num_injections):
            strategy = random.choice(["duplicate", "conflict", "hallucination"])
            
            if strategy == "duplicate":
                # Duplicate an existing signal exactly
                sig = random.choice(original_signals)
                corrupted.append(sig)
                logger.info("Injected duplicate signal.")
                
            elif strategy == "conflict":
                # Create a signal that directly opposes an existing one
                sig = random.choice(original_signals)
                conflict = Signal(
                    entity=sig.entity,
                    action="SIG_DE_ESCALATION" if "ESCALATION" in sig.action else "SIG_MIL_ESCALATION",
                    target=sig.target,
                    intensity=sig.intensity,
                    confidence=0.4, # Adversarial noise usually has lower confidence
                    source_ref="ADVERSARIAL_INJECTION"
                )
                corrupted.append(conflict)
                logger.info(f"Injected conflicting signal to {sig.action}")
                
            elif strategy == "hallucination":
                # Totally made up signal
                hallucinated = Signal(
                    entity="XYZ",
                    action="SIG_ALIEN_INVASION",
                    target="EARTH",
                    intensity=1.0,
                    confidence=0.1,
                    source_ref="ADVERSARIAL_INJECTION"
                )
                corrupted.append(hallucinated)
                logger.info("Injected hallucinated signal.")
                
        # Shuffle to hide the injections at the end
        random.shuffle(corrupted)
        return corrupted
