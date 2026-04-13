"""
Module Wrappers - Wrap existing components with ModuleBase interface.
This makes all existing agents/memory/utils compatible with the new pipeline.
"""

import logging
import re

from Core.module_base import ModuleBase, ModuleResult, ModuleStatus
from Core.context import PipelineContext
from typing import Any, Dict, List


logger = logging.getLogger("core.wrappers")


# ============== DOSSIER MODULE ==============

class DossierModule(ModuleBase):
    """Loads structured dossiers as deterministic ground truth."""

    def __init__(self):
        super().__init__()
        self._store = None

    @property
    def name(self) -> str:
        return "dossier"

    @property
    def dependencies(self) -> List[str]:
        return []  # should run first

    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        if self._store is None:
            from dossiers import dossier_store
            self._store = dossier_store

        matches = self._store.match_query(ctx.query)
        if not matches:
            return ModuleResult(status=ModuleStatus.SKIPPED, metadata={"reason": "no_match"})

        sources = self._store.as_sources(matches)
        ctx.set("dossier_hits", sources)
        # prepend dossier sources to global sources so generator can cite them
        ctx.sources = sources + ctx.sources

        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"dossiers": len(matches)},
            metadata={"entities": [m[0] for m in matches]},
        )


# ============== RETRIEVAL MODULE ==============

class RetrievalModule(ModuleBase):
    """Wraps memory.retriever.DiplomaticRetriever."""
    
    def __init__(self):
        super().__init__()
        self._retriever = None
    
    @property
    def name(self) -> str:
        return "retriever"
    
    @property
    def dependencies(self) -> List[str]:
        # Keep retrieval available even when planning/index modules are absent.
        return []

    @property
    def optional_dependencies(self) -> List[str]:
        return ["research_controller", "multi_index"]
    
    def _ensure_retriever(self):
        if self._retriever is None:
            from memory.retriever import DiplomaticRetriever
            self._retriever = DiplomaticRetriever()
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        self._ensure_retriever()
        
        # Check for cross-module call query override
        query = ctx.get("_call_query", ctx.query)
        
        docs = self._retriever.hybrid_search(query)

        # Add dossier facts if already found
        dossier_docs = ctx.get("dossier_hits", [])
        if dossier_docs:
            docs = dossier_docs + docs
        
        ctx.sources = docs
        ctx.set("retrieved_docs", docs)
        ctx.set("retrieval_scores", [d.get("score", 0.5) for d in docs])
        
        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"doc_count": len(docs)},
            metadata={"top_score": docs[0].get("score", 0) if docs else 0}
        )


# ============== SAFETY MODULE ==============

class SafetyModule(ModuleBase):
    """Wraps agents.guard.llama_guard for input/output safety."""
    
    def __init__(self):
        super().__init__()
        self._guard = None
    
    @property
    def name(self) -> str:
        return "safety"
    
    @property
    def dependencies(self) -> List[str]:
        return []  # Early in pipeline
    
    def _ensure_guard(self):
        if self._guard is None:
            from agents.guard import llama_guard
            self._guard = llama_guard
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        if not ctx.get_flag("enable_safety"):
            return ModuleResult(status=ModuleStatus.SKIPPED)
        
        self._ensure_guard()
        
        # Input safety check
        result = await self._guard.check(ctx.query)
        is_safe = result.get("safe", True)
        
        ctx.set("input_safe", is_safe)
        
        if not is_safe:
            ctx.current_answer = "Query blocked by safety filter."
            return ModuleResult(
                status=ModuleStatus.SUCCESS,
                output={"blocked": True},
                metadata={"reason": result.get("category", "unknown")}
            )
        
        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"safe": True}
        )


# ============== CRAG MODULE ==============

