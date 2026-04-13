"""
Module Registry - Plugin-like registration and discovery of modules.
Enables easy add/remove of features.
"""

from typing import Dict, List, Type, Optional, Callable
from core.module_base import ModuleBase
import importlib
import pkgutil


class ModuleRegistry:
    """
    Central registry for all pipeline modules.
    
    Features:
    - Plugin-like registration
    - Dependency resolution
    - Easy enable/disable
    - Auto-discovery from packages
    
    Usage:
        # Register a module
        registry.register(MyModule())
        
        # Enable/disable
        registry.disable("mcts")
        registry.enable("causal")
        
        # Get execution order
        order = registry.get_execution_order()
        
        # Auto-discover from package
        registry.discover_from_package("agents.modules")
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._modules: Dict[str, ModuleBase] = {}
            cls._instance._execution_order: List[str] = []
            cls._instance._order_dirty = True
        return cls._instance
    
    def register(self, module: ModuleBase):
        """
        Register a module with the registry.
        
        Args:
            module: Module instance implementing ModuleBase
        """
        if module.name in self._modules:
            print(f"[Registry] Replacing existing module: {module.name}")
        else:
            print(f"[Registry] Registered module: {module.name}")
        
        self._modules[module.name] = module
        self._order_dirty = True
    
    def unregister(self, module_name: str) -> bool:
        """
        Remove a module from the registry.
        
        Args:
            module_name: Name of module to remove
            
        Returns:
            True if removed, False if not found
        """
        if module_name in self._modules:
            del self._modules[module_name]
            self._order_dirty = True
            print(f"[Registry] Unregistered module: {module_name}")
            return True
        return False
    
    def get(self, module_name: str) -> Optional[ModuleBase]:
        """Get a module by name."""
        return self._modules.get(module_name)
    
    def get_all(self) -> Dict[str, ModuleBase]:
        """Get all registered modules."""
        return self._modules.copy()
    
    def enable(self, module_name: str) -> bool:
        """Enable a module."""
        if module_name in self._modules:
            self._modules[module_name].enable()
            print(f"[Registry] Enabled module: {module_name}")
            return True
        return False
    
    def disable(self, module_name: str) -> bool:
        """Disable a module."""
        if module_name in self._modules:
            self._modules[module_name].disable()
            print(f"[Registry] Disabled module: {module_name}")
            return True
        return False
    
    def is_enabled(self, module_name: str) -> bool:
        """Check if a module is enabled."""
        module = self._modules.get(module_name)
        return module.is_enabled if module else False
    
    def get_execution_order(self) -> List[str]:
        """
        Get modules in dependency-resolved order.
        Uses topological sort to ensure dependencies run first.
        """
        if not self._order_dirty:
            return self._execution_order
        
        # Build dependency graph
        visited = set()
        order = []
        temp_mark = set()
        
        def visit(name: str):
            if name in temp_mark:
                raise ValueError(f"Circular dependency detected involving: {name}")
            if name in visited:
                return
            
            temp_mark.add(name)
            
            module = self._modules.get(name)
            if module:
                for dep in module.dependencies:
                    if dep in self._modules:
                        visit(dep)
                for dep in module.optional_dependencies:
                    if dep in self._modules and self._modules[dep].is_enabled:
                        visit(dep)
            
            temp_mark.remove(name)
            visited.add(name)
            order.append(name)
        
        for module_name in self._modules:
            if module_name not in visited:
                visit(module_name)
        
        self._execution_order = order
        self._order_dirty = False
        
        return self._execution_order
    
    def get_enabled_execution_order(self) -> List[str]:
        """Get only enabled modules in execution order."""
        return [
            name for name in self.get_execution_order()
            if self._modules[name].is_enabled
        ]
    
    def discover_from_package(self, package_name: str):
        """
        Auto-discover and register modules from a package.
        Looks for classes inheriting from ModuleBase.
        
        Args:
            package_name: Full package path (e.g., "agents.modules")
        """
        try:
            package = importlib.import_module(package_name)
            
            for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
                try:
                    module = importlib.import_module(f"{package_name}.{modname}")
                    
                    # Find ModuleBase subclasses
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, ModuleBase) and 
                            attr is not ModuleBase):
                            # Instantiate and register
                            instance = attr()
                            self.register(instance)
                            
                except Exception as e:
                    print(f"[Registry] Failed to load module {modname}: {e}")
                    
        except Exception as e:
            print(f"[Registry] Failed to discover from {package_name}: {e}")
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get the full dependency graph for visualization."""
        return {
            name: module.dependencies + module.optional_dependencies
            for name, module in self._modules.items()
        }
    
    def get_stats(self) -> Dict[str, Dict]:
        """Get statistics for all modules."""
        return {
            name: module.get_stats()
            for name, module in self._modules.items()
        }
    
    def reset(self):
        """Clear all registered modules."""
        self._modules.clear()
        self._execution_order.clear()
        self._order_dirty = True
    
    def __len__(self):
        return len(self._modules)
    
    def __contains__(self, module_name: str):
        return module_name in self._modules


# Singleton instance
registry = ModuleRegistry()
