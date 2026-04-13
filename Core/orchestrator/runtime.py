"""
Pipeline Orchestrator - Central execution engine.
Coordinates module execution with dependency resolution.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from core.module_base import ModuleBase, ModuleResult, ModuleStatus
from core.context import PipelineContext, create_context
from core.registry import registry
import time
import asyncio


@dataclass
class PipelineResult:
    """Final result from pipeline execution."""
    success: bool
    answer: str
    confidence: float
    trace_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Module results
    modules_run: List[str] = field(default_factory=list)
    modules_skipped: List[str] = field(default_factory=list)
    modules_failed: List[str] = field(default_factory=list)
    
    # Detailed results
    module_results: Dict[str, ModuleResult] = field(default_factory=dict)
    
    # Performance
    total_duration_ms: float = 0.0
    
    # Context data
    sources: List[Dict] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "answer": self.answer,
            "confidence": self.confidence,
            "trace_id": self.trace_id,
            "modules_run": len(self.modules_run),
            "modules_skipped": len(self.modules_skipped),
            "modules_failed": len(self.modules_failed),
            "total_duration_ms": self.total_duration_ms,
            "sources_count": len(self.sources)
        }


class Orchestrator:
    """
    Central pipeline orchestrator.
    
    Features:
    - Automatic dependency resolution
    - Cross-module communication
    - Error handling with graceful degradation
    - Performance tracking
    
    Usage:
        orchestrator = Orchestrator()
        
        # Configure
        orchestrator.disable("mcts")
        orchestrator.enable("causal")
        
        # Execute
        result = await orchestrator.run("What is RCEP?", user_id="user123")
    """
    
    def __init__(self):
        self.registry = registry
        self._execution_hooks: Dict[str, List] = {
            "before_module": [],
            "after_module": [],
            "on_error": []
        }
    
    def register_module(self, module: ModuleBase):
        """Register a new module."""
        self.registry.register(module)
    
    def unregister_module(self, module_name: str):
        """Remove a module."""
        self.registry.unregister(module_name)
    
    def enable(self, module_name: str):
        """Enable a module."""
        self.registry.enable(module_name)
    
    def disable(self, module_name: str):
        """Disable a module."""
        self.registry.disable(module_name)
    
    def add_hook(self, event: str, callback):
        """Add execution hook for debugging/monitoring."""
        if event in self._execution_hooks:
            self._execution_hooks[event].append(callback)
    
    async def _call_module(self, module_name: str, ctx: PipelineContext) -> ModuleResult:
        """
        Internal method to call a module (used for cross-module calls).
        This is what ctx.call_module() uses internally.
        """
        module = self.registry.get(module_name)
        if not module:
            return ModuleResult(
                status=ModuleStatus.FAILED,
                error=f"Module '{module_name}' not found"
            )
        
        return await module.run(ctx)
    
    async def run(
        self,
        query: str,
        user_id: str = None,
        session_id: str = None,
        **flags
    ) -> PipelineResult:
        """
        Execute the full pipeline.
        
        Args:
            query: User query
            user_id: Optional user ID for RBAC
            session_id: Optional session ID for context
            **flags: Feature flags (enable_mcts=True, etc.)
            
        Returns:
            PipelineResult with answer and metadata
        """
        start_time = time.perf_counter()
        
        # Create context
        ctx = create_context(query, user_id, session_id, **flags)
        
        # Set up cross-module caller
        ctx._module_caller = self._call_module
        
        ctx.log(f"[Orchestrator] Starting pipeline for query: {query[:50]}...")
        ctx.log(f"[Orchestrator] Trace ID: {ctx.trace_id}")
        
        # Get execution order
        execution_order = self.registry.get_enabled_execution_order()
        ctx.log(f"[Orchestrator] Execution order: {len(execution_order)} modules")
        
        modules_run = []
        modules_skipped = []
        modules_failed = []
        
        # Execute modules in order
        for module_name in execution_order:
            module = self.registry.get(module_name)
            if not module:
                continue
            
            # Run before hooks
            for hook in self._execution_hooks["before_module"]:
                await hook(module_name, ctx)
            
            # Execute module
            result = await module.run(ctx)
            
            # Track results
            if result.status == ModuleStatus.SUCCESS:
                modules_run.append(module_name)
            elif result.status == ModuleStatus.SKIPPED:
                modules_skipped.append(module_name)
            elif result.status == ModuleStatus.FAILED:
                modules_failed.append(module_name)
                
                # Run error hooks
                for hook in self._execution_hooks["on_error"]:
                    await hook(module_name, result.error, ctx)
            
            # Run after hooks
            for hook in self._execution_hooks["after_module"]:
                await hook(module_name, result, ctx)
        
        total_duration = (time.perf_counter() - start_time) * 1000
        
        ctx.log(f"[Orchestrator] Pipeline complete in {total_duration:.1f}ms")
        ctx.log(f"[Orchestrator] Run: {len(modules_run)}, Skip: {len(modules_skipped)}, Fail: {len(modules_failed)}")
        
        return PipelineResult(
            success=len(modules_failed) == 0,
            answer=ctx.current_answer,
            confidence=float(ctx.get_analysis_confidence().get("score", ctx.confidence)),
            trace_id=ctx.trace_id,
            data=ctx.data.copy(),
            modules_run=modules_run,
            modules_skipped=modules_skipped,
            modules_failed=modules_failed,
            module_results=ctx.module_results,
            total_duration_ms=total_duration,
            sources=ctx.sources,
            logs=ctx.logs
        )
    
    async def run_single_module(
        self,
        module_name: str,
        ctx: PipelineContext
    ) -> ModuleResult:
        """Run a single module for testing."""
        return await self._call_module(module_name, ctx)
    
    def get_module_graph(self) -> Dict[str, List[str]]:
        """Get dependency graph for visualization."""
        return self.registry.get_dependency_graph()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            "total_modules": len(self.registry),
            "enabled_modules": len(self.registry.get_enabled_execution_order()),
            "module_stats": self.registry.get_stats()
        }


# Global orchestrator instance
orchestrator = Orchestrator()


async def run_pipeline(
    query: str,
    user_id: str = None,
    session_id: str = None,
    **flags
) -> PipelineResult:
    """Convenience function to run the pipeline."""
    return await orchestrator.run(query, user_id, session_id, **flags)
