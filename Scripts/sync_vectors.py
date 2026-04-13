
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.Layer2_Knowledge.storage.engram_store import engram_store
from engine.Layer2_Knowledge.vector_store import get_vector_store
from rich.console import Console

console = Console()

def sync_vectors():
    console.print("[bold blue]Syncing Engrams to Vector Store...[/bold blue]")
    
    # Load all engrams
    engrams = engram_store._engrams
    console.print(f"Loaded {len(engrams)} engrams from disk.")
    
    if not engrams:
        console.print("[yellow]No engrams found. Run 'ingest' first.[/yellow]")
        return

    vs = get_vector_store()
    if not vs.available:
        console.print("[red]Vector Store (ChromaDB) not available.[/red]")
        return

    # Group by space
    # Heuristic: "legal_memory" -> "legal", else "strategic"
    batches = {
        "legal": [],
        "strategic": [],
        "event": [],
        "economic": []
    }
    
    for eid, engram in engrams.items():
        source = engram.metadata.get("source", "").lower()
        
        space = "strategic" # Default
        if "legal_memory" in source or "treaty" in source:
            space = "legal"
        elif "gdelt" in source or "news" in source:
            space = "event"
        elif "trade" in source or "econ" in source:
            space = "economic"
            
        chunk = {
            "id": engram.id,
            "text": engram.content,
            "metadata": engram.metadata
        }
        batches[space].append(chunk)

    # Push to VS
    for space, chunks in batches.items():
        if not chunks:
            continue
            
        console.print(f"Pushing {len(chunks)} chunks to '{space}' collection...")
        try:
            # Batch in 100s to be safe
            batch_size = 100
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i+batch_size]
                vs.add_chunks(space, batch)
                console.print(f"  Processed {min(i+batch_size, len(chunks))}/{len(chunks)}")
        except Exception as e:
            console.print(f"[red]Error pushing to {space}: {e}[/red]")

    console.print("[green]Sync Complete![/green]")

if __name__ == "__main__":
    sync_vectors()
