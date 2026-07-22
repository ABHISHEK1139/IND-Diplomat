#!/usr/bin/env python3
"""Bulk-fix imports after moving packages into src/dip/ namespace."""

import os
import re
import sys

# All package/module names that moved into dip.*
PACKAGES = [
    "Config", "core", "analyst_api", "api_ws", "control_loop",
    "decision", "deliberation", "deploy", "exports", "ind_diplomat",
    "investigation", "investigations",
    "layer0_planning", "layer1_collection",
    "layer10_enterprise", "layer10_telemetry",
    "layer11_hitl", "layer11_research", "layer12_adaptive",
    "layer2_knowledge", "layer3_state", "layer3_world_model",
    "layer4_reasoning", "layer5_forecasting", "layer5_trajectory",
    "layer6_backtesting", "layer6_presentation", "layer6_workspace",
    "layer7_global", "layer7_learning",
    "layer8_collaboration", "layer8_wargaming",
    "layer9_decision", "layer9_ecosystem",
    "legal", "memory", "nextgen", "SystemGuardian",
]

# Standalone modules that moved into dip
MODULES = ["verifier", "unified_pipeline", "orchestrator", "api", "run",
           "investigate", "ind_diplomat"]

def build_patterns():
    """Build compiled regex patterns for import rewriting."""
    patterns = []

    # Sort by length descending so longer names match first
    all_names = sorted(set(PACKAGES + MODULES), key=len, reverse=True)

    for name in all_names:
        # from <name>.<something> import ...
        patterns.append((
            re.compile(r'^(\s*from\s+)' + re.escape(name) + r'(\.)', re.MULTILINE),
            r'\g<1>dip.' + name + r'\2'
        ))
        # from <name> import ...
        patterns.append((
            re.compile(r'^(\s*from\s+)' + re.escape(name) + r'(\s+import\s)', re.MULTILINE),
            r'\g<1>dip.' + name + r'\2'
        ))
        # import <name>.<something>
        patterns.append((
            re.compile(r'^(\s*import\s+)' + re.escape(name) + r'(\.)', re.MULTILINE),
            r'\g<1>dip.' + name + r'\2'
        ))
        # import <name> (standalone)
        patterns.append((
            re.compile(r'^(\s*import\s+)' + re.escape(name) + r'(\s*$)', re.MULTILINE),
            r'\g<1>dip.' + name + r'\2'
        ))

    return patterns


def fix_file(filepath, patterns):
    """Apply all import fixes to a single file. Returns True if modified."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            original = f.read()
    except Exception as e:
        print(f"  WARN: Cannot read {filepath}: {e}")
        return False

    content = original
    for pat, repl in patterns:
        content = pat.sub(repl, content)

    # Prevent double-prefixing (dip.*)
    content = content.replace('dip.', 'dip.')

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    patterns = build_patterns()

    search_dirs = [
        os.path.join(root, 'src', 'dip'),
        os.path.join(root, 'tests'),
        os.path.join(root, 'scripts'),
    ]

    modified = 0
    total = 0

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(search_dir):
            # Skip __pycache__
            dirnames[:] = [d for d in dirnames if d != '__pycache__']
            for fname in filenames:
                if not fname.endswith('.py'):
                    continue
                filepath = os.path.join(dirpath, fname)
                total += 1
                if fix_file(filepath, patterns):
                    modified += 1
                    print(f"  FIXED: {os.path.relpath(filepath, root)}")

    print(f"\n{'='*60}")
    print(f"Import fix complete: {modified}/{total} files modified.")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
