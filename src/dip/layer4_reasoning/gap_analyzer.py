import logging
import json
from dip.core.json_utils import strip_markdown_json, safe_parse_json
from typing import List
from litellm import completion
from dip.core.schema import StateContext, IntelligenceGap
from dip.Config.config import Config

logger = logging.getLogger("Layer4.GapAnalyzer")

class GapAnalyzer:
    """
    Identifies intelligence blindspots and collection gaps from the current StateContext.
    Calculates expected information gain for prioritization.
    """
    
    def __init__(self):
        self.model = getattr(Config, "PRIMARY_MODEL", "gemini/gemini-2.5-pro")
        
    async def analyze_gaps(self, context: StateContext) -> List[IntelligenceGap]:
        logger.info("Analyzing intelligence gaps...")
        
        if not context.current_signals:
            return [IntelligenceGap(
                missing_information="No signals available.",
                domain="All",
                priority="Critical",
                expected_information_gain=1.0
            )]
            
        signals_summary = "\n".join([f"- {s.action} ({s.domain}): {s.intensity}" for s in context.current_signals])
        
        prompt = f"""
        You are a senior intelligence gap analyst. Review the following verified signals for the target '{context.country}':
        
        {signals_summary}
        
        Identify critical blindspots or missing information that prevents higher confidence assessments.
        Consider missing pieces in military logistics, cyber reconnaissance, economic transfers, or diplomatic backchannels.
        
        Output a strict JSON array of objects with the following keys:
        - "missing_information": string (description of what is missing)
        - "domain": string (military, diplomatic, economic, cyber, information)
        - "priority": string (Low, Medium, High, Critical)
        - "expected_information_gain": float (0.0 to 1.0, how much this would increase our confidence)
        
        Only output the JSON array.
        """
        
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"} # Some models require {"type": "json_schema"} but we'll extract manually if needed
            )
            
            content = response.choices[0].message.content
            # Clean markdown code blocks if present
            content = strip_markdown_json(content)
                
            # If wrapped in an object like {"gaps": [...]}, handle it
            data = json.loads(content)
            gaps_data = data if isinstance(data, list) else (data.get("gaps", []) or data.get("intelligence_gaps", []))
            
            gaps = []
            for item in gaps_data:
                gaps.append(IntelligenceGap(
                    missing_information=item.get("missing_information", "Unknown gap"),
                    domain=item.get("domain", "Unknown"),
                    priority=item.get("priority", "Medium"),
                    expected_information_gain=float(item.get("expected_information_gain", 0.5))
                ))
            
            return gaps
            
        except Exception as e:
            logger.error(f"Failed to analyze gaps: {e}")
            return []
