"""
Translator Interface
====================
Abstract base class for all signal translators.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from ..signals.base import BaseSignal

class BaseTranslator(ABC):
    """
    Converts raw data records into a semantic signal.
    """
    
    @abstractmethod
    def translate(self, records: List[Dict[str, Any]]) -> BaseSignal:
        """
        Translate raw records into a signal.
        
        Args:
            records: List of raw data points (e.g., GDELT rows)
            
        Returns:
            A populated BaseSignal subclass (e.g., EventSignal)
        """
        pass
        
    def validate(self, signal: BaseSignal) -> bool:
        """Optional validation logic."""
        return True
