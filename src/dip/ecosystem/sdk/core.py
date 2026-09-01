# The public SDK for DIP plugins
import logging

logger = logging.getLogger("DIP3.SDK")

class Plugin:
    """Base class for all DIP Plugins."""
    name = "Base Plugin"
    version = "1.0"
    author = "Unknown"

    def register(self):
        logger.info(f"Registering plugin: {self.name} v{self.version} by {self.author}")

import pluggy
from dip.pipeline.deliberation.reasoning.dynamic_experts import DynamicExpert

# This is the decorator 3rd party devs use to register their plugins
hookimpl = pluggy.HookimplMarker("dip")

class DIPExpertPlugin(DynamicExpert):
    """
    Public SDK Class for creating a third-party Reasoning Expert.
    Inherits the DSPy reasoning engine automatically.
    """
    def __init__(self, role_name: str, expertise: str):
        # We map role_name -> self.role for DynamicExpert
        super().__init__(role=role_name, expertise=expertise)
