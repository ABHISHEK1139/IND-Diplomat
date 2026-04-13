"""
Core Signals Package — Expanded professional signal ontology.

This is an **additive layer** — it DOES NOT modify the existing
signal_registry.py or Layer4 signal_ontology.py.

It provides a comprehensive library of 80+ signals that can be
used by future sensor modules and minister reasoning.
"""

from Core.signals.signal_normalizer import normalize_signal, CANONICAL_SIGNAL_MAP
from Core.signals.ontology import SIGNAL_ONTOLOGY, get_signal_metadata
