"""Layer-2 translator compatibility package."""

from importlib import import_module as _import_module

_base = _import_module("engine.Layer2_Knowledge.sources.base")
_gdelt = _import_module("engine.Layer2_Knowledge.sources.gdelt_translator")

BaseTranslator = _base.BaseTranslator
GDELTTranslator = _gdelt.GDELTTranslator

__all__ = ["BaseTranslator", "GDELTTranslator"]
