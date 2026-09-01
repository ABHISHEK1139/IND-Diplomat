import logging
import pluggy

logger = logging.getLogger("DIP3.Layer9.PluginManager")

hookspec = pluggy.HookspecMarker("dip")
hookimpl = pluggy.HookimplMarker("dip")

class DIPPluginSpec:
    """A hook specification namespace."""
    @hookspec
    def register_sensor(self):
        """Register a new data collection sensor."""

    @hookspec
    def register_expert(self):
        """Register a new reasoning expert."""

    @hookspec
    def register_visualization(self):
        """Register a new interactive visualization type."""
        
    @hookspec
    def register_export(self):
        """Register a new export format."""

class PluginManager:
    """
    Core Pluggy host that loads external plugins exposing the 'dip_plugin' entry point.
    """
    def __init__(self):
        self.pm = pluggy.PluginManager("dip")
        self.pm.add_hookspecs(DIPPluginSpec)
        
    def load_plugins(self):
        logger.info("Loading external plugins via Python entry points...")
        self.pm.load_setuptools_entrypoints("dip_plugin")
        
        # Local test loading for development
        try:
            from dip.ecosystem.experts import climate_plugin
            self.pm.register(climate_plugin)
            logger.info("Registered local plugin: climate_plugin")
        except ImportError:
            pass

plugin_manager = PluginManager()
plugin_manager.load_plugins()
