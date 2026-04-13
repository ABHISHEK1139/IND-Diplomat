
import sys
import os
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.Layer3_StateModel.providers.state_provider import StateProvider
from engine.Layer4_Analysis.coordinator import CouncilCoordinator
from engine.Layer4_Analysis.council_session import CouncilSession
from rich.console import Console
from rich.panel import Panel
from test._support import output_path

console = Console()

def run_system_test():
    console.print("[bold green]Starting End-to-End System Test[/bold green]")
    
    # 1. Initialize Components
    console.print("1. Initializing Providers & Coordinator...")
    provider = StateProvider()
    coordinator = CouncilCoordinator()
    
    # 2. Build Context (The Intelligence Phase)
    country = "IND"
    console.print(f"2. Building State Context for {country} (Force RAG=True)...")
    
    # Force RAG to test the Query Router
    context = provider.get_state_context(country, force_rag=True)
    
    console.print(f"   > Structured Data: Military Score {context.military.mobilization_level:.2f}")
    console.print(f"   > Unstructured Data: {len(context.evidence.rag_documents)} RAG documents retrieved.")
    if context.evidence.rag_documents:
        console.print(f"     Snippet: {context.evidence.rag_documents[0][:100]}...")
    
    # 3. Convene Council (The Reasoning Phase)
    console.print("3. Convening Council of Ministers...")
    session = CouncilSession(
        session_id="test-session-001",
        question="Analyze the current threat level of India.",
        state_context=context
    )
    session = coordinator.convene_council(session)
    
    console.print(f"   > Council Decision: {session.king_decision}")
    console.print(f"   > Confidence: {session.final_confidence:.2f}")
    
    # 4. Generate Standardized Result (The Output Phase)
    console.print("4. Generating Standardized Analysis Result...")
    result = coordinator.generate_result(session)
    
    # --- WHITE BOX LOGGING ---
    log_path = output_path("script_logs", "system_trace.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=== IND-DIPLOMAT SYSTEM TRACE ===\n")
        f.write(f"Session ID: {session.session_id}\n")
        f.write(f"Timestamp: {session.created_at}\n\n")
        
        f.write("--- 1. INPUT STATE ---\n")
        f.write(f"Query: {session.question}\n")
        f.write(f"Context Summary: {context.summary()}\n")
        f.write(f"Active Signals: \n")
        f.write(f"  - Military: {context.military}\n")
        f.write(f"  - Economic: {context.economic}\n")
        f.write(f"  - Diplomatic: {context.diplomatic}\n")
        f.write(f"  - RAG Docs: {len(context.evidence.rag_documents)} items\n\n")
        
        f.write("--- 2. MINISTER DELIBERATION ---\n")
        for report in session.ministers_reports:
            f.write(f"\n[Minister: {report.minister_name}]\n")
            f.write(f"  Hypothesis: {report.hypothesis}\n")
            f.write(f"  Confidence: {report.confidence:.2f}\n")
            f.write(f"  Reasoning Chain: {report.reasoning}\n")
            f.write(f"  Predicted Signals: {report.predicted_signals}\n")
            
        f.write("\n--- 3. COUNCIL DECISION (The King) ---\n")
        f.write(f"Selected Hypothesis: {session.king_decision}\n")
        f.write(f"Final Confidence: {session.final_confidence:.2f}\n")
        f.write(f"Conflicts Identified: {session.identified_conflicts}\n")
        f.write(f"Investigation Needs: {session.investigation_needs}\n")
        
        f.write("\n=== END TRACE ===\n")
    
    console.print(Panel(
        f"[bold]Summary:[/bold] {result.summary_text}\n"
        f"[bold]Confidence:[/bold] {result.confidence_score:.2f}\n"
        f"[bold]Evidence Used:[/bold] {len(result.evidence_used)} items\n"
        f"[bold]Reasoning:[/bold]\n{result.detailed_reasoning}",
        title="Final Analysis Result",
        border_style="green"
    ))
    
    console.print(f"\n[bold blue]Detailed White Box Trace saved to: {log_path.absolute()}[/bold blue]")
    
    if result.confidence_score > 0 and context:
        console.print("[bold green]TEST PASSED: Full Pipeline Functional[/bold green]")
    else:
        console.print("[bold red]TEST FAILED: Pipeline produced no confidence or context[/bold red]")

if __name__ == "__main__":
    run_system_test()
