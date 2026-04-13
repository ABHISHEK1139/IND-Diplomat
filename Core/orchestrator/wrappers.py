"""
Research Module Wrappers - Pipeline Integration
=================================================
Wraps research components as pipeline modules.
"""

from typing import Dict, List, Any
from core.module_base import ModuleBase, ModuleResult, ModuleStatus
from core.context import PipelineContext


class ResearchControllerModule(ModuleBase):
    """
    Pipeline wrapper for Research Controller.
    
    Execution Order: Early (before retriever)
    Priority: 5 (runs early to plan investigation)
    """
    
    def __init__(self):
        super().__init__()
        self._controller = None
    
    @property
    def name(self) -> str:
        return "research_controller"
    
    @property
    def dependencies(self) -> List[str]:
        return []  # No dependencies - runs first
    
    def _get_controller(self):
        if self._controller is None:
            from Core.orchestrator.investigation_controller import investigation_controller
            self._controller = investigation_controller
        return self._controller
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        """Analyze query and create investigation plan."""
        try:
            controller = self._get_controller()
            
            # Analyze the query
            analysis = controller.analyze_query(ctx.query)
            
            # Store analysis in context
            ctx.set("query_analysis", analysis)
            ctx.set("query_type", analysis.query_type.value)
            ctx.set("required_evidence", [e.value for e in analysis.required_evidence])
            ctx.set("knowledge_spaces", analysis.knowledge_spaces)
            ctx.set("temporal_context", analysis.temporal_context)
            ctx.set("entities", analysis.entities)
            
            # Create retrieval plan
            plan = controller.create_retrieval_plan(analysis)
            ctx.set("retrieval_plan", plan)
            
            ctx.log(f"[ResearchController] Query type: {analysis.query_type.value}")
            ctx.log(f"[ResearchController] Entities: {[e['text'] for e in analysis.entities]}")
            ctx.log(f"[ResearchController] Knowledge spaces: {analysis.knowledge_spaces}")
            
            return ModuleResult(
                status=ModuleStatus.SUCCESS,
                output={
                    "query_type": analysis.query_type.value,
                    "entities": analysis.entities,
                    "knowledge_spaces": analysis.knowledge_spaces,
                    "temporal_context": analysis.temporal_context,
                    "required_evidence_count": len(analysis.required_evidence)
                }
            )
            
        except Exception as e:
            ctx.log(f"[ResearchController] Error: {e}")
            return ModuleResult(
                status=ModuleStatus.FAILED,
                error=str(e)
            )


class InvestigationModule(ModuleBase):
    """
    Pipeline wrapper for Investigation Loop.
    
    Execution Order: After research controller, before generator
    Priority: 15 (after analysis, before generation)
    """
    
    def __init__(self):
        super().__init__()
        self._loop = None
    
    @property
    def name(self) -> str:
        return "investigator"
    
    @property
    def dependencies(self) -> List[str]:
        return ["research_controller", "retriever"]
    
    def _get_loop(self):
        if self._loop is None:
            from Core.orchestrator.investigation_controller import investigation_controller
            self._loop = investigation_controller
        return self._loop
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        """Execute investigation loop."""
        try:
            loop = self._get_loop()
            
            # Get retriever from context or import
            retriever = ctx.get("retriever")
            if not retriever:
                try:
                    from memory import get_component
                    retriever = get_component("retriever")
                except Exception:
                    retriever = None
            
            # Execute investigation
            result = await loop.investigate(
                query=ctx.query,
                retriever=retriever,
                max_rounds=3,
                context=ctx
            )
            
            # Store results in context
            ctx.set("investigation_result", result)
            ctx.set("collected_documents", result.documents)
            ctx.set("evidence_sufficiency", result.final_sufficiency)
            ctx.set("investigation_sufficient", result.is_sufficient)
            ctx.set("legal_signal_pack", result.legal_signal_pack)
            
            # Update sources
            for doc in result.documents:
                ctx.add_source(doc)
            
            ctx.log(f"[Investigation] Status: {result.status.value}")
            ctx.log(f"[Investigation] Documents: {result.total_documents}")
            ctx.log(f"[Investigation] Sufficiency: {result.final_sufficiency:.2f}")
            
            return ModuleResult(
                status=ModuleStatus.SUCCESS,
                output={
                    "status": result.status.value,
                    "documents_collected": result.total_documents,
                    "sufficiency": result.final_sufficiency,
                    "is_sufficient": result.is_sufficient,
                    "rounds": result.rounds_executed,
                    "gaps": len(result.remaining_gaps)
                }
            )
            
        except Exception as e:
            ctx.log(f"[Investigation] Error: {e}")
            return ModuleResult(
                status=ModuleStatus.FAILED,
                error=str(e)
            )


