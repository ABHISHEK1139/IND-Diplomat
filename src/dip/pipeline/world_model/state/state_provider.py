"""
State Provider (Layer 3)
========================
Aggregates Layer 1 data, extracts Layer 2 knowledge, and computes the Layer 3 State Context.
"""

import logging
from typing import List, Any
from dip.core.schema import StateContext, InvestigationGoal
import asyncio

logger = logging.getLogger("Layer3.state_provider")


class StateProvider:
    def __init__(self):
        from dip.pipeline.collection.feed_integrator import FeedIntegrator
        from dip.pipeline.knowledge.signal_extractor import SignalExtractor
        self.integrator = FeedIntegrator()
        self.extractor = SignalExtractor()

    async def build_state_context(self, country: str, query: str) -> StateContext:
        """Builds the comprehensive StateContext."""
        logger.info(f"Building state context for {country}")

        # 1. Gather Raw Observations (Layer 1)
        goal = InvestigationGoal(
            target_country=country,
            topic=query,
            domains=["Military", "Economic", "Political", "Diplomatic", "Cyber"],
            time_horizon="1 Year",
            investigation_goal="Determine state context"
        )
        raw_observations = await self.integrator.fetch_all(goal)
        
        # 2. Extract Signals (Layer 2)
        extraction_result = await self.extractor.extract(raw_observations)
        signals = extraction_result.get("signals", []) if isinstance(extraction_result, dict) else extraction_result
        if not signals and query and query.strip():
            query_signals = await self.extractor.extract_signals(query)
            if query_signals:
                signals = query_signals
                if not raw_observations:
                    from datetime import datetime, timezone
                    from dip.core.schema import RawObservation
                    raw_observations = [RawObservation(source_id="query-seed", content=query, source_type="OSINT", timestamp=datetime.now(timezone.utc).isoformat())]
        
        return self.build_state(country, raw_observations, signals)
        
    def build_state(self, country: str, observations: List[Any], signals: List[Any]) -> StateContext:
        """Builds the StateContext from pre-collected observations and signals (DIP 3.0 flow)."""
        logger.info(f"Building state context for {country} (DIP 3.0)")
        context = StateContext(country=country)
        
        context.observation_count = len(observations)
        context.current_signals = signals
        
        # 3. Accumulate Beliefs (Layer 3)
        try:
            from dip.pipeline.world_model.state.belief_accumulator import evaluate
            context.beliefs = evaluate(signals)
        except Exception as e:
            logger.exception("Belief accumulation failed:")

        # 4. Temporal Memory
        try:
            from dip.pipeline.world_model.state.temporal_memory import record_snapshot, compute_trends
            if context.beliefs:
                record_snapshot(context.beliefs)
                
            for b in context.beliefs:
                trend = compute_trends(b.signal_code, b.support_score)
                context.temporal_indicators.append(trend)
        except Exception as e:
            logger.exception("Temporal memory failed:")

        # 5. Conflict State
        try:
            from dip.pipeline.world_model.state.conflict_state_model import compute_domain_indices, compute_escalation
            if context.beliefs:
                domains = compute_domain_indices(context.beliefs, context.current_signals)
                escalation = compute_escalation(domains, context.temporal_indicators, context.beliefs)
                context.escalation = escalation
        except Exception as e:
            logger.exception("Conflict state model failed:")

        return context
