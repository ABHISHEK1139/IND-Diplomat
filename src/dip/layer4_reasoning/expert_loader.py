"""
Expert Loader
==============
Dynamically loads requested expert classes from the experts/ directory.
"""

import logging
import importlib
from typing import List

from dip.layer4_reasoning.experts.base import BaseExpert
from dip.layer9_ecosystem.plugin_manager import plugin_manager

logger = logging.getLogger("Layer4.ExpertLoader")


class ExpertLoader:
    def __init__(self, package_path: str = "layer4_reasoning.experts"):
        self.package_path = package_path

    def load_experts(self, expert_names: List[str]) -> List[BaseExpert]:
        """
        Dynamically imports and instantiates experts.
        Expects files like `economist.py` with class `EconomistExpert`.
        """
        loaded = []
        for name in expert_names:
            try:
                # E.g., 'economist' -> layer4_reasoning.experts.economist
                module_name = f"{self.package_path}.{name}"
                module = importlib.import_module(module_name)
                
                # Assume class name is Capitalized + 'Expert' (e.g., EconomistExpert)
                class_name = name.title().replace('_', '') + "Expert"
                expert_class = getattr(module, class_name)
                
                loaded.append(expert_class())
                logger.info(f"Loaded internal expert: {class_name}")
            except Exception as e:
                logger.warning(f"Could not load internal expert '{name}': {e}")
                
        # Inject external 3rd-party experts from the Pluggy ecosystem
        external_experts = plugin_manager.pm.hook.register_expert()
        if external_experts:
            logger.info(f"Loaded {len(external_experts)} external experts from plugins.")
            loaded.extend(external_experts)
            
        return loaded
