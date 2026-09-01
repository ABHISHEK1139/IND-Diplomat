"""
War Gaming CLI Runner (Layer 8)
===============================
Runs a global consequence simulation based on a hypothetical Prime Ministerial action.

Usage:
  python wargame.py "Assess tensions" --country IND --action "Impose 50% tariffs on key electronics"
  python wargame.py "Assess borders" --country CHN --action "Deploy Carrier Strike Group to the strait"
"""

import argparse
import asyncio
import sys
import os

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dip.pipeline.world_model.state.state_provider import StateProvider
from dip.core.schema import WargameAction
from dip.pipeline.forecasting.wargaming.scenario_engine import run_wargame

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.rule import Rule
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


async def execute_wargame(query: str, country: str, action_desc: str):
    console = Console() if HAS_RICH else None
    
    if console:
        console.print(Panel(f"[bold cyan]IND-DIPLOMAT 2.5[/bold cyan] · WAR GAMING SIMULATOR\n"
                            f"[dim]Simulating 6-Month Global Fallout[/dim]", border_style="cyan"))
        console.print(f"[bold]Target Country:[/bold] {country}")
        console.print(f"[bold]Proposed Action:[/bold] {action_desc}\n")
        
        with console.status("[bold green]Building initial state context...[/bold green]"):
            provider = StateProvider()
            base_context = await provider.build_state_context(country, query)
            
        with console.status("[bold yellow]Running Layer 8 Scenario Engine...[/bold yellow]"):
            action = WargameAction(description=action_desc, target_country=country)
            result = await run_wargame(base_context, action)
            
        # 1. Synthetic Signals
        console.print(Rule("[bold]Action Translation (Synthetic Signals)[/bold]", style="dim"))
        for sig in result.synthetic_signals:
            console.print(f"  [magenta]▸[/magenta] {sig.action} (Intensity: {sig.intensity:.2f})")
            
        # 2. Direct Escalation Delta
        console.print()
        console.print(Rule("[bold]Direct Impact[/bold]", style="dim"))
        color = "red" if result.escalation_delta > 0 else "green"
        console.print(f"  Escalation Delta for {country}: [{color}]{result.escalation_delta:+.2f}[/{color}]")
        
        # 3. Global Spillover Table
        console.print()
        if result.global_spillovers:
            spill_table = Table(title="Global Contagion Spillover (6-Month Forecast)", box=box.SIMPLE)
            spill_table.add_column("Affected Country", style="bold")
            spill_table.add_column("Spillover Severity", justify="right")
            
            for c, amt in result.global_spillovers.items():
                bar_len = int(min(1.0, amt) * 20)
                bar = "█" * bar_len
                spill_table.add_row(c, f"[red]{bar}[/red] {amt:.3f}")
                
            console.print(spill_table)
        else:
            console.print("  [dim]No significant global spillover detected.[/dim]")
            
        # 4. Consequence Briefing
        console.print()
        console.print(Rule("[bold]Strategic Consequence Briefing[/bold]", style="dim"))
        console.print(Panel(result.consequence_briefing, border_style="blue", padding=(1, 2)))
        
    else:
        # Fallback non-rich output
        print("WAR GAMING SIMULATOR")
        print(f"Action: {action_desc} -> {country}")
        
        provider = StateProvider()
        base_context = await provider.build_state_context(country, query)
        action = WargameAction(description=action_desc, target_country=country)
        result = await run_wargame(base_context, action)
        
        print(f"\nEscalation Delta: {result.escalation_delta:+.2f}")
        print("\nSpillovers:")
        for c, amt in result.global_spillovers.items():
            print(f"  {c}: {amt:.3f}")
            
        print("\nConsequence Briefing:")
        print(result.consequence_briefing)


def main():
    parser = argparse.ArgumentParser(description="Politiq AI 2.5 War Gaming Engine")
    parser.add_argument("query", type=str, help="Context query")
    parser.add_argument("--country", type=str, required=True, help="Target country code")
    parser.add_argument("--action", type=str, required=True, help="Proposed policy/military action")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(execute_wargame(args.query, args.country, args.action))
    except KeyboardInterrupt:
        print("\n[Interrupted]")
        sys.exit(1)


if __name__ == "__main__":
    main()
