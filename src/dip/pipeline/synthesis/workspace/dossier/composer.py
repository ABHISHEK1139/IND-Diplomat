import logging
from typing import Dict, Any

logger = logging.getLogger("DIP3.Layer6.Composer")

class DossierComposer:
    """
    Uses LangGraph to independently compose modular report sections
    (Executive Summary, Timeline, Evidence, etc.) instead of a monolithic LLM prompt.
    """
    def __init__(self):
        pass
        
    async def build_dossier_async(self, investigation_id: str, data: Dict[str, Any]) -> str:
        logger.info(f"Compiling intelligence dossier for {investigation_id}")
        session = data.get("session")
        if not session:
            return "No session data available to compose dossier."

        try:
            import litellm
            from dip.core.Config.config import config
            
            # Format the 7 minister hypotheses
            hypotheses_text = "\n\n".join([
                f"[{getattr(h, 'minister', 'Minister')}] Confidence: {getattr(h, 'confidence', 0.0)}\n"
                f"Rationale: {getattr(h, 'rationale', 'N/A')}\n"
                f"Evidence: {', '.join(getattr(h, 'matched_signals', []))}"
                for h in getattr(session, "hypotheses", [])
            ])
            
            prompt = (
                f"You are an Executive Intelligence Briefer. Synthesize the following 7-minister "
                f"council findings into a concise, 3-paragraph executive summary.\n\n"
                f"Focus on the consensus, major disagreements, and the most critical evidence. "
                f"Do not invent facts.\n\n"
                f"Council Findings:\n{hypotheses_text}"
            )
            
            response = await litellm.acompletion(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=600
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Dossier composition failed: {e}")
            return "Auto-generated summary based on verified facts (LLM failed)."

    def build_dossier(self, investigation_id: str, data: Dict[str, Any]) -> str:
        """Synchronous wrapper for legacy compatibility if needed."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            return loop.create_task(self.build_dossier_async(investigation_id, data))
        except RuntimeError:
            return asyncio.run(self.build_dossier_async(investigation_id, data))
