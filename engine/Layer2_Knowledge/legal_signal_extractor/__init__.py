"""Compatibility package for legal signal extraction."""

from importlib import import_module as _import_module

_impl = _import_module("engine.Layer2_Knowledge.signal_extraction.legal_signal_extractor")

legal_signal_extractor = _impl.legal_signal_extractor
precedence_engine = _impl.precedence_engine

__all__ = ["legal_signal_extractor", "precedence_engine"]
