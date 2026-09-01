import logging
from typing import Dict, Any

from .evaluation.deep_evaluator import DeepEvaluator
from .monitoring.langfuse_tracer import LangfuseTracer
from .human_feedback.feedback_ingestor import FeedbackIngestor
from .dataset.dataset_builder import DatasetBuilder
from .training.unsloth_finetuner import UnslothFineTuner

logger = logging.getLogger("DIP3.Layer7.LearningOrchestrator")

class LearningOrchestrator:
    """
    Phase 7: Self-Evolution & Human Learning Loop
    """
    def __init__(self):
        logger.info("Learning Orchestrator initialized.")
        self.evaluator = DeepEvaluator()
        self.tracer = LangfuseTracer()
        self.ingestor = FeedbackIngestor()
        self.dataset_builder = DatasetBuilder()
        self.finetuner = UnslothFineTuner()

    async def run_learning_loop(self, investigation: Any, dossier: Dict[str, Any], query: str, context: list, human_edits: list):
        logger.info(f"Triggering learning loop for {investigation.investigation_id}")
        
        # 1. Evaluate output quality
        eval_metrics = self.evaluator.evaluate_dossier(query=query, context=context, generated_output=dossier)
        
        # 2. Log to Langfuse
        self.tracer.log_run(investigation.investigation_id, eval_metrics)
        
        # 3. Ingest Human Feedback
        self.ingestor.ingest(human_edits)
        
        # 4. Compile SFT/DPO datasets
        self.dataset_builder.build_records(human_edits)
        
        # 5. Check if we have enough data to trigger an auto-finetune run
        training_result = self.finetuner.check_and_train("data/datasets")
        
        return {
            "eval_metrics": eval_metrics,
            "training_result": training_result,
        }

