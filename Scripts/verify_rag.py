
import sys
import os
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.Layer2_Knowledge.storage.engram_store import engram_store
from engine.Layer2_Knowledge.vector_store import get_vector_store
from rich.console import Console
from rich.table import Table

console = Console()

def verify_rag():
    console.print("[bold blue]Verifying RAG Consistency...[/bold blue]")
    
    # 1. Check Engram Store
    estats = engram_store.stats()
    total_engrams = estats["total_engrams"]
    console.print(f"Engram Store Count: [green]{total_engrams}[/green]")
    
    if total_engrams == 0:
        console.print("[red]Engram Store is empty! Run ingestion first.[/red]")
        return

    # 2. Check Vector Store
    vs = get_vector_store()
    if not vs.available:
        console.print("[red]Vector Store not available.[/red]")
        return
        
    collections = ["legal", "strategic", "event", "economic"]
    total_vectors = 0
    
    table = Table(title="Vector Store Collections")
    table.add_column("Collection", style="cyan")
    table.add_column("Count", style="green")
    
    for name in collections:
        try:
            col = vs.client.get_collection(name)
            count = col.count()
            table.add_row(name, str(count))
            total_vectors += count
        except Exception:
            table.add_row(name, "0 (Not Created)")

    console.print(table)
    console.print(f"Total Vectors: [green]{total_vectors}[/green]")
    
    # 3. Verdict
    # Vectors might be slightly different if chunking dropped empty ones, but should be close.
    # Actually, sync_vectors pushes 1:1 from engrams.
    
    if total_vectors >= total_engrams:
        console.print(f"\n[bold green]SUCCESS: RAG is fully populated ({total_vectors} vectors for {total_engrams} engrams).[/bold green]")
    elif total_vectors > 0:
         percentage = (total_vectors / total_engrams) * 100
         console.print(f"\n[bold yellow]PARTIAL: {percentage:.1f}% synced. ({total_vectors}/{total_engrams})[/bold yellow]")
    else:
        console.print("\n[bold red]FAILURE: Vector Store is empty.[/bold red]")

if __name__ == "__main__":
    verify_rag()