class CRAGModule(ModuleBase):
    """Wraps agents.crag.crag_engine for retrieval correction."""
    
    def __init__(self):
        super().__init__()
        self._crag = None
    
    @property
    def name(self) -> str:
        return "crag"
    
    @property
    def dependencies(self) -> List[str]:
        return ["retriever"]
    
    def _ensure_crag(self):
        if self._crag is None:
            from agents.crag import crag_engine
            self._crag = crag_engine
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        if not ctx.get_flag("enable_crag"):
            return ModuleResult(status=ModuleStatus.SKIPPED)
        
        self._ensure_crag()
        
        docs = ctx.get("retrieved_docs", [])
        
        result = await self._crag.evaluate_and_correct(
            ctx.query, docs, context={"user_id": ctx.user_id}
        )
        
        if result.refined_docs:
            ctx.sources = result.refined_docs
            ctx.set("retrieved_docs", result.refined_docs)
        
        # Keep retrieval-quality confidence separate from canonical analysis confidence.
        ctx.set("crag_confidence_before", result.confidence_before)
        ctx.set("crag_confidence_after", result.confidence_after)
        ctx.set("crag_action", result.action_taken.value)
        
        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"action": result.action_taken.value},
            metadata={"confidence_before": result.confidence_before, "confidence_after": result.confidence_after}
        )


# ============== CONFIDENCE LEDGER MODULE ==============

class ConfidenceLedgerModule(ModuleBase):
    """Scores sources for reliability and sets a confidence ledger."""

    def __init__(self):
        super().__init__()
        self._scorer = None

    @property
    def name(self) -> str:
        return "confidence_ledger"

    @property
    def dependencies(self) -> List[str]:
        return ["retriever"]

    @property
    def optional_dependencies(self) -> List[str]:
        return ["crag", "dossier", "temporal"]

    def _ensure(self):
        if self._scorer is None:
            from utils.reliability import ReliabilityScorer
            self._scorer = ReliabilityScorer()

    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        if not ctx.get_flag("enable_confidence_ledger"):
            return ModuleResult(status=ModuleStatus.SKIPPED)

        self._ensure()
        sources = ctx.get("retrieved_docs", []) + ctx.get("dossier_hits", [])
        ledger, aggregate = self._scorer.score_sources(sources, ctx.query)
        ctx.set("confidence_ledger", ledger)
        ctx.set_analysis_confidence(
            aggregate,
            source="layer3_confidence_ledger",
            components={
                "sources_scored": len(ledger),
                "method": "reliability_recency_retrieval_weighted",
            },
        )

        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"sources_scored": len(ledger)},
            metadata={"aggregate_confidence": aggregate},
        )


# ============== TEMPORAL BRIEFING MODULE ==============

class TemporalBriefingModule(ModuleBase):
    """Adds temporal annotations and a briefing timeline."""

    def __init__(self):
        super().__init__()
        self._tm = None

    @property
    def name(self) -> str:
        return "temporal_briefing"

    @property
    def dependencies(self) -> List[str]:
        return ["retriever"]

    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        if not ctx.get_flag("enable_temporal_briefing"):
            return ModuleResult(status=ModuleStatus.SKIPPED)

        if self._tm is None:
            from temporal import get_timeline_manager
            self._tm = get_timeline_manager()

        enhanced_query, enhanced_sources = self._tm.add_temporal_context(
            ctx.query, ctx.get("retrieved_docs", [])
        )
        ctx.set("temporal_briefing", {"query": enhanced_query, "sources": enhanced_sources})
        ctx.set("temporal_query", enhanced_query)
        ctx.set("retrieved_docs", enhanced_sources)
        ctx.sources = enhanced_sources

        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"briefed_sources": len(enhanced_sources)}
        )


# ============== GENERATION MODULE ==============

