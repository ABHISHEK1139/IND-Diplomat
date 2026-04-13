
from typing import List, Dict, Any, Tuple
import logging

from engine.Layer4_Analysis.core.context_curator import (
    build_red_team_query_pack,
    build_red_team_refinement_pack,
)
from engine.Layer4_Analysis.core.intelligence_controller import (
    recommend_stage_output_budget,
    stage_budget_instruction,
)

logger = logging.getLogger(__name__)

class RedTeamAgent:
    """
    State-grounded Red Team Agent.

    Challenges hypotheses using StateContext signals — NOT raw documents.
    Layer-4 must never read documents directly; all counter-evidence
    comes from measured world state (contradictions, weak signals,
    insufficient confidence).

    Capabilities:
    1. LLM-based attack vector generation (from draft answer text)
    2. StateContext contradiction and weakness detection
    3. Structured critique generation
    4. Safe answer refinement
    """

    def __init__(self, state_context: Dict[str, Any] = None):
        self.state_context = state_context or {}
        self.minister_context: str = ""     # Populated by coordinator with minister reasoning
        self.disagreement_detected: bool = False
        self.attack_prompts = [
            "Find evidence that contradicts: {claim}",
            "What are the risks or downsides of: {claim}",
            "Historical failures related to: {claim}",
            "Critics and opposing viewpoints on: {claim}"
        ]

    def set_state_context(self, state_context: Dict[str, Any]) -> None:
        """Update the state context for the next challenge round."""
        self.state_context = state_context or {}

    @staticmethod
    def _extract_json_from_llm(raw: str) -> Any:
        """
        Robust JSON extraction from LLM output.

        Handles deepseek-r1 <think> blocks, markdown code fences,
        and surrounding narrative text.  Falls back to brace-matching
        when simple stripping fails.
        """
        import json
        import re

        text = str(raw or "").strip()
        if not text:
            return None

        # 1. Strip <think>...</think> reasoning blocks
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # 2. Extract content inside code fences (if present anywhere)
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        # 3. Try direct parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # 4. Find outermost { ... } block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass

        # 5. Find outermost [ ... ] block (for array responses)
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass

        return None

    async def generate_counter_arguments(self, draft_answer: str) -> List[str]:
        """
        Generates attack queries using LLM reasoning.
        Falls back to template-based generation if LLM unavailable.
        """
        from engine.Layer4_Analysis.core.llm_client import llm_client

        logger.info("[Red Team] Generating attack vectors for draft answer...")

        try:
            pack = build_red_team_query_pack(
                draft_answer=draft_answer,
                state_context=self.state_context,
                minister_context=self.minister_context,
                output_schema=(
                    '{\n'
                    '  "queries": [\n'
                    '    "query to contradict",\n'
                    '    "query to find risks",\n'
                    '    "query to surface alternative perspective"\n'
                    "  ]\n"
                    "}"
                ),
            )
            max_budget = recommend_stage_output_budget(
                "red_team",
                int(pack.output_budget or 0) or 1200,
                disagreement_detected=self.disagreement_detected,
            )
            system_prompt = (
                "You are a critical analyst. Return ONLY valid JSON."
                f" {stage_budget_instruction('red_team', disagreement_detected=self.disagreement_detected)}"
            ).strip()

            response = await llm_client.generate(
                pack.render(),
                system_prompt=system_prompt,
                query_type="factual",
                json_mode=True,
                max_tokens=max_budget,
                task_type="red_team",
                context_pack=pack,
            )

            parsed = None
            if isinstance(response, str):
                parsed = self._extract_json_from_llm(response)

            queries = []
            if isinstance(parsed, dict):
                raw_list = parsed.get("queries", [])
                if isinstance(raw_list, str):
                    raw_list = [raw_list]
                if isinstance(raw_list, list):
                    queries = [q.strip() for q in raw_list if str(q or "").strip()]

            if not queries:
                raise ValueError(f"Bad JSON or empty queries: {response}")

            logger.info("[Red Team] Generated %d LLM-based attack queries", len(queries))
            return queries[:3]

        except Exception as e:
            logger.warning("[Red Team] LLM generation failed, using template fallback: %s", e)
            # Fallback to template-based
            return self._template_based_attacks(draft_answer)

    def _template_based_attacks(self, draft_answer: str) -> List[str]:
        """Template-based attack generation fallback."""
        # Extract key terms from answer
        keywords = []
        key_terms = ["agreement", "treaty", "policy", "trade", "security", "alliance", "beneficial", "risk"]
        for term in key_terms:
            if term in draft_answer.lower():
                keywords.append(term)

        attack_queries = []
        subject = draft_answer[:50].replace("\n", " ")

        if "beneficial" in draft_answer.lower():
            attack_queries.append(f"Negative impacts and risks of {subject}")
            attack_queries.append(f"Failures and criticisms of {subject}")

        if "trade" in draft_answer.lower():
            attack_queries.append(f"Trade disputes and violations related to {subject}")

        if not attack_queries:
            attack_queries.append(f"Counter-evidence and opposing views on {subject}")
            attack_queries.append(f"Historical failures similar to {subject}")

        return attack_queries

    async def execute_attack(self, draft_answer: str) -> Tuple[bool, str, List[str]]:
        """
        Executes the Red Team challenge loop using StateContext signals.

        Instead of searching raw documents, this method:
        1. Generates attack vectors (LLM or template)
        2. Checks the StateContext for contradictions, low confidence,
           and signals that weaken the draft answer
        3. Produces a structured critique grounded in measured state

        Returns: (is_robust, critique, counter_evidence_summaries)
        """
        # 1. Generate Attack Vectors
        attack_vectors = await self.generate_counter_arguments(draft_answer)

        if not attack_vectors:
            return True, "No attack vectors generated.", []

        # 2. Check StateContext for contradictions and weaknesses
        counter_evidence = []

        # Extract state dimensions
        military = self.state_context.get("military", {}) or {}
        diplomatic = self.state_context.get("diplomatic", {}) or {}
        economic = self.state_context.get("economic", {}) or {}
        domestic = self.state_context.get("domestic", {}) or {}
        meta = self.state_context.get("meta", {}) or {}

        draft_lower = draft_answer.lower()

        # Challenge 1: Draft claims military aggression but state shows low mobilization
        if any(kw in draft_lower for kw in ["invasion", "military", "attack", "war"]):
            mob = float(military.get("mobilization_level", 0) or 0)
            if mob < 0.4:
                counter_evidence.append(
                    f"STATE CONTRADICTION: Draft implies military threat but mobilization_level={mob:.2f} "
                    f"(below 0.40 threshold). State does not support military aggression hypothesis."
                )

        # Challenge 2: Draft claims diplomacy/peace but hostility is high
        if any(kw in draft_lower for kw in ["peace", "diplomatic", "negotiat", "cooperat"]):
            hostility = float(diplomatic.get("hostility_tone", 0) or 0)
            if hostility > 0.6:
                counter_evidence.append(
                    f"STATE CONTRADICTION: Draft implies diplomatic resolution but hostility_tone={hostility:.2f} "
                    f"(above 0.60). Measured diplomatic reality suggests ongoing tension."
                )

        # Challenge 3: Low data confidence undermines any strong conclusion
        data_conf = float(meta.get("data_confidence", 0.5) or 0.5)
        if data_conf < 0.5:
            counter_evidence.append(
                f"CONFIDENCE WARNING: data_confidence={data_conf:.2f} is below 0.50. "
                f"Any strong conclusion is inadequately supported by available evidence."
            )

        # Challenge 4: Draft claims economic stability but sanctions/pressure are high
        if any(kw in draft_lower for kw in ["stable", "economic growth", "trade benefit"]):
            sanctions = float(economic.get("sanctions", 0) or 0)
            econ_pressure = float(economic.get("economic_pressure", 0) or 0)
            if sanctions > 0.5 or econ_pressure > 0.5:
                counter_evidence.append(
                    f"STATE CONTRADICTION: Draft implies economic stability but sanctions={sanctions:.2f}, "
                    f"economic_pressure={econ_pressure:.2f}. Measured economic state suggests pressure."
                )

        # Challenge 5: Domestic instability not reflected in draft
        regime_stability = float(domestic.get("regime_stability", 0.5) or 0.5)
        unrest = float(domestic.get("unrest", 0) or 0)
        if regime_stability < 0.4 or unrest > 0.6:
            if not any(kw in draft_lower for kw in ["domestic", "unrest", "instability", "protest"]):
                counter_evidence.append(
                    f"MISSING FACTOR: regime_stability={regime_stability:.2f}, unrest={unrest:.2f} "
                    f"but draft does not address domestic instability as a causal factor."
                )

        # Challenge 6: Low source count weakens confidence
        source_count = int(meta.get("source_count", 0) or 0)
        if source_count < 5:
            counter_evidence.append(
                f"EVIDENCE THINNESS: Only {source_count} sources available. "
                f"Conclusions based on sparse evidence may be unreliable."
            )

        # ── Fix 6: NEW CHALLENGE CATEGORIES ──────────────────────────

        # Challenge 7: Contradictory signals — both diplomacy active
        # AND diplomatic hostility suggest incoherent signal environment
        signal_conf = self.state_context.get("signal_confidence", {}) or {}
        diplomacy_str = float(signal_conf.get("SIG_DIPLOMACY_ACTIVE", 0) or 0)
        hostility_str = float(signal_conf.get("SIG_DIP_HOSTILITY", 0) or 0)
        if diplomacy_str > 0.40 and hostility_str > 0.40:
            counter_evidence.append(
                f"CONTRADICTORY SIGNALS: SIG_DIPLOMACY_ACTIVE={diplomacy_str:.2f} and "
                f"SIG_DIP_HOSTILITY={hostility_str:.2f} are both elevated. These signals "
                f"are analytically contradictory — the situation may be more ambiguous "
                f"than the assessment reflects. Consider whether coercive diplomacy or "
                f"dual-track signaling explains the pattern."
            )

        # Challenge 8: Source monoculture — if all signals come from
        # one type of source, conclusions may have systematic bias
        observed_signals = self.state_context.get("observed_signals", set()) or set()
        signal_sources = self.state_context.get("signal_sources", {}) or {}
        _all_sources = set()
        for _src_list in signal_sources.values():
            if isinstance(_src_list, (list, set)):
                _all_sources.update(str(s).lower() for s in _src_list)
        if _all_sources:
            _osint_sources = {s for s in _all_sources if any(
                kw in s for kw in ["gdelt", "moltbot", "news", "osint", "derived"]
            )}
            if len(_osint_sources) == len(_all_sources) and len(_all_sources) >= 2:
                counter_evidence.append(
                    f"SOURCE MONOCULTURE: All {len(_all_sources)} sources are OSINT/news-derived. "
                    f"No SIGINT, HUMINT, or official-channel sources detected. "
                    f"Assessment may have systematic media-narrative bias."
                )

        # Challenge 9: Causal logic gap — economic signals dominating
        # military conclusion without military corroboration
        econ_strength = max(
            float(economic.get("sanctions", 0) or 0),
            float(economic.get("economic_pressure", 0) or 0),
        )
        mob_strength = float(military.get("mobilization_level", 0) or 0)
        if econ_strength > 0.50 and mob_strength < 0.25:
            if any(kw in draft_lower for kw in ["military escalation", "armed conflict", "war"]):
                counter_evidence.append(
                    f"CAUSAL GAP: Assessment implies military escalation but evidence is "
                    f"primarily economic (sanctions={econ_strength:.2f}, "
                    f"mobilization={mob_strength:.2f}). Economic pressure historically "
                    f"correlates weakly with military escalation without concurrent "
                    f"military posture changes. The causal chain is underspecified."
                )

        # Challenge 10: Historical outlier — compare current assessment
        # to rolling SRE history
        try:
            import json as _json
            import os as _os
            _sre_path = _os.path.join(
                _os.path.dirname(__file__), "..", "..", "data", "sre_history.json"
            )
            if _os.path.exists(_sre_path):
                with open(_sre_path, "r") as _f:
                    _sre_data = _json.load(_f)
                _sre_values = _sre_data.get("values", [])
                if len(_sre_values) >= 5:
                    _mean = sum(_sre_values) / len(_sre_values)
                    _variance = sum((v - _mean) ** 2 for v in _sre_values) / len(_sre_values)
                    _std = _variance ** 0.5 if _variance > 0 else 0.01
                    _current_sre = float(meta.get("sre_score", _mean) or _mean)
                    _z_score = abs(_current_sre - _mean) / max(_std, 0.01)
                    if _z_score > 2.0:
                        counter_evidence.append(
                            f"OUTLIER ASSESSMENT: Current SRE={_current_sre:.3f} deviates "
                            f"{_z_score:.1f}σ from rolling mean={_mean:.3f} (std={_std:.3f}). "
                            f"This is a statistical outlier — verify whether a genuine "
                            f"step-change occurred or if the assessment is anomalous."
                        )
        except Exception:
            pass  # SRE history not available — skip this check

        if not counter_evidence:
            return True, "Robust: No state-grounded contradictions found.", []

        # 3. Formulate Structured Critique
        critique = self._formulate_critique(draft_answer, counter_evidence)

        return False, critique, counter_evidence

    def _formulate_critique(self, draft: str, evidence: List[str]) -> str:
        """Formulates a structured critique based on state-grounded counter-evidence."""
        critique_parts = [
            f"VULNERABILITY ASSESSMENT (State-Grounded):",
            f"- Draft Answer: {draft[:100]}...",
            f"- State contradictions found: {len(evidence)}",
            f"",
            "KEY RISKS IDENTIFIED:"
        ]

        for i, ev in enumerate(evidence[:5]):
            critique_parts.append(f"  {i+1}. {ev}")

        critique_parts.append("")
        critique_parts.append("RECOMMENDATION: Revise answer to align with measured state reality.")

        return "\n".join(critique_parts)

    async def refine_answer_with_critique(self, draft_answer: str, critique: str, evidence: List[str]) -> str:
        """
        Refines the answer using LLM to address Red Team critique.
        """
        from engine.Layer4_Analysis.core.llm_client import llm_client

        try:
            pack = build_red_team_refinement_pack(
                draft_answer=draft_answer,
                critique=critique,
                evidence=evidence,
            )
            max_budget = recommend_stage_output_budget(
                "red_team_refine",
                int(pack.output_budget or 0) or 1200,
                disagreement_detected=self.disagreement_detected,
            )
            system_prompt = (
                "You are a senior diplomatic analyst. Return only the revised answer. Keep it concise and grounded. "
                f"{stage_budget_instruction('red_team_refine', disagreement_detected=self.disagreement_detected)}"
            ).strip()

            refined = await llm_client.generate(
                pack.render(),
                system_prompt=system_prompt,
                query_type="factual",
                max_tokens=max_budget,
                task_type="red_team_refine",
                context_pack=pack,
            )
            return refined

        except Exception as e:
            print(f"[Red Team] LLM refinement failed, using template: {e}")
            # Fallback to template refinement
            risk_summary = evidence[0][:100] if evidence else "potential risks exist"
            return f"{draft_answer}\n\nHowever, it is important to note that {risk_summary}. A balanced assessment should consider these factors."
