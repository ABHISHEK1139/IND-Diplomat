"""
apply_conflict_state_wire.py — Wire conflict_state into result dicts.
Adds conflict_state field to council_session in both WITHHELD and APPROVED paths.
Also adds it to the global_model dict.
Run once:  python Scripts/apply_conflict_state_wire.py
"""
import pathlib, sys

COORD = pathlib.Path(__file__).resolve().parent.parent / "Layer4_Analysis" / "coordinator.py"
src = COORD.read_text(encoding="utf-8")
original = src

# ===================================================================
# Insert conflict_state into the result dicts
# We add it right after "collection_priority" in global_model blocks
# ===================================================================

# Pattern: find all  "collection_priority": list(...)  lines in global_model blocks
# and add conflict_state after them

ANCHOR = '"collection_priority": list(getattr(session, "p7_collection_priority", []) or []),'
REPLACEMENT = '''"collection_priority": list(getattr(session, "p7_collection_priority", []) or []),
                        "conflict_state": dict(getattr(session, "conflict_state", {}) or {}),'''

count = src.count(ANCHOR)
if count < 1:
    print(f"[ERROR] Anchor found {count} times (expected >=1). Abort.")
    sys.exit(1)

src = src.replace(ANCHOR, REPLACEMENT)
print(f"[OK] Inserted conflict_state into {count} global_model dict(s).")

# ===================================================================
# Final write
# ===================================================================
if src == original:
    print("ERROR: No changes made! Aborting.")
    sys.exit(1)

COORD.write_text(src, encoding="utf-8")
print(f"Done. {COORD}")