class GenerationModule(ModuleBase):
    """Wraps agents.llm_client for response generation."""
    
    def __init__(self):
        super().__init__()
        self._llm = None
    
    @property
    def name(self) -> str:
        return "generator"
    
    @property
    def dependencies(self) -> List[str]:
        return ["retriever"]
    
    @property
    def optional_dependencies(self) -> List[str]:
        return ["investigator", "crag", "mcts", "causal", "temporal_briefing"]  # evidence_binder runs AFTER generator
    
    def _ensure_llm(self):
        if self._llm is None:
            from agents.llm_client import llm_client
            self._llm = llm_client

    @staticmethod
    def _select_prompt_docs(docs: List[Dict[str, Any]], max_docs: int = 10) -> List[Dict[str, Any]]:
        decorated = []
        for idx, doc in enumerate(docs):
            score = None
            if isinstance(doc, dict):
                try:
                    score = float(doc.get("score"))
                except Exception:
                    score = None
            decorated.append((score, idx, doc))

        if any(score is not None for score, _, _ in decorated):
            decorated.sort(key=lambda item: (item[0] is None, -(item[0] or 0.0), item[1]))
            return [doc for _, _, doc in decorated[:max_docs]]

        return [doc for _, _, doc in decorated[:max_docs]]

    def _build_runtime_gate(self, ctx: PipelineContext) -> Dict[str, Any]:
        """
        Enforce Layer-4 runtime policy before any LLM call:
        1) question scope must be allowed
        2) analysis readiness must be true
        """
        from engine.Layer3_StateModel.analysis_readiness import evaluate_analysis_readiness
        from engine.Layer4_Analysis.intake.question_scope_checker import check_question_scope

        scope_report = check_question_scope(ctx.query)
        confidence_contract = ctx.get_analysis_confidence()
        confidence_score = float(confidence_contract.get("score", ctx.confidence))

        docs = ctx.get("collected_documents") or ctx.get("retrieved_docs") or []
        if not isinstance(docs, list):
            docs = []

        legal_pack = ctx.get("legal_signal_pack") or {}
        recent_activity_signals = 0
        if isinstance(legal_pack, dict):
            try:
                recent_activity_signals = max(0, int(legal_pack.get("signal_count", 0)))
            except Exception:
                recent_activity_signals = 0
        if recent_activity_signals == 0:
            recent_activity_signals = len(docs)

        # Readiness contract expects Layer-3 style state vectors.
        country_state = {
            "recent_activity_signals": recent_activity_signals,
            "signal_breakdown": {
                "validation_confidence": {
                    "overall_score": confidence_score,
                }
            },
        }
        relationship_state = {
            "observation_count": len(docs),
            "supporting_evidence": docs,
        }
        readiness_report = evaluate_analysis_readiness(
            country_state=country_state,
            relationship_state=relationship_state,
            confidence=confidence_score,
        )

        blockers: List[str] = []
        if not scope_report.allowed:
            blockers.append(scope_report.reason)
        blockers.extend(readiness_report.blockers)

        return {
            "allowed": bool(scope_report.allowed and readiness_report.ready),
            "scope": scope_report.to_dict(),
            "readiness": readiness_report.to_dict(),
            "reason": "; ".join(blockers).strip(),
        }
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        gate = self._build_runtime_gate(ctx)
        ctx.set("layer4_gate", gate)
        ctx.set("layer4_scope", gate.get("scope"))
        ctx.set("layer4_readiness", gate.get("readiness"))

        if not gate.get("allowed", False):
            reason = gate.get("reason") or "Layer-4 runtime guard blocked this query."
            ctx.current_answer = (
                "Analysis deferred by Layer-4 runtime guard. "
                f"{reason}"
            )
            ctx.set("refused", True)
            ctx.set("refusal_reason", "layer4_runtime_guard")
            return ModuleResult(
                status=ModuleStatus.SKIPPED,
                output={"blocked": True},
                metadata={"layer4_gate": gate},
            )

        self._ensure_llm()

        query_text = str(ctx.get("temporal_query") or ctx.query)
        docs = ctx.get("retrieved_docs", [])
        selected_docs = self._select_prompt_docs(docs, max_docs=10)
        
        # Build context
        context_text = "\n\n".join([
            f"Source: {d.get('metadata', {}).get('source', 'Unknown')}\n{d.get('content', '')}"
            for d in selected_docs
            if isinstance(d, dict)
        ])
        
        # Add causal analysis if available
        causal = ctx.get("causal_analysis")
        if causal:
            context_text += f"\n\nCausal Analysis:\n{causal}"
        
        prompt = f"""Based on the following sources, answer the question.

    Sources:
    {context_text}

    Question: {query_text}

    Answer:"""
        
        answer = await self._llm.generate(
            prompt,
            system_prompt="You are a diplomatic intelligence analyst.",
            query_type="factual"
        )
        
        ctx.current_answer = answer
        
        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"answer_length": len(answer)}
        )


