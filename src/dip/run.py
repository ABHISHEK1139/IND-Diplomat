"""
CLI Runner for IND-Diplomat (dip 2.0)
======================================

Full 7-layer intelligence assessment system.

Usage:
  python run.py "Assess military tensions near borders" --country IND
  python run.py "Evaluate threat level" --country CHN --json
  python run.py "Diplomatic situation" --country PAK --verbose
"""

import argparse
import asyncio
import json
import sys
import os

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dip.unified_pipeline import execute

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.rule import Rule
    from rich.columns import Columns
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ── Threat level styling ─────────────────────────────────────────

THREAT_STYLES = {
    "CRITICAL": "bold white on red",
    "HIGH": "bold red",
    "ELEVATED": "bold yellow",
    "LOW": "bold green",
}

STATUS_STYLES = {
    "COMPLETE": "green",
    "REFUSED": "red",
    "HUMAN_REVIEW": "yellow",
    "ERROR": "bold red",
}


def display_rich_output(result: dict, verbose: bool = False) -> None:
    console = Console()
    console.print()

    # ── Header Banner ──
    threat = result.get("threat_level", "N/A")
    threat_style = THREAT_STYLES.get(threat, "dim")
    status = result.get("status", "UNKNOWN")
    status_style = STATUS_STYLES.get(status, "white")
    elapsed = result.get("elapsed_seconds", 0.0)

    console.print(Panel(
        f"[bold cyan]IND-DIPLOMAT 2.0[/bold cyan]  ·  "
        f"7-Layer Intelligence Assessment System\n"
        f"[dim]Query: {result['query']}  |  Country: {result['country']}  |  "
        f"Time: {elapsed:.1f}s[/dim]",
        border_style="cyan",
        box=box.DOUBLE,
    ))

    # ── Status Summary ──
    verification = result.get("verification_score", 0.0)
    obs_count = result.get("observation_count", 0)

    summary = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 3))
    summary.add_column("Label", style="bold", width=18)
    summary.add_column("Value")
    summary.add_row("Status", f"[{status_style}]● {status}[/{status_style}]")
    summary.add_row("Threat Level", f"[{threat_style}]{threat}[/{threat_style}]")
    summary.add_row("Verification", f"{'✓' if verification > 0.7 else '✗'} {verification:.0%}")
    summary.add_row("Observations", str(obs_count))
    console.print(Panel(summary, title="[bold]Assessment Summary[/bold]", border_style="blue"))

    # ── Hypotheses Table ──
    hypotheses = result.get("hypotheses", [])
    if hypotheses:
        hyp_table = Table(
            title="Minister Council Hypotheses",
            box=box.ROUNDED,
            show_lines=True,
            title_style="bold magenta",
        )
        hyp_table.add_column("Minister", style="cyan", width=22)
        hyp_table.add_column("Domain", style="white", width=24)
        hyp_table.add_column("Confidence", justify="center", width=12)
        hyp_table.add_column("Signals", justify="center", width=10)
        hyp_table.add_column("Gaps", justify="center", width=10)

        for h in hypotheses:
            conf = h.get("confidence", 0)
            conf_style = "green" if conf > 0.7 else "yellow" if conf > 0.4 else "red"
            hyp_table.add_row(
                h.get("minister", "?"),
                h.get("type", "?"),
                f"[{conf_style}]{conf:.0%}[/{conf_style}]",
                str(len(h.get("matched_signals", []))),
                str(len(h.get("missing_signals", []))),
            )
        console.print(hyp_table)

    # ── Trajectory Forecast ──
    trajectory = result.get("trajectory")
    if trajectory and isinstance(trajectory, dict):
        traj_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        traj_table.add_column("Window", style="bold")
        traj_table.add_column("P(HIGH)")
        traj_table.add_row("14-day", f"{trajectory.get('prob_14d', 0):.0%}")
        traj_table.add_row("30-day", f"{trajectory.get('prob_30d', 0):.0%}")
        traj_table.add_row("60-day", f"{trajectory.get('prob_60d', 0):.0%}")
        traj_label = trajectory.get("label", "STABLE")
        traj_style = "red" if traj_label == "ESCALATING" else "green" if traj_label == "DE_ESCALATING" else "yellow"
        traj_table.add_row("Trajectory", f"[{traj_style}]{traj_label}[/{traj_style}]")
        console.print(Panel(traj_table, title="[bold]Trajectory Forecast[/bold]", border_style="magenta"))

    # ── Black Swan Alert ──
    black_swan = result.get("black_swan")
    if black_swan and isinstance(black_swan, dict) and black_swan.get("triggered"):
        reasons = black_swan.get("reasons", [])
        console.print(Panel(
            "[bold red]⚠ DISCONTINUITY EVENT DETECTED[/bold red]\n\n" +
            "\n".join(f"  [red]▸[/red] {r}" for r in reasons) +
            "\n\n[dim]Mandatory human review required.[/dim]",
            title="[bold red]BLACK SWAN ALERT[/bold red]",
            border_style="red",
        ))

    # ── Briefing ──
    briefing = result.get("briefing")
    if briefing:
        console.print()
        console.print(Rule("[bold]Executive Intelligence Briefing[/bold]", style="cyan"))
        console.print()
        console.print(Panel(briefing, border_style="dim cyan", padding=(1, 2)))

    # ── Refusal ──
    if result.get("refusal"):
        console.print()
        refusal = result["refusal"]
        reasons = refusal.get("reasons", []) if isinstance(refusal, dict) else [str(refusal)]
        recommendation = refusal.get("recommendation", "") if isinstance(refusal, dict) else ""
        console.print(Panel(
            "\n".join(f"  • {r}" for r in reasons) +
            f"\n\n[dim]{recommendation}[/dim]",
            title="[bold red]⚠ ASSESSMENT REFUSED[/bold red]",
            border_style="red",
        ))

    # ── HITL Review ──
    if result.get("hitl_review"):
        review = result["hitl_review"]
        console.print(Panel(
            f"Priority: [yellow]{review.get('priority', 'N/A')}[/yellow]\n"
            f"Reason: {review.get('reason', 'N/A')}\n\n"
            f"[bold]Action Required:[/bold]\n" +
            "\n".join(f"  {i+1}. {a}" for i, a in enumerate(review.get("action_required", []))),
            title="[bold yellow]👁 HUMAN REVIEW REQUIRED[/bold yellow]",
            border_style="yellow",
        ))

    # ── Contagion ──
    contagion = result.get("contagion")
    if contagion and isinstance(contagion, dict):
        console.print()
        console.print("[bold red]Global Contagion Spillovers:[/bold red]")
        for target, amount in contagion.items():
            bar = "█" * int(amount * 40)
            console.print(f"  {target}: [red]{bar}[/red] {amount:.3f}")

    # ── Learning Report ──
    learning = result.get("learning")
    if learning and isinstance(learning, dict) and verbose:
        console.print()
        console.print("[bold]Learning Report:[/bold]")
        for k, v in learning.items():
            console.print(f"  [dim]{k}:[/dim] {v}")

    # ── Verbose: Evidence & Red Team ──
    if verbose:
        console.print()
        console.print(Rule("[bold]Detailed Evidence[/bold]", style="dim"))

        evidence = result.get("evidence_log", [])
        if evidence:
            for e in evidence:
                console.print(f"  [dim]📎[/dim] {e}")
        else:
            console.print("  [dim]No evidence collected.[/dim]")

        red_team = result.get("red_team_report", [])
        if red_team:
            console.print()
            console.print("[bold red]Red Team Challenges:[/bold red]")
            for c in red_team:
                console.print(f"  [red]⚡[/red] {c}")

    console.print()


