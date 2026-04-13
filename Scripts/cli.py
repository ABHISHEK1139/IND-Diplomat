"""
CLI Entrypoint for IND-Diplomat
Typer-based CLI for ingestion, engram persistence, and graph loading.
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Optional, List

try:
    import typer
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    TYPER_AVAILABLE = True
except ImportError:
    TYPER_AVAILABLE = False
    print("Error: typer and rich packages required. Install with: pip install typer rich")
    sys.exit(1)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.Layer2_Knowledge.storage.engram_store import engram_store
# form Layer3_StateModel.binding.graph_manager import GraphManager (Moved to lazy import)
from engine.Layer1_Collection.ingestion.feeder.service import IngestionService
from Utils.tracing import tracer, trace_ingestion, log_event, TracePhase

app = typer.Typer(
    name="ind-diplomat",
    help="IND-Diplomat Sovereign Intelligence CLI",
    add_completion=False
)
console = Console()


@app.command()
def ingest(
    path: Path = typer.Argument(..., help="Path to document or directory to ingest"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursively process directories"),
    use_ocr: bool = typer.Option(False, "--ocr", help="Enable OCR for scanned documents"),
    persist: bool = typer.Option(True, "--persist/--no-persist", help="Persist to engram store")
):
    """Ingest documents into the knowledge base."""
    console.print(f"[bold blue]IND-Diplomat Ingestion[/bold blue]")
    console.print(f"Path: {path}")
    
    if not path.exists():
        console.print(f"[red]Error: Path does not exist: {path}[/red]")
        raise typer.Exit(1)
    
    service = IngestionService()
    files_to_process = []
    
    if path.is_file():
        files_to_process.append(path)
    elif path.is_dir():
        pattern = "**/*" if recursive else "*"
        for ext in [".pdf", ".docx", ".txt", ".md", ".json", ".html"]:
            files_to_process.extend(path.glob(f"{pattern}{ext}"))
    
    if not files_to_process:
        console.print("[yellow]No supported files found.[/yellow]")
        raise typer.Exit(0)
    
    console.print(f"Found {len(files_to_process)} file(s) to process")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Processing documents...", total=len(files_to_process))
        
        success_count = 0
        error_count = 0
        
        for file_path in files_to_process:
            progress.update(task, description=f"Processing: {file_path.name}")
            
            try:
                with trace_ingestion("ingest_document", file=str(file_path)):
                    result = asyncio.run(service.parse_document(str(file_path), use_ocr=use_ocr))
                
                # Add to Engram Store (JSON Persistence)
                if persist:
                    vector_chunks = []
                    for chunk in result.get("chunks", []):
                        # Add to Engram Store
                        engram_store.add(
                            content=chunk["content"],
                            metadata={
                                "source": str(file_path),
                                "chunk_id": chunk["id"],
                                "document_type": file_path.suffix[1:],
                                **result.get("metadata", {})
                            }
                        )
                        
                        # Prepare for Vector Store
                        vector_chunks.append({
                            "id": chunk["id"],
                            "text": chunk["content"],
                            "metadata": {
                                "source": str(file_path),
                                "document_type": file_path.suffix[1:],
                                **result.get("metadata", {})
                            }
                        })
                    
                    # Add to Vector Store (ChromaDB)
                    # Determine space based on path or type. Defaulting to 'legal' for now as primary use case is legal_memory.
                    # In a robust system, we'd detect 'global_risk_data' vs 'legal_memory'.
                    target_space = "legal" if "legal" in str(file_path) else "strategic"
                    
                    try:
                        from engine.Layer2_Knowledge.vector_store import get_vector_store
                        vs = get_vector_store()
                        vs.add_chunks(space=target_space, chunks=vector_chunks)
                    except Exception as ve:
                        console.print(f"[red]Vector Store Error: {ve}[/red]")

                success_count += 1
                log_event(f"Ingested: {file_path.name}", TracePhase.INGESTION, chunks=len(result.get("chunks", [])))
                
            except Exception as e:
                error_count += 1
                console.print(f"[red]Error processing {file_path}: {e}[/red]")
            
            progress.advance(task)
    
    console.print(f"\n[green]✓ Processed: {success_count}[/green]")
    if error_count > 0:
        console.print(f"[red]✗ Errors: {error_count}[/red]")
    
    if persist:
        engram_store.persist_all()
        console.print(f"[blue]Persisted to: {engram_store.persist_path}[/blue]")


@app.command()
def persist(
    output_dir: Path = typer.Option("./data/engrams", "--output", "-o", help="Output directory")
):
    """Persist engram store to disk."""
    console.print(f"[bold blue]Persisting Engram Store[/bold blue]")
    
    engram_store.persist_path = output_dir
    engram_store.persist_all()
    
    stats = engram_store.stats()
    console.print(f"[green]✓ Saved {stats['total_engrams']} engrams to {output_dir}[/green]")


@app.command("graph-load")
def graph_load(
    neo4j_uri: str = typer.Option("bolt://localhost:7687", "--uri", help="Neo4j URI"),
    neo4j_user: str = typer.Option("neo4j", "--user", help="Neo4j username"),
    neo4j_password: str = typer.Option("password", "--password", help="Neo4j password")
):
    """Load engrams into Neo4j graph database."""
    console.print(f"[bold blue]Loading to Neo4j Graph[/bold blue]")
    console.print(f"URI: {neo4j_uri}")
    
    os.environ["NEO4J_URI"] = neo4j_uri
    os.environ["NEO4J_USER"] = neo4j_user
    os.environ["NEO4J_PASSWORD"] = neo4j_password
    
    os.environ["NEO4J_PASSWORD"] = neo4j_password
    
    from engine.Layer3_StateModel.binding.graph_manager import GraphManager
    graph = GraphManager()
    
    if not graph.is_connected():
        console.print("[red]Error: Could not connect to Neo4j[/red]")
        raise typer.Exit(1)
    
    graph.init_schema()
    
    stats = engram_store.stats()
    console.print(f"Loading {stats['total_engrams']} engrams...")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Loading to graph...", total=stats['total_engrams'])
        
        for engram_id in list(engram_store._engrams.keys()):
            engram = engram_store.get(engram_id)
            if engram:
                graph.add_entity(
                    engram.id,
                    engram.metadata.get("document_type", "document"),
                    {
                        "content": engram.content[:500],
                        "fingerprint": engram.fingerprint,
                        **engram.metadata
                    }
                )
            progress.advance(task)
    
    console.print(f"[green]✓ Loaded {stats['total_engrams']} engrams to Neo4j[/green]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    jurisdiction: Optional[str] = typer.Option(None, "--jurisdiction", "-j", help="Filter by jurisdiction"),
    fuzzy: bool = typer.Option(True, "--fuzzy/--exact", help="Enable fuzzy matching"),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results")
):
    """Search the engram store."""
    console.print(f"[bold blue]Searching: {query}[/bold blue]")
    
    results = engram_store.search_clauses(
        query=query,
        jurisdiction=jurisdiction,
        fuzzy=fuzzy,
        limit=limit
    )
    
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return
    
    table = Table(title="Search Results")
    table.add_column("ID", style="cyan")
    table.add_column("Score", style="green")
    table.add_column("Content", style="white", max_width=60)
    table.add_column("Jurisdiction", style="blue")
    
    for r in results:
        engram = r["engram"]
        table.add_row(
            engram["id"][:20],
            f"{r['score']:.1f}",
            engram["content"][:100] + "...",
            engram.get("metadata", {}).get("jurisdiction", "N/A")
        )
    
    console.print(table)


@app.command()
def stats():
    """Show engram store statistics."""
    console.print(f"[bold blue]Engram Store Statistics[/bold blue]")
    
    s = engram_store.stats()
    
    table = Table()
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Engrams", str(s["total_engrams"]))
    table.add_row("Jurisdictions", ", ".join(s["jurisdictions"][:5]) or "None")
    table.add_row("Components", ", ".join(s["components"][:5]) or "None")
    table.add_row("Persist Path", str(s["persist_path"]))
    
    console.print(table)


@app.command()
def demo():
    """Run a complete demo: ingest → persist → graph-load."""
    console.print("[bold magenta]IND-Diplomat Demo Pipeline[/bold magenta]")
    console.print("=" * 50)
    
    # Step 1: Add sample data
    console.print("\n[blue]Step 1: Adding sample engrams...[/blue]")
    
    sample_data = [
        {
            "content": "Article 1 of the RCEP Agreement establishes the free trade area among signatory nations.",
            "metadata": {"jurisdiction": "ASEAN", "document_type": "treaty", "date": "2020-11-15", "component_id": "rcep_art1"}
        },
        {
            "content": "The Quad Security Dialogue focuses on maritime security in the Indo-Pacific region.",
            "metadata": {"jurisdiction": "Indo-Pacific", "document_type": "security", "date": "2021-03-12", "component_id": "quad_maritime"}
        },
        {
            "content": "UNCLOS Article 76 defines the continental shelf and its boundaries.",
            "metadata": {"jurisdiction": "International", "document_type": "law", "date": "1982-12-10", "component_id": "unclos_art76"}
        }
    ]
    
    for item in sample_data:
        engram_id, is_new = engram_store.add(item["content"], item["metadata"])
        status = "NEW" if is_new else "UPDATED"
        console.print(f"  [{status}] {engram_id}")
    
    # Step 2: Persist
    console.print("\n[blue]Step 2: Persisting to disk...[/blue]")
    engram_store.persist_all()
    console.print(f"  Saved to: {engram_store.persist_path}")
    
    # Step 3: Search
    console.print("\n[blue]Step 3: Testing search...[/blue]")
    results = engram_store.search_clauses("maritime security", fuzzy=True, limit=3)
    for r in results:
        console.print(f"  Score: {r['score']:.1f} - {r['engram']['content'][:50]}...")
    
    # Step 4: Stats
    console.print("\n[blue]Step 4: Statistics[/blue]")
    s = engram_store.stats()
    console.print(f"  Total engrams: {s['total_engrams']}")
    console.print(f"  Jurisdictions: {s['jurisdictions']}")
    
    console.print("\n[green]✓ Demo complete![/green]")


if __name__ == "__main__":
    app()
