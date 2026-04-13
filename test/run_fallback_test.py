"""Wrapper to run test_fallback and capture output to a file."""
import subprocess
import sys
import os
from pathlib import Path

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test._support import script_log_path

result = subprocess.run(
    [sys.executable, "-X", "utf8", "-m", "test.test_fallback"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=300,
)

output_path = script_log_path("fallback_clean.txt")
with open(output_path, "w", encoding="utf-8") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr)
    f.write(f"\n=== EXIT CODE: {result.returncode} ===\n")

print(f"Output written to {output_path}")
print(f"Exit code: {result.returncode}")
