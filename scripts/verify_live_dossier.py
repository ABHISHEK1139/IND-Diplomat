import asyncio
import logging
from dip.layer3_state.state_provider import StateProvider
from dip.layer3_state.bayesian_tracker import BayesianTracker
from dip.layer4_reasoning.gap_analyzer import GapAnalyzer
from dip.layer6_presentation.dossier_compiler import DossierCompiler
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LiveVerification")

async def run_live_verification():
    target = "Russia Sanctions Economy"
    query = "Analyze the impact of global economic sanctions on Russia and potential cyber retaliation."
    
    logger.info(f"Initiating LIVE Dossier Compilation for: {target}")
    
    # 1. Fetch live data (RSS/GDELT) and extract signals
    provider = StateProvider()
    context = await provider.build_state_context(target, query)
    
    logger.info(f"Extracted {len(context.current_signals)} signals from live sources.")
    
    if len(context.current_signals) == 0:
        logger.error("No signals extracted. Cannot build dossier.")
        return
        
    # 2. Bayesian Confidence Updates
    tracker = BayesianTracker(initial_prior=0.40) # Assume 40% initial belief of escalation
    traces = tracker.update_beliefs(context.current_signals, hypothesis_label="Economic Instability / Cyber Retaliation")
    context.bayesian_traces = traces
    logger.info(f"Generated {len(traces)} Bayesian update steps.")
    
    # 3. Gap Analysis
    gap_analyzer = GapAnalyzer()
    gaps = await gap_analyzer.analyze_gaps(context)
    context.intelligence_gaps = gaps
    logger.info(f"Identified {len(gaps)} critical intelligence gaps.")
    
    # 4. Dossier Compilation via LangGraph
    compiler = DossierCompiler()
    dossier_md = compiler.compile_dossier(context)
    
    # Write to output file
    output_path = "live_dossier_output.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(dossier_md)
        
    logger.info(f"Successfully wrote 25-section dossier to {output_path}")

if __name__ == "__main__":
    asyncio.run(run_live_verification())
