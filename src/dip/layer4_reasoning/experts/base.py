"""
Base Expert
===========
All domain experts inherit from this. 
They have access to Mem0 to remember past mistakes and lessons learned.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

try:
    from mem0 import Memory
except ImportError:
    Memory = None

from dip.Config.config import config
from dip.layer10_telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer4.Experts.Base")


class BaseExpert(ABC):
    def __init__(self, name: str, expertise: str):
        self.name = name
        self.expertise = expertise
        self.model = config.LLM_MODEL
        
        # Initialize expert's long-term memory
        self.memory = None
        if Memory:
            # Separate namespace for each expert
            self.memory = Memory.from_config({
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "host": "localhost",
                        "port": 6333,
                        "collection_name": f"expert_memory_{self.name.lower().replace(' ', '_')}"
                    }
                }
            })

    def recall_lessons(self, topic: str) -> str:
        """Recall past mistakes or lessons learned regarding this topic."""
        if not self.memory:
            return ""
            
        try:
            results = self.memory.search(query=topic, user_id=f"expert_{self.name}", limit=3)
            if not results:
                return ""
                
            lessons = "Lessons from past investigations:\n"
            for res in results:
                lessons += f"- {res.get('text', '')}\n"
            return lessons
        except Exception as e:
            logger.warning(f"Memory recall failed for {self.name}: {e}")
            return ""

    @abstractmethod
    async def analyze(self, world_model, topic: str) -> Dict[str, Any]:
        """
        Analyze the world model and produce a domain-specific hypothesis.
        To be implemented by specific experts.
        """
        pass
