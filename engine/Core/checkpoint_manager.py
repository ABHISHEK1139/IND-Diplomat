import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("diplomat.checkpoint")

# Use runtime/checkpoints for local dev, or fallback to user home
try:
    from ind_diplomat.paths import RUNTIME_DIR
    CHECKPOINT_DIR = RUNTIME_DIR / "checkpoints"
except ImportError:
    CHECKPOINT_DIR = Path.home() / ".ind_diplomat" / "checkpoints"

class CheckpointManager:
    """
    Manages state persistence between pipeline stages, allowing the engine
    to resume from a specific point rather than starting over on failure.
    Inspired by LangGraph checkpointing in TradingAgents.
    """
    
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.checkpoint_dir = CHECKPOINT_DIR / self.trace_id
        os.makedirs(self.checkpoint_dir, exist_ok=True)
    
    def _get_path(self, layer_name: str) -> Path:
        return self.checkpoint_dir / f"{layer_name}.pkl"
        
    def save_checkpoint(self, layer_name: str, data: Any) -> None:
        """Save an intermediate state blob."""
        path = self._get_path(layer_name)
        try:
            # We use pickle to support complex StateContext/dataclass objects easily
            with open(path, "wb") as f:
                pickle.dump(data, f)
            logger.info(f"Checkpoint saved for trace {self.trace_id} at layer '{layer_name}'")
        except Exception as e:
            logger.error(f"Failed to save checkpoint {layer_name}: {e}")
            
    def load_checkpoint(self, layer_name: str) -> Optional[Any]:
        """Load an intermediate state blob if it exists."""
        path = self._get_path(layer_name)
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            logger.info(f"Checkpoint loaded for trace {self.trace_id} at layer '{layer_name}'")
            return data
        except Exception as e:
            logger.error(f"Failed to load checkpoint {layer_name}: {e}")
            return None
            
    def has_checkpoint(self, layer_name: str) -> bool:
        return self._get_path(layer_name).exists()
        
    def clear_all(self) -> None:
        """Clear checkpoints on successful complete run."""
        try:
            if self.checkpoint_dir.exists():
                for p in self.checkpoint_dir.glob("*.pkl"):
                    p.unlink()
                self.checkpoint_dir.rmdir()
                logger.info(f"Checkpoints cleared for trace {self.trace_id}")
        except Exception as e:
            logger.error(f"Failed to clear checkpoints for trace {self.trace_id}: {e}")
