from dip.Config.config import config
"""
Signal Extractor (Layer 2)
==========================
Uses LLM to semantically parse raw observations into structured signals.
"""

import os
import json
import logging
from typing import List

try:
    import litellm
except ImportError:
    litellm = None

from dotenv import load_dotenv
from dip.core.json_utils import strip_markdown_json
from dip.core.schema import RawObservation, Signal, Entity, Claim
from dip.layer10_telemetry.llm_tracer import tracer

load_dotenv()

logger = logging.getLogger("Layer2.signal_extractor")
LLM_MODEL = config.LLM_MODEL

SOURCE_TIERS = {
    "SOCIAL": 0.30,
    "NEWS": 0.55,
    "OSINT": 0.55,
    "GOV": 0.75,
    "DATASET": 0.90,
}


class SignalExtractor:
    async def extract(self, observations: List[RawObservation]) -> dict:
        if not observations:
            return {"signals": [], "entities": [], "claims": []}
            
        if litellm is None:
            logger.error("litellm not installed, cannot extract signals semantically.")
            return {"signals": [], "entities": [], "claims": []}

        if os.getenv("FORCE_MINISTER_HEURISTIC") == "1":
            return {
                "signals": [Signal(entity="Test", action="TEST_ACTION", intensity=0.5, confidence=0.8, source_ref="test")],
                "entities": [Entity(entity_id="TEST-1", name="Test", type="COUNTRY", mentions=1)],
                "claims": [Claim(claim_id="C-1", subject="Test", predicate="Tested", object="Test", claim="Tested", confidence=0.8, source_ref="test")]
            }

        # Batch observations to save tokens, max 10 per batch
        batches = [observations[i:i+10] for i in range(0, len(observations), 10)]
        all_signals = []
        
        for batch in batches:
            obs_json = [{"id": i, "content": obs.content, "source": obs.source_type} for i, obs in enumerate(batch)]
            all_entities = []
            all_claims = []
            
            try:
            
                prompt = (
                    "You are an expert intelligence parser. Extract knowledge from the following observations.\n"
                    f"Observations:\n{json.dumps(obs_json, indent=2)}\n\n"
                    "Return a JSON object with three keys: 'signals', 'entities', and 'claims'.\n"
                    "'signals' must be an array where each object has:\n"
                    "  - 'obs_id': The ID of the source observation.\n"
                    "  - 'entity': The primary actor country (ISO-3).\n"
                    "  - 'action': Event code (e.g., SIG_MIL_ESCALATION, SIG_ECONOMIC_SANCTIONS).\n"
                    "  - 'target': The target country (ISO-3) or null.\n"
                    "  - 'intensity': Float 0.0 to 1.0.\n"
                    "'entities' must be an array where each object has:\n"
                    "  - 'entity_id': Unique string ID.\n"
                    "  - 'name': Human readable name.\n"
                    "  - 'type': e.g., 'Person', 'Organization', 'Location'.\n"
                    "'claims' must be an array where each object has:\n"
                    "  - 'claim_id': Unique string ID.\n"
                    "  - 'subject': The entity making the claim or being described.\n"
                    "  - 'predicate': The relationship or action.\n"
                    "  - 'object': The target of the claim.\n"
                    "  - 'confidence': Float 0.0 to 1.0.\n"
                    "  - 'source_ref': 'obs_id' as a string.\n"
                )

                response = await tracer.acompletion(
                    layer="Layer2_SignalExtractor",
                    model=LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("LLM returned empty or None content")
                raw = strip_markdown_json(content)
                
                parsed = json.loads(raw)
                
                # Parse Signals
                for item in parsed.get("signals", []):
                    obs_id = item.get("obs_id")
                    if obs_id is not None and 0 <= int(obs_id) < len(batch):
                        original_obs = batch[int(obs_id)]
                        conf = SOURCE_TIERS.get(original_obs.source_type, 0.5)
                        sig = Signal(
                            entity=item.get("entity", "UNKNOWN"),
                            action=item.get("action", "SIG_UNKNOWN"),
                            target=item.get("target"),
                            intensity=float(item.get("intensity", 0.5)),
                            confidence=conf,
                            source_ref=original_obs.source_id,
                            timestamp=original_obs.timestamp
                        )
                        all_signals.append(sig)
                
                # Parse Entities
                for item in parsed.get("entities", []):
                    all_entities.append(Entity(
                        entity_id=item.get("entity_id", "UNK"),
                        name=item.get("name", "Unknown"),
                        type=item.get("type", "Unknown")
                    ))
                    
                # Parse Claims
                for item in parsed.get("claims", []):
                    all_claims.append(Claim(
                        claim_id=item.get("claim_id", "UNK"),
                        subject=item.get("subject", "Unknown"),
                        predicate=item.get("predicate", "Unknown"),
                        object=item.get("object", "Unknown"),
                        confidence=float(item.get("confidence", 0.5)),
                        source_ref=item.get("source_ref", "Unknown")
                    ))
                        
            except Exception as e:
                logger.error(f"Failed to extract signals via LLM: {e}")
                
        # Noise Filtering (Echo Chamber Mitigation)
        # Filter mirrored reports as a single source if entity, action, and target match
        unique_signals = {}
        for sig in all_signals:
            # Create a semantic fingerprint for the event
            fingerprint = f"{sig.entity}_{sig.action}_{sig.target}"
            if fingerprint not in unique_signals:
                unique_signals[fingerprint] = sig
            else:
                # Merge mirrored reports (boost confidence slightly due to multiple outlets, but treat as one signal)
                existing = unique_signals[fingerprint]
                existing.confidence = min(1.0, existing.confidence + 0.05)
                # Keep the highest intensity
                existing.intensity = max(existing.intensity, sig.intensity)
                
        return {
            "signals": list(unique_signals.values()),
            "entities": all_entities,
            "claims": all_claims
        }
