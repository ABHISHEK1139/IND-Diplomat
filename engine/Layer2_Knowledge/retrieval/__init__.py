"""Layer-2 retrieval compatibility package."""

from importlib import import_module as _import_module

_impl = _import_module("engine.Layer2_Knowledge.access_api.time_selector")

filter_documents_by_time = _impl.filter_documents_by_time

__all__ = ["filter_documents_by_time"]
