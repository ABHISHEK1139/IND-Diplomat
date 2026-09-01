import logging
from typing import Dict, Any

from .dossier.composer import DossierComposer
from .explainability.tracer import ExplainabilityTracer
from .dashboard.metrics import DashboardMetrics
from .exports.exporter import MultiFormatExporter

logger = logging.getLogger("DIP3.Layer6.WorkspaceOrchestrator")

class WorkspaceOrchestrator:
    """
    Phase 6: Intelligence Dossier & Analyst Workspace
    Turns all intelligence into a living, interactive workspace.
    """
    def __init__(self):
        logger.info("Workspace Orchestrator initialized.")
        self.composer = DossierComposer()
        self.tracer = ExplainabilityTracer()
        self.metrics = DashboardMetrics()
        self.exporter = MultiFormatExporter()

    async def run(self, investigation: Any, simulation_results: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Building intelligence workspace for {investigation.investigation_id}")
        
        # 1. Compose the Dossier
        dossier = self.composer.build_dossier(investigation.investigation_id, simulation_results)
        
        # 2. Add Explainability Traces
        traced_dossier = self.tracer.trace(dossier)
        
        # 3. Compute Live Dashboard Metrics
        dash_metrics = self.metrics.compute_metrics(investigation)
        
        # 4. Generate Default Exports
        export_path = self.exporter.export(traced_dossier, format="json")
        
        return {
            "status": "success",
            "dossier": traced_dossier,
            "metrics": dash_metrics,
            "export_path": export_path
        }
