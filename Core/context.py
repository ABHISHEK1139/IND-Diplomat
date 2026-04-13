"""
Pipeline Context - Shared context passed between modules.
Enables cross-module communication and data sharing.
"""

from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import uuid

if TYPE_CHECKING:
    from core.module_base import ModuleResult


@dataclass
class PipelineContext:
    """
    Shared context passed through the entire pipeline.
    
    Features:
    - Shared data store for inter-module data
    - Cross-module calling (module A can call module B)
    - Logging with trace ID
    - Feature flags
    
    Example usage in a module:
        # Read data from previous module
        docs = ctx.get("retrieved_docs", [])
        
        # Store data for next module
        ctx.set("verified_answer", verified)
        
        # Call another module
        result = await ctx.call_module("retriever", query="refined query")
    """
    
    # Core identifiers
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    
    # Original query
    query: str = ""
    
    # Pipeline state
    current_answer: str = ""
    confidence: float = 0.5
    sources: List[Dict] = field(default_factory=list)
    
    # Module tracking
    completed_modules: List[str] = field(default_factory=list)
    module_results: Dict[str, 'ModuleResult'] = field(default_factory=dict)
    
    # Shared data store (any module can read/write)
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Feature flags
    flags: Dict[str, bool] = field(default_factory=lambda: {
        "enable_safety": True,
        "enable_crag": True,
        "enable_cove": True,
        "enable_mcts": False,
        "enable_causal": False,
        "enable_debate": False,
        "enable_perspectives": False,
        "enable_red_team": True,
        "enable_hitl": True,
        "enable_temporal": True,
        "enable_temporal_briefing": True,
        "enable_confidence_ledger": True,
        "enable_dossier": True,
        "enable_scenarios": True
    })
    
    # Logs
    logs: List[str] = field(default_factory=list)
    
    # Cross-module call registry (set by orchestrator)
    _module_caller: Optional[Callable] = field(default=None, repr=False)
    
    # Timestamp
    created_at: datetime = field(default_factory=datetime.now)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from shared data store."""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set value in shared data store."""
        self.data[key] = value

    def add_source(self, source: Dict[str, Any]):
        """Append a source document to the context source list."""
        if isinstance(source, dict):
            self.sources.append(source)

    def set_analysis_confidence(
        self,
        score: float,
        source: str,
        components: Optional[Dict[str, Any]] = None,
    ):
        """
        Set the canonical analysis confidence produced before final explanation.
        Layer 4 verification metrics should be stored separately.
        """
        clamped = max(0.0, min(1.0, float(score)))
        self.confidence = clamped
        self.set(
            "analysis_confidence",
            {
                "score": round(clamped, 4),
                "source": source,
                "components": components or {},
                "updated_at": datetime.now().isoformat(),
            },
        )

    def get_analysis_confidence(self) -> Dict[str, Any]:
        """Return canonical confidence contract or a default view from ctx.confidence."""
        contract = self.get("analysis_confidence")
        if isinstance(contract, dict):
            return contract
        return {
            "score": round(max(0.0, min(1.0, float(self.confidence))), 4),
            "source": "default",
            "components": {},
        }
    
    def has(self, key: str) -> bool:
        """Check if key exists in data store."""
        return key in self.data
    
    def update(self, **kwargs):
        """Update multiple values in data store."""
        self.data.update(kwargs)
    
    def get_flag(self, flag_name: str) -> bool:
        """Get a feature flag value."""
        return self.flags.get(flag_name, False)
    
    def set_flag(self, flag_name: str, value: bool):
        """Set a feature flag."""
        self.flags[flag_name] = value
    
    def log(self, message: str):
        """Add a log entry with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = f"[{timestamp}] {message}"
        self.logs.append(entry)
        print(entry)  # Also print for debugging
    
    def record_module_completion(self, module_name: str, result: 'ModuleResult'):
        """Record that a module has completed."""
        self.completed_modules.append(module_name)
        self.module_results[module_name] = result
    
    async def call_module(self, module_name: str, **kwargs) -> 'ModuleResult':
        """
        Call another module from within a module.
        Enables bidirectional module communication.
        
        Example:
            # From CoVe module, call Retriever for more docs
            result = await ctx.call_module("retriever", query="refined query")
            
            # From RedTeam, call CoVe to verify critique
            result = await ctx.call_module("cove", answer=critique)
        """
        if self._module_caller is None:
            raise RuntimeError("Module caller not set. Use within pipeline context only.")
        
        self.log(f"[CrossCall] Calling module '{module_name}' with kwargs: {list(kwargs.keys())}")
        
        # Update context with provided kwargs
        for key, value in kwargs.items():
            self.set(f"_call_{key}", value)
        
        result = await self._module_caller(module_name, self)
        
        self.log(f"[CrossCall] Module '{module_name}' returned: {result.status.value}")
        
        return result
    
    def get_module_result(self, module_name: str) -> Optional['ModuleResult']:
        """Get the result from a previously completed module."""
        return self.module_results.get(module_name)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "query": self.query,
            "current_answer": self.current_answer,
            "confidence": self.confidence,
            "analysis_confidence": self.get_analysis_confidence(),
            "sources_count": len(self.sources),
            "completed_modules": self.completed_modules,
            "flags": self.flags,
            "created_at": self.created_at.isoformat()
        }
    
    def clone(self) -> 'PipelineContext':
        """Create a copy of this context for parallel execution."""
        return PipelineContext(
            trace_id=self.trace_id,
            session_id=self.session_id,
            user_id=self.user_id,
            query=self.query,
            current_answer=self.current_answer,
            confidence=self.confidence,
            sources=self.sources.copy(),
            completed_modules=self.completed_modules.copy(),
            module_results=self.module_results.copy(),
            data=self.data.copy(),
            flags=self.flags.copy(),
            logs=self.logs.copy(),
            _module_caller=self._module_caller,
            created_at=self.created_at
        )


def create_context(
    query: str,
    user_id: str = None,
    session_id: str = None,
    **flags
) -> PipelineContext:
    """Factory function to create a new pipeline context."""
    ctx = PipelineContext(
        query=query,
        user_id=user_id,
        session_id=session_id
    )
    
    # Update flags from kwargs
    for key, value in flags.items():
        if key.startswith("enable_"):
            ctx.set_flag(key, value)
    
    return ctx
