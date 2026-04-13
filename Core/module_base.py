"""
Core Module Base - Abstract base class for all pipeline modules.
All modules must implement this interface for plugin-like integration.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import time
import traceback

if TYPE_CHECKING:
    from Core.context import PipelineContext


class ModuleStatus(Enum):
    """Module execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ModuleResult:
    """Result from module execution."""
    status: ModuleStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModuleBase(ABC):
    """
    Abstract base class for all pipeline modules.
    
    To create a new module:
    1. Inherit from ModuleBase
    2. Implement name, dependencies, execute()
    3. Register with: registry.register(MyModule())
    
    Example:
        class MyModule(ModuleBase):
            @property
            def name(self) -> str:
                return "my_module"
            
            @property
            def dependencies(self) -> List[str]:
                return ["retriever"]  # Runs after retriever
            
            async def execute(self, ctx: 'PipelineContext') -> ModuleResult:
                # Your logic here
                return ModuleResult(status=ModuleStatus.SUCCESS, output=result)
    """
    
    def __init__(self):
        self._enabled = True
        self._call_count = 0
        self._total_time_ms = 0.0
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique module name used for registration and cross-module calls."""
        pass
    
    @property
    def dependencies(self) -> List[str]:
        """List of module names that must run before this one."""
        return []
    
    @property
    def optional_dependencies(self) -> List[str]:
        """Modules that should run first IF enabled, but not required."""
        return []
    
    @property
    def is_enabled(self) -> bool:
        """Whether this module is currently enabled."""
        return self._enabled
    
    def enable(self):
        """Enable this module."""
        self._enabled = True
    
    def disable(self):
        """Disable this module."""
        self._enabled = False
    
    def can_execute(self, ctx: 'PipelineContext') -> bool:
        """
        Check if this module can execute given current context.
        Override in subclass for custom conditions.
        """
        if not self._enabled:
            return False
        
        # Check required dependencies have completed
        for dep in self.dependencies:
            if dep not in ctx.completed_modules:
                return False
        
        return True
    
    @abstractmethod
    async def execute(self, ctx: 'PipelineContext') -> ModuleResult:
        """
        Execute the module's main logic.
        
        Args:
            ctx: Pipeline context with shared data and cross-module access
            
        Returns:
            ModuleResult with status, output, and metadata
        """
        pass
    
    async def run(self, ctx: 'PipelineContext') -> ModuleResult:
        """
        Wrapper that handles logging, timing, and error handling.
        Do NOT override this - override execute() instead.
        """
        if not self.can_execute(ctx):
            reason = "disabled" if not self._enabled else "dependencies_not_met"
            return ModuleResult(
                status=ModuleStatus.SKIPPED,
                metadata={"reason": reason}
            )
        
        start_time = time.perf_counter()
        ctx.log(f"[{self.name}] Starting execution")
        
        try:
            result = await self.execute(ctx)
            duration = (time.perf_counter() - start_time) * 1000
            result.duration_ms = duration
            
            self._call_count += 1
            self._total_time_ms += duration
            
            ctx.log(f"[{self.name}] Completed in {duration:.1f}ms")
            ctx.record_module_completion(self.name, result)
            
            return result
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"
            ctx.log(f"[{self.name}] FAILED: {error_msg}")
            
            return ModuleResult(
                status=ModuleStatus.FAILED,
                error=error_msg,
                duration_ms=duration,
                metadata={"traceback": traceback.format_exc()}
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get module performance statistics."""
        return {
            "name": self.name,
            "enabled": self._enabled,
            "call_count": self._call_count,
            "total_time_ms": self._total_time_ms,
            "avg_time_ms": self._total_time_ms / self._call_count if self._call_count > 0 else 0
        }
    
    def __repr__(self):
        return f"<Module:{self.name} enabled={self._enabled}>"