# ============== CoVe MODULE ==============

class CoVeModule(ModuleBase):
    """Wraps agents.cove.cove_verifier for answer verification."""
    
    def __init__(self):
        super().__init__()
        self._cove = None
    
    @property
    def name(self) -> str:
        return "cove"
    
    @property
    def dependencies(self) -> List[str]:
        return ["generator"]
    
    def _ensure_cove(self):
        if self._cove is None:
            from agents.cove import cove_verifier
            self._cove = cove_verifier
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        if not ctx.get_flag("enable_cove"):
            return ModuleResult(status=ModuleStatus.SKIPPED)
        
        self._ensure_cove()
        
        docs = ctx.get("retrieved_docs", [])
        
        result = await self._cove.run_cove_loop(
            ctx.query, ctx.current_answer, docs
        )
        
        ctx.set("cove_faithfulness_score", result.faithfulness_score)
        ctx.set("cove_verified", result.state.value == "accepted")
        ctx.set("cove_revisions", result.revisions_made)
        
        if result.final_answer:
            ctx.current_answer = result.final_answer
        
        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"verified": result.state.value == "accepted", "revisions": result.revisions_made},
            metadata={"faithfulness": result.faithfulness_score}
        )


# ============== RED TEAM MODULE ==============

class RedTeamModule(ModuleBase):
    """Wraps agents.red_team.RedTeamAgent for adversarial testing."""
    
    def __init__(self):
        super().__init__()
        self._red_team = None
    
    @property
    def name(self) -> str:
        return "red_team"
    
    @property
    def dependencies(self) -> List[str]:
        return ["generator"]
    
    @property
    def optional_dependencies(self) -> List[str]:
        return ["cove"]
    
    def _ensure_red_team(self):
        if self._red_team is None:
            from agents.red_team import RedTeamAgent
            self._red_team = RedTeamAgent()
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        if not ctx.get_flag("enable_red_team"):
            return ModuleResult(status=ModuleStatus.SKIPPED)
        
        self._ensure_red_team()
        
        is_robust, critique, counter_evidence = await self._red_team.execute_attack(
            ctx.current_answer
        )
        
        ctx.set("red_team_passed", is_robust)
        ctx.set("red_team_critique", critique if not is_robust else None)
        
        if not is_robust:
            # Refine answer
            refined = await self._red_team.refine_answer_with_critique(
                ctx.current_answer, critique, counter_evidence
            )
            ctx.current_answer = refined
        
        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"robust": is_robust},
            metadata={"critique": critique if not is_robust else None}
        )


# ============== MCTS MODULE ==============

class MCTSModule(ModuleBase):
    """Wraps agents.mcts.MCTSRAGAgent for complex reasoning."""
    
    def __init__(self):
        super().__init__()
        self._mcts = None
    
    @property
    def name(self) -> str:
        return "mcts"
    
    @property
    def dependencies(self) -> List[str]:
        return ["retriever"]
    
    def _ensure_mcts(self):
        if self._mcts is None:
            from agents.mcts import MCTSRAGAgent
            self._mcts = MCTSRAGAgent()
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        if not ctx.get_flag("enable_mcts"):
            return ModuleResult(status=ModuleStatus.SKIPPED)
        
        self._ensure_mcts()
        
        # MCTS returns best reasoning path
        path = self._mcts.search(ctx.query)
        
        ctx.set("mcts_path", path)
        
        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"path_length": len(path) if path else 0}
        )


# ============== CAUSAL MODULE ==============