def display_plain_output(result: dict, verbose: bool = False) -> None:
    """Fallback display without Rich."""
    print("\n" + "=" * 60)
    print("IND-DIPLOMAT 2.0 — 7-Layer Intelligence Assessment")
    print("=" * 60)
    print(f"Query:        {result['query']}")
    print(f"Country:      {result['country']}")
    print(f"Status:       {result.get('status', 'UNKNOWN')}")
    print(f"Threat:       {result.get('threat_level', 'N/A')}")
    print(f"Verified:     {result.get('verification_score', 0.0):.0%}")
    print(f"Observations: {result.get('observation_count', 0)}")
    print(f"Time:         {result.get('elapsed_seconds', 0):.1f}s")
    print("-" * 60)

    for h in result.get("hypotheses", []):
        print(f"  [{h['minister']}] {h['type']}: {h['confidence']:.0%}")

    trajectory = result.get("trajectory")
    if trajectory and isinstance(trajectory, dict):
        print(f"\nTrajectory: {trajectory.get('label', 'N/A')}")
        print(f"  P(14d): {trajectory.get('prob_14d', 0):.0%}")

    briefing = result.get("briefing")
    if briefing:
        print(f"\n{'=' * 60}\nEXECUTIVE BRIEFING\n{'=' * 60}")
        print(briefing)

    if result.get("refusal"):
        print(f"\n{'!' * 60}\nASSESSMENT REFUSED")
        refusal = result["refusal"]
        if isinstance(refusal, dict):
            for r in refusal.get("reasons", []):
                print(f"  • {r}")

    if verbose:
        for e in result.get("evidence_log", []):
            print(f"  📎 {e}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="IND-Diplomat 2.0 — Geopolitical Intelligence Assessment System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run.py \"Assess military tensions\" --country IND\n"
            "  python run.py \"Evaluate threat level\" --country CHN --json\n"
            "  python run.py \"Diplomatic situation\" --country PAK --verbose\n"
        ),
    )
    parser.add_argument("query", type=str, help="Intelligence query to assess")
    parser.add_argument("--country", type=str, default="IND", help="Country code (default: IND)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output raw JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed evidence and logs")

    args = parser.parse_args()

    try:
        result = asyncio.run(execute(args.query, args.country))
    except KeyboardInterrupt:
        print("\n[Interrupted]")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        sys.exit(1)

    if args.json_output:
        print(json.dumps(result, indent=2, default=str))
    elif HAS_RICH:
        display_rich_output(result, verbose=args.verbose)
    else:
        display_plain_output(result, verbose=args.verbose)


if __name__ == "__main__":
    main()
