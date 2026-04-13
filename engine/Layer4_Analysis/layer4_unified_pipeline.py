"""
Layer-4 Unified Execution Pipeline

The complete reasoning pipeline in strict sequence:

1. Create CouncilSession (shared memory)
2. CONVENE_COUNCIL - Ministers propose hypotheses
3. DETECT_CONFLICTS - Check disagreement
4. RED_TEAM - Challenge if conflicts/low confidence
5. INVESTIGATE (CRAG) - Collect missing signals (can be recursive)
6. SYNTHESIZE - Aggregate to threat level
7. VERIFY (CoVe) - Check atomic claims
8. REFUSE? - If verification < 0.7, refuse
9. HITL? - If high threat + low verification, escalate
10. REPORT - Format final output

All modules access ONLY through CouncilSession.
No direct module-to-module calls.
No document reading (only StateContext signals).
"""

import uuid
from typing import Dict, Any, Optional
from dataclasses import asdict

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.council_session import CouncilSession, SessionStatus
from engine.Layer4_Analysis.coordinator import CouncilCoordinator
from engine.Layer4_Analysis.schema import ThreatLevel


class Layer4UnifiedPipeline:
    """
    The complete Layer-4 reasoning execution engine.
    
    Entry point: execute(query, state_context, **flags)
    
    Output: structured result with decision and metadata
    """
    
    def __init__(self):
        self.coordinator = CouncilCoordinator()
    
    async def execute(
        self,
        query: str,
        state_context: StateContext,
        user_id: Optional[str] = None,
        enable_red_team: bool = True,
        max_investigation_loops: int = 1,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the complete Layer-4 pipeline with comprehensive error handling.
        
        Args:
            query: The question/analysis request
            state_context: Fully hydrated StateContext from Layer-3
            enable_red_team: Whether to activate red team challenges
            max_investigation_loops: Max iterations for CRAG
        
        Returns:
            Structured result with answer, confidence, metadata
        """
        session_id = f"l4_exec_{uuid.uuid4().hex[:10]}"
        
        try:
            # Input validation
            if not query or not isinstance(query, str):
                raise ValueError("query must be a non-empty string")
            if not state_context:
                raise ValueError("state_context is required")
            
            # Create shared session object
            session = CouncilSession(
                session_id=session_id,
                question=query,
                state_context=state_context
            )
            
            print(f"\n[Layer-4] Starting unified pipeline: {session_id}")
            print(f"[Layer-4] Query: {query}")
            
            # Execute through coordinator which orchestrates all stages
            result = await self.coordinator.process_query(
                query=query,
                state_context=state_context,
                use_red_team=enable_red_team,
                max_investigation_loops=max_investigation_loops
            )
            
            print(f"[Layer-4] Pipeline complete. Decision: {result.get('council_session', {}).get('status')}")
            
            return result
            
        except ValueError as e:
            print(f"[ERROR] Input validation failed: {e}")
            return {
                "answer": f"Pipeline failed: {str(e)}",
                "sources": [],
                "confidence": 0.0,
                "council_session": {
                    "session_id": session_id,
                    "status": SessionStatus.FAILED.name,
                    "error": str(e)
                }
            }
        except RuntimeError as e:
            print(f"[ERROR] Async runtime error: {e}")
            return {
                "answer": "Pipeline failed due to async execution error. Please try again.",
                "sources": [],
                "confidence": 0.0,
                "council_session": {
                    "session_id": session_id,
                    "status": SessionStatus.FAILED.name,
                    "error": f"Async error: {str(e)}"
                }
            }
        except Exception as e:
            print(f"[CRITICAL ERROR] Unexpected error in Layer-4 pipeline: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "answer": "Pipeline failed due to unexpected system error. Please try again.",
                "sources": [],
                "confidence": 0.0,
                "council_session": {
                    "session_id": session_id,
                    "status": SessionStatus.FAILED.name,
                    "error": f"Unexpected error: {type(e).__name__}: {str(e)}"
                }
            }
    
    def get_status(self, session_id: str) -> Dict[str, Any]:
        """Query status of a running or completed session."""
        # Would connect to a session store
        return {"status": "not_implemented"}


class Layer4PipelineFactory:
    """Factory for creating and managing Layer-4 pipeline instances."""
    
    _instance: Optional[Layer4UnifiedPipeline] = None
    
    @classmethod
    def get_pipeline(cls) -> Layer4UnifiedPipeline:
        """Get or create singleton pipeline."""
        if cls._instance is None:
            cls._instance = Layer4UnifiedPipeline()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset the singleton (for testing)."""
        cls._instance = None


# Convenience function for direct execution
async def run_layer4_analysis(
    query: str,
    state_context: StateContext,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience entry point for Layer-4 analysis.
    
    Usage:
        result = await run_layer4_analysis(query, state_context)
    """
    pipeline = Layer4PipelineFactory.get_pipeline()
    return await pipeline.execute(query, state_context, **kwargs)
