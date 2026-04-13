"""
Investigation Loop - Iterative Retrieval Until Sufficiency
============================================================
Implements the core investigation pattern:
collect → check → refine → collect again

Key Principle:
"A real analyst workflow is iterative, not single-shot"
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from Core.case_management.case_manager import case_manager
from Core.case_management.case import CaseStatus


class InvestigationStatus(Enum):
    """Status of an investigation."""
    IN_PROGRESS = "in_progress"
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    MAX_ROUNDS_REACHED = "max_rounds_reached"
    ERROR = "error"


@dataclass
class InvestigationRound:
    """Record of a single investigation round."""
    round_number: int
    query_used: str
    documents_found: int
    sufficiency_before: float
    sufficiency_after: float
    gaps_identified: List[str]
    refinements_made: List[str]


@dataclass
class InvestigationResult:
    """Result of a complete investigation."""
    query: str
    status: InvestigationStatus
    
    # Evidence collected
    documents: List[Dict]
    total_documents: int
    
    # Sufficiency
    final_sufficiency: float
    sufficiency_threshold: float
    is_sufficient: bool
    
    # Process details
    rounds_executed: int
    max_rounds: int
    round_history: List[InvestigationRound] = field(default_factory=list)
    
    # Gaps remaining
    remaining_gaps: List[str] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    legal_signal_pack: Optional[Dict[str, Any]] = None
    case_id: Optional[str] = None


class InvestigationLoop:
    """
    Implements iterative retrieval until evidence is sufficient.
    
    This is what makes the system behave like a real analyst:
    1. Search for evidence
    2. Check if it's enough
    3. If not, refine search and try again
    4. Repeat until sufficient or max rounds
    
    Usage:
        loop = InvestigationLoop()
        
        result = await loop.investigate(
            query="What are India's obligations under RCEP?",
            retriever=my_retriever,
            max_rounds=3
        )
        
        if result.is_sufficient:
            # Proceed to generate answer
            ...
        else:
            # Handle insufficient evidence
            print(f"Gaps: {result.remaining_gaps}")
    """
    
    def __init__(
        self,
        sufficiency_threshold: float = 0.7,
        min_documents: int = 3,
        max_documents: int = 50
    ):
        self.sufficiency_threshold = sufficiency_threshold
        self.min_documents = min_documents
        self.max_documents = max_documents
        
        # Import dependencies lazily
        self._research_controller = None
        self._evidence_registry = None
    
    def _get_research_controller(self):
        """Lazy import research controller."""
        if self._research_controller is None:
            from .research_controller import research_controller
            self._research_controller = research_controller
        return self._research_controller
    
    def _get_evidence_registry(self):
        """Lazy import evidence registry."""
        if self._evidence_registry is None:
            from Core.database.evidence_registry import EvidenceRegistry
            self._evidence_registry = EvidenceRegistry()
        return self._evidence_registry
    
    async def investigate(
        self,
        query: str,
        retriever=None,
        max_rounds: int = 3,
        context=None
    ) -> InvestigationResult:
        """
        Execute complete investigation loop.
        
        Args:
            query: The question to investigate
            retriever: Retriever to use for searching
            max_rounds: Maximum retrieval iterations
            context: Optional pipeline context
            
        Returns:
            InvestigationResult with collected evidence
        """
        print(f"[InvestigationLoop] Starting investigation: {query[:50]}...")
        
        controller = self._get_research_controller()
        registry = self._get_evidence_registry()
        registry.reset()
        
        # Initial analysis
        analysis = controller.analyze_query(query)
        registry.add_requirements_from_analysis(analysis)
        case = case_manager.create_case(
            question=query,
            actors=[entity.get("normalized", "") for entity in analysis.entities if entity.get("type") == "country"],
            hypothesis=f"Initial {analysis.query_type.value} hypothesis",
            metadata={"query_type": analysis.query_type.value},
        )
        
        all_documents = []
        round_history = []
        current_round = 0
        current_sufficiency = 0.0
        status = InvestigationStatus.IN_PROGRESS
        legal_signal_pack = None
        
        while current_round < max_rounds:
            current_round += 1
            print(f"[InvestigationLoop] Round {current_round}/{max_rounds}")
            
            # Get current gaps
            sufficiency_result = registry.check_sufficiency()
            sufficiency_before = sufficiency_result.overall_score
            gaps = sufficiency_result.gaps
            
            print(f"[InvestigationLoop] Sufficiency: {sufficiency_before:.2f}")
            print(f"[InvestigationLoop] Gaps: {len(gaps)}")
            
            # Check if already sufficient
            if sufficiency_before >= self.sufficiency_threshold:
                print(f"[InvestigationLoop] Evidence sufficient!")
                status = InvestigationStatus.SUFFICIENT
                break
            
            # Create retrieval plan
            plan = controller.create_retrieval_plan(analysis)
            
            # Refine plan based on gaps if not first round
            if current_round > 1 and gaps:
                plan = self._refine_plan_for_gaps(plan, gaps)
            if case:
                case_manager.add_search_step(
                    case_id=case.case_id,
                    query=plan.search_queries[0]["query"] if plan.search_queries else query,
                    indexes=plan.query_analysis.knowledge_spaces,
                    gaps=gaps,
                )
            
            # Execute retrieval
            try:
                evidence = await controller.execute_retrieval(plan, retriever)
                new_docs = evidence.documents
                if evidence.legal_signal_pack:
                    legal_signal_pack = evidence.legal_signal_pack
                if case and evidence.evidence_ids:
                    case_manager.attach_evidence_ids(case.case_id, evidence.evidence_ids)
            except Exception as e:
                print(f"[InvestigationLoop] Retrieval error: {e}")
                new_docs = []
            
            # Register new documents
            for doc in new_docs:
                if doc not in all_documents:
                    all_documents.append(doc)
            
            registry.register_documents(new_docs)
            
            # Check new sufficiency
            new_sufficiency_result = registry.check_sufficiency()
            sufficiency_after = new_sufficiency_result.overall_score
            
            # Record round
            round_history.append(InvestigationRound(
                round_number=current_round,
                query_used=plan.search_queries[0]["query"] if plan.search_queries else query,
                documents_found=len(new_docs),
                sufficiency_before=sufficiency_before,
                sufficiency_after=sufficiency_after,
                gaps_identified=gaps,
                refinements_made=[f"Targeted search for: {g}" for g in gaps[:3]]
            ))
            if case:
                case_manager.add_analysis_round(
                    case_id=case.case_id,
                    round_number=current_round,
                    sufficiency_before=sufficiency_before,
                    sufficiency_after=sufficiency_after,
                    notes=f"Retrieved {len(new_docs)} documents",
                )
            
            current_sufficiency = sufficiency_after
            
            # Check if sufficient
            if sufficiency_after >= self.sufficiency_threshold:
                print(f"[InvestigationLoop] Evidence sufficient after round {current_round}!")
                status = InvestigationStatus.SUFFICIENT
                break
            
            # Check if making progress
            if sufficiency_after <= sufficiency_before and current_round > 1:
                print(f"[InvestigationLoop] No progress made, stopping early")
                status = InvestigationStatus.INSUFFICIENT
                break
            
            # Small delay between rounds
            await asyncio.sleep(0.1)
        
        # Final status
        if status == InvestigationStatus.IN_PROGRESS:
            if current_sufficiency >= self.sufficiency_threshold:
                status = InvestigationStatus.SUFFICIENT
            elif current_round >= max_rounds:
                status = InvestigationStatus.MAX_ROUNDS_REACHED
            else:
                status = InvestigationStatus.INSUFFICIENT
        
        # Get remaining gaps
        final_sufficiency = registry.check_sufficiency()
        remaining_gaps = final_sufficiency.gaps
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            status, remaining_gaps, all_documents
        )
        
        result = InvestigationResult(
            query=query,
            status=status,
            case_id=case.case_id if case else None,
            documents=all_documents,
            total_documents=len(all_documents),
            final_sufficiency=current_sufficiency,
            sufficiency_threshold=self.sufficiency_threshold,
            is_sufficient=status == InvestigationStatus.SUFFICIENT,
            rounds_executed=current_round,
            max_rounds=max_rounds,
            round_history=round_history,
            remaining_gaps=remaining_gaps,
            recommendations=recommendations,
            legal_signal_pack=legal_signal_pack,
        )
        if case:
            mapped_status = {
                InvestigationStatus.SUFFICIENT: CaseStatus.SUFFICIENT,
                InvestigationStatus.INSUFFICIENT: CaseStatus.INSUFFICIENT,
                InvestigationStatus.MAX_ROUNDS_REACHED: CaseStatus.INSUFFICIENT,
                InvestigationStatus.ERROR: CaseStatus.ERROR,
                InvestigationStatus.IN_PROGRESS: CaseStatus.INVESTIGATING,
            }.get(status, CaseStatus.INVESTIGATING)
            case_manager.update_case_status(
                case_id=case.case_id,
                status=mapped_status,
                confidence=current_sufficiency,
                missing_evidence=remaining_gaps,
            )
        
        # Store in context if available
        if context:
            context.set("investigation_result", result)
            context.set("collected_documents", all_documents)
        
        print(f"[InvestigationLoop] Investigation complete")
        print(f"[InvestigationLoop] Status: {status.value}")
        print(f"[InvestigationLoop] Documents: {len(all_documents)}")
        print(f"[InvestigationLoop] Sufficiency: {current_sufficiency:.2f}")
        
        return result
    
    def _refine_plan_for_gaps(self, plan, gaps: List[str]):
        """Refine retrieval plan based on identified gaps."""
        from .research_controller import RetrievalPlan
        
        new_queries = []
        
        for gap in gaps[:3]:  # Focus on top 3 gaps
            # Parse gap to determine search refinement
            gap_lower = gap.lower()
            
            if "treaty" in gap_lower or "legal" in gap_lower:
                new_queries.append({
                    "query": f"{plan.query_analysis.original_query} treaty text provisions",
                    "indexes": ["legal"],
                    "filters": {"document_type": "treaty"},
                    "priority": 1
                })
            elif "statement" in gap_lower or "official" in gap_lower:
                new_queries.append({
                    "query": f"{plan.query_analysis.original_query} official press release",
                    "indexes": ["event"],
                    "filters": {"document_type": "statement"},
                    "priority": 1
                })
            elif "statistical" in gap_lower or "data" in gap_lower:
                new_queries.append({
                    "query": f"{plan.query_analysis.original_query} statistics data figures",
                    "indexes": ["economic"],
                    "filters": {},
                    "priority": 1
                })
            else:
                # Generic refinement
                new_queries.append({
                    "query": f"{plan.query_analysis.original_query} details",
                    "indexes": plan.query_analysis.knowledge_spaces,
                    "filters": {},
                    "priority": 2
                })
        
        return RetrievalPlan(
            query_analysis=plan.query_analysis,
            search_queries=new_queries if new_queries else plan.search_queries,
            priority_order=plan.priority_order,
            max_documents=plan.max_documents,
            time_filter=plan.time_filter
        )
    
    def _generate_recommendations(
        self,
        status: InvestigationStatus,
        gaps: List[str],
        documents: List[Dict]
    ) -> List[str]:
        """Generate recommendations based on investigation outcome."""
        recommendations = []
        
        if status == InvestigationStatus.SUFFICIENT:
            recommendations.append("Evidence is sufficient - proceed to generate answer")
            if len(documents) > 10:
                recommendations.append("Consider summarizing key documents before generation")
        
        elif status == InvestigationStatus.INSUFFICIENT:
            recommendations.append("Evidence is insufficient for a reliable answer")
            for gap in gaps[:3]:
                recommendations.append(f"Seek: {gap}")
            recommendations.append("Consider asking user for more specific information")
        
        elif status == InvestigationStatus.MAX_ROUNDS_REACHED:
            recommendations.append("Maximum retrieval rounds reached")
            if gaps:
                recommendations.append(f"Still missing: {', '.join(gaps[:2])}")
            recommendations.append("Consider expanding knowledge base or refining query")
        
        return recommendations
    
    def get_investigation_summary(self, result: InvestigationResult) -> Dict[str, Any]:
        """Get a summary of the investigation."""
        return {
            "case_id": result.case_id,
            "query": result.query[:100],
            "status": result.status.value,
            "is_sufficient": result.is_sufficient,
            "documents_collected": result.total_documents,
            "sufficiency_score": result.final_sufficiency,
            "rounds_executed": result.rounds_executed,
            "remaining_gaps": len(result.remaining_gaps),
            "recommendations": result.recommendations[:3]
        }


# Singleton instance
investigation_loop = InvestigationLoop()


__all__ = [
    "InvestigationLoop",
    "investigation_loop",
    "InvestigationResult",
    "InvestigationRound",
    "InvestigationStatus",
]
