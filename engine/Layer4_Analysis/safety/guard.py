"""
Llama Guard Integration for IND-Diplomat
Provides content safety classification using Llama Guard 3.
"""

import os
from typing import Dict, Any, Tuple, List
from enum import Enum


class SafetyCategory(Enum):
    """Safety categories for content classification."""
    SAFE = "safe"
    UNSAFE_VIOLENCE = "S1"  # Violence and Hate
    UNSAFE_SEXUAL = "S2"    # Sexual Content
    UNSAFE_CRIMINAL = "S3"  # Criminal Planning
    UNSAFE_WEAPONS = "S4"   # Weapons/Dangerous Materials
    UNSAFE_REGULATED = "S5" # Regulated Substances
    UNSAFE_SELF_HARM = "S6" # Self-Harm
    UNSAFE_PRIVACY = "S7"   # Privacy Violations
    UNSAFE_DEFAMATION = "S8" # Defamation
    UNSAFE_ELECTION = "S9"  # Election Interference
    UNSAFE_CODE = "S10"     # Code Exploits
    INJECTION = "S11"       # Prompt Injection


class LlamaGuard:
    """
    Production-grade Llama Guard integration with:
    1. Real Llama Guard 3 via Ollama (when available)
    2. Fallback pattern-based classification
    3. Detailed safety category reporting
    """
    
    def __init__(self):
        self.model_name = os.getenv("LLAMA_GUARD_MODEL", "llama-guard3:8b")
        self.ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._model_available = False
        
        # Enhanced injection patterns
        self.injection_patterns = [
            r"ignore\s+(previous|all|your)\s+instructions",
            r"forget\s+(everything|all|your)",
            r"you\s+are\s+now\s+a",
            r"system\s*:\s*",
            r"override\s+your\s+programming",
            r"act\s+as\s+if",
            r"pretend\s+(you\s+are|to\s+be)",
            r"<\/?system>",
            r"\[INST\]|\[\/INST\]",
            r"###\s*(instruction|system|human|assistant)",
            r"disregard\s+all",
            r"new\s+instructions",
            r"jailbreak",
            r"DAN\s+mode",
            r"developer\s+mode",
        ]
        
        # Dangerous content patterns by category
        self.category_patterns = {
            SafetyCategory.UNSAFE_VIOLENCE: [
                r"(kill|murder|assassinate|bomb|attack)\s+(the|a|people|target)",
                r"how\s+to\s+(hurt|harm|injure)",
            ],
            SafetyCategory.UNSAFE_CRIMINAL: [
                r"how\s+to\s+(hack|break\s+into|steal)",
                r"plan\s+a\s+(robbery|heist|attack)",
            ],
            SafetyCategory.UNSAFE_PRIVACY: [
                r"(personal|private)\s+(data|information)\s+of",
                r"doxx|doxing",
                r"(home\s+address|phone\s+number)\s+of",
            ],
            SafetyCategory.UNSAFE_ELECTION: [
                r"(spread|create)\s+(misinformation|fake\s+news)\s+about\s+elections?",
                r"manipulate\s+(votes?|voting|election)",
            ],
        }
        
        self._check_model_availability()
    
    def _check_model_availability(self):
        """Checks if Llama Guard model is available via Ollama."""
        try:
            import requests
            response = requests.get(f"{self.ollama_base}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                self._model_available = any("guard" in name.lower() for name in model_names)
                if self._model_available:
                    print(f"[LlamaGuard] Model available via Ollama")
        except Exception as e:
            print(f"[LlamaGuard] Model check failed: {e}. Using pattern-based fallback.")
            self._model_available = False
    
    async def classify_content(self, content: str, role: str = "user") -> Dict[str, Any]:
        """
        Classifies content safety using Llama Guard.
        Returns: {is_safe, category, confidence, reason}
        """
        # Try real Llama Guard first
        if self._model_available:
            try:
                return await self._classify_with_llama_guard(content, role)
            except Exception as e:
                print(f"[LlamaGuard] Model call failed: {e}")
        
        # Fallback to pattern-based
        return self._classify_with_patterns(content)

    async def check(self, content: str) -> Dict[str, Any]:
        """Alias for classify_content for wrapper compatibility."""
        result = await self.classify_content(content)
        return {
            "safe": result.get("is_safe", True), 
            "category": getattr(result.get("category"), "value", "safe") if hasattr(result.get("category"), "value") else str(result.get("category", "safe")),
            "reason": result.get("reason", "")
        }
    
    async def _classify_with_llama_guard(self, content: str, role: str) -> Dict[str, Any]:
        """Classifies using actual Llama Guard model."""
        from engine.Layer4_Analysis.core.llm_client import llm_client
        
        # Llama Guard 3 prompt format
        prompt = f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if there is unsafe content in '{role}' messages in conversations according to our safety policy.

<BEGIN CONVERSATION>

{role}: {content}

<END CONVERSATION>

Provide your safety assessment for {role} in the above conversation:
- First line must read 'safe' or 'unsafe'.
- If unsafe, a second line must include a comma-separated list of violated categories.<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
        
        response = await llm_client.generate(
            prompt,
            system_prompt="You are a content safety classifier.",
            query_type="factual"
        )
        
        return self._parse_guard_response(response)
    
    def _parse_guard_response(self, response: str) -> Dict[str, Any]:
        """Parses Llama Guard response."""
        lines = response.strip().lower().split('\n')
        
        if not lines:
            return {"is_safe": True, "category": SafetyCategory.SAFE, "confidence": 0.5, "reason": "Empty response"}
        
        is_safe = lines[0].strip() == "safe"
        
        if is_safe:
            return {
                "is_safe": True,
                "category": SafetyCategory.SAFE,
                "confidence": 0.95,
                "reason": "Content classified as safe"
            }
        
        # Parse unsafe categories
        categories = []
        if len(lines) > 1:
            category_line = lines[1].strip()
            for cat in SafetyCategory:
                if cat.value.lower() in category_line:
                    categories.append(cat)
        
        primary_category = categories[0] if categories else SafetyCategory.UNSAFE_VIOLENCE
        
        return {
            "is_safe": False,
            "category": primary_category,
            "all_categories": categories,
            "confidence": 0.9,
            "reason": f"Content violates safety policy: {primary_category.value}"
        }
    
    def _classify_with_patterns(self, content: str) -> Dict[str, Any]:
        """Pattern-based classification fallback."""
        import re
        content_lower = content.lower()
        
        # Check for injection first
        for pattern in self.injection_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return {
                    "is_safe": False,
                    "category": SafetyCategory.INJECTION,
                    "confidence": 0.85,
                    "reason": "Potential prompt injection detected"
                }
        
        # Check category patterns
        for category, patterns in self.category_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    return {
                        "is_safe": False,
                        "category": category,
                        "confidence": 0.75,
                        "reason": f"Pattern match for {category.value}"
                    }
        
        return {
            "is_safe": True,
            "category": SafetyCategory.SAFE,
            "confidence": 0.8,
            "reason": "No unsafe patterns detected"
        }
    
    def is_model_available(self) -> bool:
        return self._model_available


# Singleton instance
llama_guard = LlamaGuard()
