"""Compatibility shim for Layer2_Knowledge.signal_extraction.legal_signal_extractor.extractor."""

from importlib import import_module as _import_module

_impl = _import_module("engine.Layer2_Knowledge.signal_extraction.legal_signal_extractor.extractor")

__all__ = getattr(_impl, "__all__", [name for name in dir(_impl) if not name.startswith("_")])
for _name in __all__:
    globals()[_name] = getattr(_impl, _name)


def __getattr__(name):
    return getattr(_impl, name)


def __dir__():
    return sorted(set(globals().keys()) | set(dir(_impl)))
