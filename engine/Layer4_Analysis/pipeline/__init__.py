"""
Layer4_Analysis.pipeline — Extracted sub-modules from coordinator.py
====================================================================
Surgical refactor: the coordinator delegates heavy computation here.

Modules
-------
confidence_pipeline   Multi-factor confidence scoring + shadow mode
synthesis_engine      SRE, trajectory, black swan, global theater, conflict state
output_builder        WITHHELD / APPROVED dict builders + serialisation helpers
legal_rag_runner      Post-gate 4-brain legal evidence engine
withheld_recollection Directed re-collection loop (PIR → evidence → re-gate)
"""

from engine.Layer4_Analysis.pipeline.confidence_pipeline import compute_weighted_confidence
from engine.Layer4_Analysis.pipeline.synthesis_engine import run_synthesis
from engine.Layer4_Analysis.pipeline.output_builder import (
    build_withheld_output,
    build_approved_output,
    build_council_reasoning_dict,
    serialize_hypotheses,
)
from engine.Layer4_Analysis.pipeline.legal_rag_runner import run_post_gate_legal_rag
from engine.Layer4_Analysis.pipeline.withheld_recollection import run_recollection_loop