class CausalModule(ModuleBase):
    """Wraps agents.causal.CausalInferenceEngine for causal analysis."""
    
    def __init__(self):
        super().__init__()
        self._causal = None
    
    @property
    def name(self) -> str:
        return "causal"
    
    @property
    def dependencies(self) -> List[str]:
        return ["retriever"]
    
    def _ensure_causal(self):
        if self._causal is None:
            from agents.causal import CausalInferenceEngine
            self._causal = CausalInferenceEngine()

    @staticmethod
    def _looks_causal(query: str) -> bool:
        query_lower = str(query or "").strip().lower()
        patterns = [
            r"\bwhat if\b",
            r"\bimpact\b",
            r"\bscenario\b",
            r"\bcounterfactual\b",
            r"\bif\b.+\bthen\b",
        ]
        return any(re.search(pattern, query_lower) for pattern in patterns)
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        if not ctx.get_flag("enable_causal"):
            if not self._looks_causal(ctx.query):
                return ModuleResult(status=ModuleStatus.SKIPPED)
        
        self._ensure_causal()
        
        analysis = await self._causal.analyze_causality(ctx.query)
        
        ctx.set("causal_analysis", analysis)
        
        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"has_analysis": analysis is not None}
        )


# ============== SCENARIO PLAYBOOK MODULE ==============

class ScenarioPlaybookModule(ModuleBase):
    """Provides structured scenario templates and mitigations."""

    def __init__(self):
        super().__init__()
        self._playbooks = None

    @property
    def name(self) -> str:
        return "scenario_playbook"

    @property
    def dependencies(self) -> List[str]:
        return ["generator"]

    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        if not ctx.get_flag("enable_scenarios"):
            return ModuleResult(status=ModuleStatus.SKIPPED)

        if self._playbooks is None:
            from simulation.playbooks import playbook_store
            self._playbooks = playbook_store

        matched = self._playbooks.match(ctx.query)
        if not matched:
            return ModuleResult(status=ModuleStatus.SKIPPED, metadata={"reason": "no_playbook"})

        scenario = self._playbooks.build_response(matched, ctx.current_answer)
        ctx.set("scenario_playbook", scenario)

        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"scenarios": len(matched)},
            metadata={"matched": matched}
        )


# ============== REFUSAL MODULE ==============

class RefusalModule(ModuleBase):
    """Wraps logic.refusal_engine for uncertainty handling."""
    
    def __init__(self):
        super().__init__()
        self._refusal = None
    
    @property
    def name(self) -> str:
        return "refusal"
    
    @property
    def dependencies(self) -> List[str]:
        return ["generator"]
    
    @property
    def optional_dependencies(self) -> List[str]:
        return ["cove"]
    
    def _ensure_refusal(self):
        if self._refusal is None:
            from logic.refusal_engine import refusal_engine
            self._refusal = refusal_engine
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        self._ensure_refusal()
        
        docs = ctx.get("retrieved_docs", [])
        retrieval_scores = ctx.get("retrieval_scores", [0.5])
        faithfulness_score = float(
            ctx.get("cove_faithfulness_score", ctx.get_analysis_confidence().get("score", ctx.confidence))
        )
        
        assessment = self._refusal.assess_confidence(
            query=ctx.query,
            sources=docs,
            answer=ctx.current_answer,
            retrieval_scores=retrieval_scores,
            faithfulness_score=faithfulness_score
        )
        
        refused = assessment.should_refuse()
        ctx.set("refused", refused)
        
        if refused:
            formatted = self._refusal.format_response(assessment, ctx.current_answer)
            ctx.current_answer = formatted.get("answer") or formatted.get("message", str(formatted))
            ctx.set("refusal_reason", assessment.refusal_reason.value if assessment.refusal_reason else "low_confidence")
        
        return ModuleResult(
            status=ModuleStatus.SUCCESS,
            output={"refused": refused}
        )


# ============== REGISTER ALL MODULES ==============

def register_all_modules():
    """Register all module wrappers with the registry."""
    from Core.registry import registry
    
    modules = [
        DossierModule(),
        RetrievalModule(),
        SafetyModule(),
        CRAGModule(),
        ConfidenceLedgerModule(),
        TemporalBriefingModule(),
        MCTSModule(),
        CausalModule(),
        GenerationModule(),
        CoVeModule(),
        RefusalModule(),
        RedTeamModule(),
        ScenarioPlaybookModule(),
    ]
    
    for module in modules:
        registry.register(module)
    
    logger.info("[Modules] Registered %d modules", len(modules))
    return modules
