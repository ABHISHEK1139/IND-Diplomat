"""
NextGen: Experiment Gate (Neuro-Symbolic Fusion)
================================================
Enforces the hand-in-glove execution of Symbolic Heuristics and LLM Reasoning.
The LLM is NOT a fallback, nor is it an A/B test. The heuristic provides the 
ground truth bounds (the guardrails), and the LLM provides the nuanced narrative 
and qualitative assessment within those bounds.
"""

from typing import Dict, Any, Callable, Optional
import logging
from dip.core.schema import NextGenSREOutput

logger = logging.getLogger("NextGen.experiment_gate")

class ExperimentGate:
    """
    Gates the interaction between deterministic pipelines (SRE) and 
    probabilistic ones (LLM Ministers), ensuring they fuse rather than fork.
    """
    
    def fuse_assessment(
        self, 
        heuristic_output: NextGenSREOutput, 
        llm_deliberation: Callable[..., Dict[str, Any]], 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fuses the symbolic SRE output with the LLM deliberation.
        The LLM is explicitly constrained to operate within the risk bands
        defined by the heuristic.
        """
        # Extract the strict bounds from the heuristic
        max_risk = heuristic_output.system_escalation_index
        allowed_bands = [heuristic_output.risk_band]
        
        # Inject the heuristic bounds into the LLM kwargs so it is aware of the ceiling
        fusion_kwargs = kwargs.copy()
        fusion_kwargs["system_escalation_index"] = max_risk
        fusion_kwargs["enforced_risk_band"] = allowed_bands[0]
        
        # Execute the LLM deliberation (this function calls the LLM, but now it has strict context)
        try:
            llm_result = llm_deliberation(**fusion_kwargs)
        except Exception as e:
            logger.error(f"LLM Deliberation failed in FusionGate: {e}")
            # The system must not fail. If LLM fails, we fall back to raw heuristic dict.
            # (Note: This is a system reliability fallback, not an architectural 'fallback')
            return self._heuristic_to_dict(heuristic_output)
            
        # Fusion Validation: Enforce that the LLM did not violate the heuristic bounds
        fused_result = self._enforce_bounds(heuristic_output, llm_result)
        return fused_result
        
    def _enforce_bounds(self, heuristic: NextGenSREOutput, llm_output: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures the LLM did not hallucinate a threat level outside the heuristic."""
        fused = llm_output.copy()
        
        llm_threat = str(fused.get("threat_level", "")).upper()
        heuristic_threat = heuristic.risk_band.upper()
        
        # If the LLM deviated from the heuristic risk band, we force the heuristic ground truth
        if llm_threat != heuristic_threat and llm_threat != "":
            logger.warning(f"FusionGate override: LLM suggested {llm_threat}, forcing heuristic {heuristic_threat}")
            fused["threat_level"] = heuristic_threat
            fused["neuro_symbolic_override"] = True
            
        # Ensure base heuristic data is merged in
        fused["system_escalation_index"] = heuristic.system_escalation_index
        
        return fused

    def _heuristic_to_dict(self, heuristic: NextGenSREOutput) -> Dict[str, Any]:
        return {
            "threat_level": heuristic.risk_band,
            "system_escalation_index": heuristic.system_escalation_index,
            "neuro_symbolic_override": True,
            "fusion_status": "LLM_FAILED_HEURISTIC_PRESERVED"
        }