class EvidenceBinderModule(ModuleBase):
    """
    Pipeline wrapper for Evidence Binder.
    
    Execution Order: After generator, before final output
    Priority: 85 (late - checks generated answer)
    """
    
    def __init__(self):
        super().__init__()
        self._binder = None
    
    @property
    def name(self) -> str:
        return "evidence_binder"
    
    @property
    def dependencies(self) -> List[str]:
        return ["generator"]
    
    def _get_binder(self):
        if self._binder is None:
            from engine.Layer3_StateModel.evidence_binder import evidence_binder
            self._binder = evidence_binder
        return self._binder
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        """Verify and bind claims to sources."""
        try:
            binder = self._get_binder()
            
            # Get generated answer
            answer = ctx.current_answer
            if not answer:
                ctx.log("[EvidenceBinder] No answer to verify")
                return ModuleResult(
                    status=ModuleStatus.SKIPPED,
                    output={"reason": "No answer to verify"}
                )
            
            # Get sources
            sources = ctx.sources
            if not sources:
                sources = ctx.get("collected_documents", [])
            
            if not sources:
                ctx.log("[EvidenceBinder] No sources available for verification")
                return ModuleResult(
                    status=ModuleStatus.SKIPPED,
                    output={"reason": "No sources available"}
                )
            
            # Bind claims to sources
            result = binder.bind_claims_to_sources(answer, sources)
            
            # Store binding result
            ctx.set("binding_result", result)
            ctx.set("all_claims_grounded", result.all_grounded)
            
            # Enforce grounding if not all grounded
            if not result.all_grounded:
                ctx.log(f"[EvidenceBinder] {result.ungrounded_claims} claims ungrounded")
                
                # Get grounded-only version
                grounded_answer = binder.enforce_grounding(result, mode="filter")
                ctx.set("grounded_answer", grounded_answer)
                
                # Update current answer if strict mode
                if binder.strict_mode:
                    ctx.current_answer = grounded_answer
            
            # Update confidence based on grounding
            # Keep grounding as a verification metric; do not overwrite canonical confidence.
            ctx.set("grounding_score", result.grounding_score)
            
            ctx.log(f"[EvidenceBinder] Grounded: {result.grounded_claims}/{result.total_claims}")
            ctx.log(f"[EvidenceBinder] Grounding score: {result.grounding_score:.2f}")
            
            return ModuleResult(
                status=ModuleStatus.SUCCESS,
                output={
                    "total_claims": result.total_claims,
                    "grounded_claims": result.grounded_claims,
                    "ungrounded_claims": result.ungrounded_claims,
                    "grounding_score": result.grounding_score,
                    "all_grounded": result.all_grounded
                }
            )
            
        except Exception as e:
            ctx.log(f"[EvidenceBinder] Error: {e}")
            return ModuleResult(
                status=ModuleStatus.FAILED,
                error=str(e)
            )


__all__ = [
    "ResearchControllerModule",
    "InvestigationModule",
    "EvidenceBinderModule",
]
