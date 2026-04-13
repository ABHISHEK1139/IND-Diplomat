"""
Knowledge Module Wrappers - Pipeline Integration
=================================================
Wraps knowledge components as pipeline modules.
"""

from typing import Dict, List, Any
from core.module_base import ModuleBase, ModuleResult, ModuleStatus
from core.context import PipelineContext


class MultiIndexModule(ModuleBase):
    """
    Pipeline wrapper for Multi-Index Manager.
    
    Execution Order: With retriever
    Priority: 10 (early, configures knowledge spaces)
    """
    
    def __init__(self):
        super().__init__()
        self._manager = None
    
    @property
    def name(self) -> str:
        return "multi_index"
    
    @property
    def dependencies(self) -> List[str]:
        return ["research_controller"]
    
    def _get_manager(self):
        if self._manager is None:
            from engine.Layer2_Knowledge.multi_index import multi_index_manager
            self._manager = multi_index_manager
        return self._manager
    
    async def execute(self, ctx: PipelineContext) -> ModuleResult:
        """Configure knowledge space routing based on query analysis."""
        try:
            manager = self._get_manager()
            manager.initialize()
            
            # Get query analysis from context
            query_type = ctx.get("query_type", "factual")
            required_evidence = ctx.get("required_evidence", [])
            
            # Determine recommended spaces
            spaces = manager.get_recommended_spaces(query_type, required_evidence)
            
            # Store in context for retriever to use
            ctx.set("knowledge_spaces", [s.value for s in spaces])
            ctx.set("multi_index_manager", manager)
            
            ctx.log(f"[MultiIndex] Recommended spaces: {[s.value for s in spaces]}")
            
            return ModuleResult(
                status=ModuleStatus.SUCCESS,
                output={
                    "spaces": [s.value for s in spaces],
                    "space_stats": manager.get_space_stats()
                }
            )
            
        except Exception as e:
            ctx.log(f"[MultiIndex] Error: {e}")
            return ModuleResult(
                status=ModuleStatus.FAILED,
                error=str(e)
            )


__all__ = [
    "MultiIndexModule",
]
