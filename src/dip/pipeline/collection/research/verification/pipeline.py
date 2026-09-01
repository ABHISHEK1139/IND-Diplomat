"""
Politiq AI — Verification Pipeline
==================================

Transforms raw extracted Documents into highly structured, verified Evidence.
Includes Normalization, Source Scoring, Bias Estimation, and CAMEO Tagging.
"""

import json
import logging
import litellm
from typing import List, Optional

from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json
from dip.pipeline.collection.research.schemas import Document, Evidence

logger = logging.getLogger("Research.VerificationPipeline")


class VerificationPipeline:
    """Multi-stage pipeline to evaluate and verify Documents into Evidence."""

    def __init__(self):
        self.model = config.LLM_MODEL

    async def verify(self, documents: List[Document], query_context: str) -> List[Evidence]:
        """
        Run the verification pipeline on a list of Documents.
        
        Args:
            documents: List of crawled and extracted Document objects.
            query_context: Context string about what we are researching.
            
        Returns:
            List of structured Evidence objects.
        """
        evidence_list: List[Evidence] = []
        
        for doc in documents:
            ev = await self._verify_single(doc, query_context)
            if ev:
                evidence_list.append(ev)
                
        return evidence_list

    async def _verify_single(self, doc: Document, context: str) -> Optional[Evidence]:
        """Verify a single document using an LLM prompt to perform all 4 steps."""
        prompt = (
            "You are an expert intelligence analyst and evidence verifier.\n"
            f"Context of research: {context}\n\n"
            "Analyze the following extracted document:\n"
            f"Title: {doc.title}\n"
            f"URL: {doc.url}\n"
            f"Text snippet (truncated for analysis):\n{doc.clean_text[:3000]}\n\n"
            "Perform the following verifications and return a JSON object:\n"
            "1. Normalizer: Identify the true publisher/source name.\n"
            "2. Scorer: Estimate reliability_score (0.0 to 1.0) based on source reputation and objective tone.\n"
            "3. BiasEstimator: Estimate bias_score (-1.0 to 1.0) where -1 is heavily anti-establishment/left, +1 is heavily pro/right, and 0 is neutral.\n"
            "4. FactChecker: Estimate confidence (0.0 to 1.0) that the text addresses the research context factually.\n"
            "5. CAMEOTagger: Assign a primary CAMEO conflict code if applicable (e.g., '190' for military attack, '010' for statement, '040' for consult), else null.\n"
            "6. Summary: Provide a 1-3 sentence verified text summary of the critical facts.\n\n"
            "Return EXACTLY this JSON format:\n"
            "{\n"
            '  "publisher": "Name",\n'
            '  "reliability_score": 0.8,\n'
            '  "bias_score": 0.1,\n'
            '  "confidence": 0.9,\n'
            '  "cameo_code": "010",\n'
            '  "verified_text": "The summarized facts..."\n'
            "}"
        )

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            raw = response.choices[0].message.content.strip()
            raw = strip_markdown_json(raw)
            parsed = json.loads(raw)
            
            # Construct Evidence
            return Evidence(
                title=doc.title,
                url=doc.url,
                publisher=parsed.get("publisher", "Unknown"),
                country=None,  # Could add extraction for this later
                reliability_score=float(parsed.get("reliability_score", 0.5)),
                bias_score=float(parsed.get("bias_score", 0.0)),
                confidence=float(parsed.get("confidence", 0.5)),
                cameo_code=parsed.get("cameo_code"),
                language=doc.language,
                text=parsed.get("verified_text", doc.clean_text[:500])
            )
            
        except Exception as e:
            logger.error(f"Verification failed for {doc.url}: {e}")
            # Fallback to basic Evidence if LLM fails
            return Evidence(
                title=doc.title,
                url=doc.url,
                publisher="Unknown",
                reliability_score=0.5,
                bias_score=0.0,
                confidence=0.1,
                text=doc.clean_text[:500] + "..."
            )
