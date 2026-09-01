"""
Reasoning Orchestrator
=======================
The entry point for Phase 4. Decides which experts are needed for the
investigation and initializes the debate workflow.
"""

import logging
from typing import List, Dict, Any

from dip.core.Config.config import config
from dip.telemetry.llm_tracer import tracer
from dip.pipeline.deliberation.reasoning.expert_loader import ExpertLoader, BaseExpert
from dip.pipeline.deliberation.reasoning.debate_manager import DebateManager
from dip.pipeline.deliberation.reasoning.consensus import ConsensusEngine
from dip.pipeline.deliberation.reasoning.hypothesis_generator import HypothesisGenerator
from dip.pipeline.deliberation.reasoning.counterfactual import CounterfactualEngine
from dip.pipeline.deliberation.reasoning.historical_analog import HistoricalAnalogEngine
from dip.pipeline.deliberation.reasoning.uncertainty import UncertaintyEngine
from dip.pipeline.deliberation.reasoning.reasoning_trace import ReasoningTrace

logger = logging.getLogger("Layer4.Orchestrator")


class ReasoningOrchestrator:
    """
    Determines which domain experts are required based on the investigation scope,
    runs the debate, and produces the final rigorous assessment.
    """
    def __init__(self):
        self.model = config.LLM_MODEL
        self.loader = ExpertLoader()
        self.debate_manager = DebateManager()
        self.consensus_engine = ConsensusEngine()
        self.hypothesis_gen = HypothesisGenerator()
        self.counterfactual = CounterfactualEngine()
        self.analog_engine = HistoricalAnalogEngine()
        self.uncertainty = UncertaintyEngine()
        self.trace = ReasoningTrace()

    async def determine_experts(self, topic: str, domains: List[str]) -> List[BaseExpert]:
        prompt = (
            f"Investigation Topic: {topic}\n"
            f"Domains: {', '.join(domains)}\n\n"
            "We have a library of experts: economist, geopolitics, technology, military, cyber, health, climate.\n"
            "Identify exactly 3 to 5 expert roles needed for this specific topic.\n"
            "Output ONLY a comma-separated list of the expert names (e.g., economist, geopolitics, cyber)."
        )

        try:
            response = await tracer.acompletion(
                layer="Layer4_Orchestrator",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            content = response.choices[0].message.content.strip().lower()
            expert_names = [e.strip() for e in content.split(',')]
            
            experts = self.loader.load_experts(expert_names)
            if not experts:
                logger.warning("No experts loaded. Falling back to default.")
                experts = self.loader.load_experts(["geopolitics", "economist"])
                
            return experts
            
        except Exception as e:
            logger.error(f"Failed to determine experts: {e}")
            return self.loader.load_experts(["geopolitics"])

    async def run(self, world_model, topic: str, domains: List[str], inv_id: str) -> Dict[str, Any]:
        """
        Executes the 13-step Phase 4 Pipeline.
        """
        logger.info(f"Starting Multi-Expert Reasoning for: {topic}")
        self.trace.record_step("START", {"topic": topic, "domains": domains})

        # 1. Spawn Experts
        experts = await self.determine_experts(topic, domains)
        self.trace.record_step("EXPERTS_LOADED", {"experts": [e.name for e in experts]})

        # 2. Independent Analysis (Hypothesis Generation)
        import asyncio
        tasks = [expert.analyze(world_model, topic) for expert in experts]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        raw_hypotheses = []
        for expert, result in zip(experts, task_results):
            if isinstance(result, Exception):
                logger.exception("Expert %s failed", getattr(expert, "name", expert), exc_info=result)
                continue
            raw_hypotheses.append(result)
        
        # Convert to dicts for the graph
        expert_hypotheses = [
            {
                "minister": h.minister,
                "predicted_signals": h.predicted_signals,
                "matched_signals": h.matched_signals,
                "missing_signals": h.missing_signals,
                "confidence": h.confidence,
                "rationale": h.rationale
            } for h in raw_hypotheses
        ]
        self.trace.record_step("EXPERT_HYPOTHESES", {"count": len(expert_hypotheses)})

        # 3. LangGraph Debate & Evidence Judging
        debate_result = await self.debate_manager.run_debate(topic, world_model, expert_hypotheses)
        evidence_verdicts = debate_result.get("evidence_verdicts", [])
        devils_critique = debate_result.get("devils_critique", {})
        self.trace.record_step("DEBATE_COMPLETE", {"verdicts": evidence_verdicts, "red_team": devils_critique})

        # 4. Bayesian Consensus Update
        consensus = self.consensus_engine.generate_weighted_consensus(expert_hypotheses, evidence_verdicts)
        self.trace.record_step("CONSENSUS_REACHED", consensus)

        # 5. Probabilistic Hypothesis Splitting (H1, H2, H3)
        multi_hypotheses = await self.hypothesis_gen.generate_hypotheses(
            consensus.get("consensus_hypothesis", ""), world_model, topic
        )
        self.trace.record_step("HYPOTHESES_GENERATED", {"hypotheses": multi_hypotheses})

        # 6. Historical Analogs
        analogs = await self.analog_engine.find_analogs(topic, world_model)
        self.trace.record_step("HISTORICAL_ANALOGS", {"analogs": analogs})

        # 7. Uncertainty & Sensitivity Analysis
        missing_all = []
        for h in expert_hypotheses:
            missing_all.extend(h.get("missing_signals", []))
        uncertainty = self.uncertainty.evaluate(consensus, list(set(missing_all)))
        self.trace.record_step("UNCERTAINTY_ANALYSIS", uncertainty)

        # Export trace
        trace_file = f"investigations/{inv_id}/reasoning_trace.json"
        self.trace.export_trace(trace_file)

        return {
            "consensus": consensus,
            "hypotheses": multi_hypotheses,
            "devils_advocate": devils_critique,
            "historical_analogs": analogs,
            "uncertainty": uncertainty,
            "trace_file": trace_file
        }
