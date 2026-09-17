"""Retired: live dossier verification script (stale, kept as a pointer).

This script predates the DIP 3 package layout. It imports
``dip.pipeline.synthesis.presentation.dossier_compiler`` (which no longer
exists) and attributes that no longer exist on StateContext, so it cannot
run. It is preserved here instead of deleted so existing references keep
resolving to an explanation rather than a bare ModuleNotFoundError.

Use instead:
  - Offline calibrated backtest:  pytest tests/test_offline_backtest.py
  - Validation suite (heuristic):  python scripts/run_validation_suite.py
  - Live dossier check:            POST /api/v3/assess, then
                                   GET /api/v3/jobs/{id}/result (briefing)
"""
import sys

print(__doc__)
sys.exit(2)
