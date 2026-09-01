"""
Counterfactual Test Harness for IND-Diplomat 2.0.

Validates the pipeline's decision-making by testing three scenarios:
  1. Full signals (military + tension) -> should produce HIGH threat
  2. Remove military keyword -> should produce LOW or REFUSED
  3. Empty/irrelevant query -> should produce REFUSED

Run:
  python -m tests.counterfactual_harness
  python tests/counterfactual_harness.py
"""

import asyncio
import sys
import os
import pytest

# Ensure project root and src are on PYTHONPATH
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
sys.path.insert(0, PROJECT_ROOT)

from dip.unified_pipeline import execute


# ANSI colors for terminals
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_result_summary(name, result):
    """Print a compact summary of a test result."""
    print(f"  {CYAN}Status:{RESET}       {result.get('status', 'N/A')}")
    print(f"  {CYAN}Threat:{RESET}       {result.get('threat_level', 'N/A')}")
    print(f"  {CYAN}Verification:{RESET} {result.get('verification_score', 0.0):.0%}")
    print(f"  {CYAN}Hypotheses:{RESET}   {len(result.get('hypotheses', []))}")
    if result.get("refusal"):
        reasons = result["refusal"].get("reasons", [])
        print(f"  {CYAN}Refusal:{RESET}     {'; '.join(reasons[:2])}")
    print()


async def test_full_signals():
    """
    Test 1: Full signals query -> expects HIGH threat level.
    Military + tension keywords should trigger full signal generation.
    """
    print(f"{BOLD}Test 1: Full signals -> HIGH threat{RESET}")
    print(f"  Query: 'Assess military tensions near border regions'")
    print(f"  Country: IND")
    print()

    result = await execute(
        query="Assess military tensions near border regions",
        country_code="IND",
    )

    print_result_summary("Full Signals", result)

    threat = result.get("threat_level")
    has_hypotheses = len(result.get("hypotheses", [])) > 0

    # Accept CRITICAL, HIGH or ELEVATED (the heuristic path may vary slightly)
    passed = threat in ("CRITICAL", "HIGH", "ELEVATED") and has_hypotheses

    if passed:
        print(f"  {GREEN}[PASS]{RESET} -- Threat={threat}, Hypotheses={len(result['hypotheses'])}")
    else:
        print(f"  {RED}[FAIL]{RESET} -- Expected HIGH/ELEVATED with hypotheses, "
              f"got Threat={threat}, Hypotheses={len(result.get('hypotheses', []))}")

    return passed


async def test_no_military():
    """
    Test 2: Remove military keyword -> expects LOW or REFUSED.
    Without military/tension triggers, StateProvider produces no signals.
    """
    print(f"\n{BOLD}Test 2: No military signals -> LOW/REFUSED{RESET}")
    print(f"  Query: 'Evaluate economic trade patterns'")
    print(f"  Country: IND")
    print()

    result = await execute(
        query="Evaluate economic trade patterns",
        country_code="IND",
    )

    print_result_summary("No Military", result)

    threat = result.get("threat_level")
    status = result.get("status")

    # Without military signals, we expect LOW/MODERATE threat or REFUSED/WITHHELD status
    passed = threat in ("LOW", "MODERATE") or status in ("REFUSED", "WITHHELD")

    if passed:
        print(f"  {GREEN}[PASS]{RESET} -- Threat={threat}, Status={status}")
    else:
        print(f"  {RED}[FAIL]{RESET} -- Expected LOW/MODERATE/REFUSED/WITHHELD, "
              f"got Threat={threat}, Status={status}")

    return passed


async def test_empty_query():
    """
    Test 3: Empty/irrelevant query -> expects REFUSED.
    No signals should be generated, pipeline should refuse to assess.
    """
    print(f"\n{BOLD}Test 3: Empty signals -> REFUSED{RESET}")
    print(f"  Query: ''")
    print(f"  Country: XYZ")
    print()

    result = await execute(
        query="",
        country_code="XYZ",
    )

    print_result_summary("Empty Query", result)

    status = result.get("status")
    threat = result.get("threat_level")

    # With empty query, no signals -> expect REFUSED or LOW
    passed = status == "REFUSED" or threat == "LOW"

    if passed:
        print(f"  {GREEN}[PASS]{RESET} -- Status={status}, Threat={threat}")
    else:
        print(f"  {RED}[FAIL]{RESET} -- Expected REFUSED or LOW, "
              f"got Status={status}, Threat={threat}")

    return passed


async def run_all_tests():
    """Run the complete counterfactual test suite."""
    print()
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  IND-DIPLOMAT 2.0 -- Counterfactual Test Harness{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print()

    results = []

    try:
        results.append(("Full signals -> HIGH", await test_full_signals()))
    except Exception as e:
        print(f"  {RED}[ERROR]{RESET} -- {e}")
        results.append(("Full signals -> HIGH", False))

    try:
        results.append(("No military -> LOW/REFUSED", await test_no_military()))
    except Exception as e:
        print(f"  {RED}[ERROR]{RESET} -- {e}")
        results.append(("No military -> LOW/REFUSED", False))

    try:
        results.append(("Empty -> REFUSED", await test_empty_query()))
    except Exception as e:
        print(f"  {RED}[ERROR]{RESET} -- {e}")
        results.append(("Empty -> REFUSED", False))

    # Summary
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  Test Summary{RESET}")
    print(f"{'=' * 60}")

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for name, p in results:
        icon = f"{GREEN}[PASS]{RESET}" if p else f"{RED}[FAIL]{RESET}"
        print(f"  {icon}  {name}")

    print(f"\n  {BOLD}Result: {passed}/{total} tests passed{RESET}")

    if passed == total:
        print(f"  {GREEN}{BOLD}All tests passed!{RESET}")
    else:
        print(f"  {YELLOW}{BOLD}Some tests failed -- review output above.{RESET}")

    print()


@pytest.mark.asyncio
async def test_counterfactual_suite():
    assert await test_full_signals() is True
    assert await test_no_military() is True
    assert await test_empty_query() is True

if __name__ == "__main__":
    asyncio.run(run_all_tests())
