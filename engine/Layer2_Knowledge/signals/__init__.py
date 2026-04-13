"""Signal model compatibility package."""

from importlib import import_module as _import_module

_impl = _import_module("engine.Layer2_Knowledge.signal_extraction.signals")

SignalType = _impl.SignalType
EventSignal = _impl.EventSignal

__all__ = ["SignalType", "EventSignal"]
