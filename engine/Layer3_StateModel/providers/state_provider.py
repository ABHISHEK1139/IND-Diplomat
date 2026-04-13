
import logging
from typing import Optional, List, Dict, Any

from engine.Layer3_StateModel.construction.country_state_builder import CountryStateBuilder
from engine.Layer2_Knowledge.retriever import DiplomaticRetriever
from engine.Layer3_StateModel.schemas.state_context import (
    StateContext, ActorsContext, MilitaryContext, DiplomaticContext, 
    EconomicContext, DomesticContext, CapabilityIndicators, MetaContext, EvidenceContext
)

logger = logging.getLogger(__name__)

class StateProvider:
    """
    Unified Intelligence Interface (The Query Router).
    Routes requests between Structured Providers (SQL/APIs) and Unstructured Knowledge (RAG).
    Constructs the final StateContext for the Deliberative Engine.
    """
    
    def __init__(self):
        self.builder = CountryStateBuilder()
        self.retriever = DiplomaticRetriever()

    def get_state_context(self, 
                          subject_country: str, 
                          target_country: str = None, 
                          date: str = None,
                          force_rag: bool = False) -> StateContext:
        """
        Builds the full StateContext, intelligently routing queries for enriched context.
        """
        if not target_country:
            # Default to primary adversary or neighbor if not specified (Logic could be expanded)
            target_country = "OPFOR" 

        # 1. Fetch Structured Signals (Layer 3)
        # This uses the specific providers (SIPRI, GDELT, etc.)
        vector = self.builder.build(subject_country, date)
        
        # 2. Map Structured Data to Context Schema
        # (Translating CountryStateVector -> StateContext)
        # Note: Vector has normalized scores (0-1). Context expects normalized scores.
        
        military_ctx = MilitaryContext(
            mobilization_level=vector.military_pressure.value,
            clash_history=1 if vector.conflict_activity.value > 0.5 else 0, # Simplified
            exercises=0 # Not in vector explicit
        )
        
        dip_ctx = DiplomaticContext(
            hostility_tone=vector.diplomatic_isolation.value,
            negotiations=0.5, # Default
            alliances=0.5     # Default
        )
        
        econ_ctx = EconomicContext(
            sanctions=vector.economic_stress.value, # Proxy
            trade_dependency=0.5,
            economic_pressure=vector.economic_stress.value
        )
        
        dom_ctx = DomesticContext(
            regime_stability=vector.internal_stability.value if vector.internal_stability else 0.5,
            unrest=1.0 - (vector.internal_stability.value if vector.internal_stability else 0.5),
            protests=0.0
        )
        
        meta_ctx = MetaContext(
            data_confidence=0.8, # Placeholder
            time_recency=1.0,
            # Fix 6: Use evidence_log_size as source_count (tracks actual
            # unique observations, not just recent_activity_signals)
            source_count=max(
                int(vector.recent_activity_signals or 0),
                len(getattr(vector, 'observations', []) or []),
                20,  # floor: GDELT sensor typically provides 15-25 articles
            )
        )
        
        # 3. Intelligent Query Routing (Layer 2 Integration)
        # If signals are alarming (High Threat) or RAG is forced, consult the Knowledge Base.
        rag_docs = []
        rag_reasoning = ""
        
        high_tension = vector.tension_index > 0.6
        
        if force_rag or high_tension:
            logger.info(f"[QueryRouter] Triggering RAG lookup for {subject_country} (Tension: {vector.tension_index:.2f})")
            
            # Construct a natural language query based on the active signals
            query_focus = []
            if vector.military_pressure.value > 0.5: query_focus.append("military movements")
            if vector.economic_stress.value > 0.5: query_focus.append("sanctions and trade blocks")
            if vector.diplomatic_isolation.value > 0.5: query_focus.append("diplomatic statements")
            
            topic = " and ".join(query_focus) or "general situation"
            query = f"What is the {topic} regarding {subject_country} around {vector.date}?"
            
            # Use Retriever
            results = self.retriever.hybrid_search(query, top_k=5)
            rag_docs = [r["content"] for r in results]
            rag_reasoning = f"Retrieved {len(rag_docs)} documents focused on {topic}."
            
        evidence = EvidenceContext(
            rag_documents=rag_docs,
            rag_reasoning=rag_reasoning
        )

        return StateContext(
            actors=ActorsContext(subject_country=subject_country, target_country=target_country),
            military=military_ctx,
            diplomatic=dip_ctx,
            economic=econ_ctx,
            domestic=dom_ctx,
            capability=CapabilityIndicators(), # Default empty
            meta=meta_ctx,
            evidence=evidence
        )
