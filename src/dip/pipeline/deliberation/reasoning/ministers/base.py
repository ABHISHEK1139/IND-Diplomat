"""Abstract base minister with dual-mode reliability.

Ministers are hypothesis testers, not independent decision-makers. Each
minister first creates a deterministic proposal from StateContext and SRE, then
allows a schema-constrained LLM to refine it within explicit bounds.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import List

from dotenv import load_dotenv

from dip.core.Config.config import config
from dip.core.schema import (
    DualModeMinisterDecision,
    Hypothesis,
    MinisterHypothesisOutput,
    MinisterCritiqueOutput,
    MinisterRecalibrationOutput,
    DebateCritique,
    StateContext,
)
from dip.engines.structured_llm import structured_acompletion

load_dotenv()

LLM_MODEL = config.LLM_MODEL


class BaseMinister(ABC):
    """Abstract base for all hypothesis-testing ministers."""

    @property
    @abstractmethod
    def minister_name(self) -> str:
        """Human-readable name used in Hypothesis.minister field."""
        ...

    @property
    @abstractmethod
    def hypothesis_type(self) -> str:
        """The core question this minister tests."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt that frames the LLM as a hypothesis tester."""
        ...

    def _extract_signal_descriptions(self, ctx: StateContext) -> List[str]:
        """Flatten current signals into short human-readable strings."""

        descriptions: List[str] = []
        for sig in ctx.current_signals:
            desc = f"{sig.entity} {sig.action}"
            if sig.target:
                desc += f" targeting {sig.target}"
            desc += f" (intensity={sig.intensity:.2f}, confidence={sig.confidence:.2f})"
            descriptions.append(desc)
        return descriptions

    def _build_prediction_prompt(self, ctx: StateContext) -> str:
        """Build the user prompt that asks the LLM to predict and match signals."""

        signal_block = "\n".join(
            f"  - {signal}" for signal in self._extract_signal_descriptions(ctx)
        ) or "  (none)"
        conflicts_block = ", ".join(ctx.active_conflicts) or "(none)"
        history_block = json.dumps(ctx.historical_context, indent=2) if ctx.historical_context else "(none)"

        return (
            f"Country under analysis: {ctx.country}\n\n"
            f"Current observed signals:\n{signal_block}\n\n"
            f"Active conflicts: {conflicts_block}\n"
            f"Historical context: {history_block}\n\n"
            f"Hypothesis being tested: {self.hypothesis_type}\n\n"
            "Return only JSON matching MinisterHypothesisOutput:\n"
            "{ predicted_signals: string[], matched_signals: string[], "
            "missing_signals: string[], confidence: number, rationale: string, "
            "critical_signal_refs: string[] }\n"
        )

    def _heuristic_proposal(self, ctx: StateContext) -> MinisterHypothesisOutput:
        """Deterministic proposal. This is the rail the LLM must respect."""

        observed = self._extract_signal_descriptions(ctx)
        tokens = [
            token.strip(" ?-_").lower()
            for token in self.hypothesis_type.replace("/", " ").split()
            if len(token.strip(" ?-_")) > 3
        ]
        predicted = [f"expect_{token}_indicator" for token in tokens[:4]]
        if not predicted:
            predicted = [f"expect_{self.minister_name.lower().replace(' ', '_')}_indicator"]

        # Domain keywords for domain-sensitive hypothesis alignment
        domain_keywords = {
            "Security Minister": ["military", "defense", "troop", "weapon", "force", "alert", "patrol", "border", "navy", "air", "kinetic", "incursion", "posture"],
            "Diplomacy Minister": ["diplomatic", "treaty", "talk", "dialogue", "accord", "ambassador", "un", "bilateral", "statement", "negotiation", "disengagement"],
            "Economic Minister": ["economic", "trade", "sanction", "supply", "tariff", "export", "import", "market", "currency", "energy", "embargo"],
            "Strategy Minister": ["strategic", "escalation", "deterrence", "doctrine", "posture", "alliance", "long-term", "objective"],
            "Domestic Minister": ["domestic", "political", "public", "protest", "election", "civil", "unrest", "internal"],
            "Alliance Minister": ["alliance", "coalition", "partner", "nato", "quad", "bilateral", "pact", "joint"],
            "Contrarian Minister": ["alternative", "de-escalation", "routine", "exercise", "misinterpretation", "noise", "posturing"],
        }
        relevant_keywords = set(tokens + domain_keywords.get(self.minister_name, []))

        matched = []
        for item in observed:
            low = item.lower()
            if any(kw in low for kw in relevant_keywords):
                matched.append(item)
        matched = matched[:5]

        sre = getattr(ctx, "nextgen_sre", None)
        sre_score = float(getattr(sre, "sre_escalation_score", 0.0) or 0.0)
        
        weighted_signal_mass = 0.0
        max_source_tier = 1.0
        
        if ctx.current_signals:
            total_weight = 0.0
            for sig in ctx.current_signals:
                rel = getattr(sig, "reliability_score", 0.8) or 0.8
                src_ref = str(getattr(sig, "source_ref", "") or "").upper()
                
                # Check for official / high-tier source signatures
                if any(t in src_ref for t in ["DEFENSE", "GOV", "OFFICIAL", "TREATY", "UN_", "BULLETIN", "CACHE", "REUTERS", "AP"]):
                    tier_multiplier = 1.35
                    max_source_tier = max(max_source_tier, 1.35)
                elif rel >= 0.80:
                    tier_multiplier = 1.25
                    max_source_tier = max(max_source_tier, 1.25)
                elif rel >= 0.50:
                    tier_multiplier = 1.0
                else:
                    tier_multiplier = 0.70
                
                conf = float(getattr(sig, "confidence", 0.7) or 0.7)
                intensity = float(getattr(sig, "intensity", 0.5) or 0.5)
                
                sig_val = conf * max(intensity, 0.40) * tier_multiplier
                weighted_signal_mass += sig_val
                total_weight += tier_multiplier
            
            signal_pressure = weighted_signal_mass / max(total_weight, 1.0)
        else:
            signal_pressure = 0.0

        match_score = len(matched) / max(len(predicted), 1)
        
        # Base confidence calculation combining domain match, signal pressure, and source tier
        if matched and ctx.current_signals:
            base_conf = 0.45 + 0.30 * signal_pressure + 0.15 * min(1.0, match_score) + 0.10 * sre_score
            confidence = min(0.95, max(0.40, base_conf))
        elif ctx.current_signals:
            confidence = min(0.80, max(0.30, 0.45 * signal_pressure + 0.30 * sre_score))
        else:
            # Genuine absence of evidence -> properly conservative for epistemic refusal
            confidence = 0.15

        missing = [item for item in predicted if not any(item.lower() in m.lower() for m in matched)]

        return MinisterHypothesisOutput(
            predicted_signals=predicted,
            matched_signals=matched,
            missing_signals=missing,
            confidence=round(confidence, 3),
            rationale="Deterministic calibrated proposal from source-weighted signals, domain match, and SRE.",
        )

    def _build_refinement_prompt(self, ctx: StateContext, heuristic: MinisterHypothesisOutput) -> str:
        """Prompt the LLM to critique/refine, not decide independently."""

        return (
            f"{self._build_prediction_prompt(ctx)}\n\n"
            "DETERMINISTIC HEURISTIC PROPOSAL:\n"
            f"{heuristic.model_dump_json(indent=2)}\n\n"
            "You may refine predicted/matched/missing signals using qualitative context, "
            "but you are not the final decision-maker. Do not change confidence by more "
            "than +/- 0.15 unless you cite concrete critical signals in critical_signal_refs. "
            "Do not invent evidence outside StateContext."
        )

    async def _llm_refinement(
        self,
        ctx: StateContext,
        heuristic: MinisterHypothesisOutput,
    ) -> MinisterHypothesisOutput | None:
        return await structured_acompletion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self._build_refinement_prompt(ctx, heuristic)},
            ],
            output_model=MinisterHypothesisOutput,
            temperature=0.1,
            max_tokens=900,
        )

    def _merge_dual_mode(
        self,
        heuristic: MinisterHypothesisOutput,
        llm: MinisterHypothesisOutput | None,
    ) -> DualModeMinisterDecision:
        if llm is None:
            return DualModeMinisterDecision(
                minister=self.minister_name,
                hypothesis_type=self.hypothesis_type,
                heuristic=heuristic,
                final=heuristic,
                agreement_score=1.0,
                resolution_action="heuristic_only",
            )

        delta = float(llm.confidence) - float(heuristic.confidence)
        notes: List[str] = []
        final = llm.model_copy(deep=True)
        resolution = "llm_refined_within_bounds"

        if abs(delta) > 0.15 and not llm.critical_signal_refs:
            bounded = heuristic.confidence + (0.15 if delta > 0 else -0.15)
            final.confidence = round(max(0.0, min(1.0, bounded)), 3)
            notes.append(
                "LLM confidence delta exceeded +/-0.15 without critical signal references; confidence was bounded."
            )
            resolution = "bounded_llm_refinement"
        elif abs(delta) > 0.15 and llm.critical_signal_refs:
            notes.append(
                f"LLM confidence adjusted by {delta:+.2f} backed by critical signal references: {', '.join(llm.critical_signal_refs)}."
            )

        agreement = round(max(0.0, 1.0 - abs(final.confidence - heuristic.confidence)), 3)
        if agreement < 0.75:
            notes.append("Heuristic and LLM confidence materially disagree; verify before use.")


        return DualModeMinisterDecision(
            minister=self.minister_name,
            hypothesis_type=self.hypothesis_type,
            heuristic=heuristic,
            llm=llm,
            final=final,
            agreement_score=agreement,
            resolution_action=resolution,
            disagreement_notes=notes,
        )

    async def _autonomous_search(
        self,
        rfi_queries: List[str],
        state_context: StateContext,
    ) -> List[str]:
        """Execute per-minister autonomous web search for RFI-tagged queries.

        When a minister's LLM refinement includes critical_signal_refs prefixed
        with 'RFI:', this method fires targeted web searches and returns new
        evidence strings that get injected into the minister's signal context.
        """
        new_evidence: List[str] = []
        rfi_items = [q for q in rfi_queries if q.upper().startswith("RFI:")]

        if not rfi_items:
            return new_evidence

        try:
            from dip.pipeline.collection.research.retrieval.web_surfer import ResilientWebSurfer
            from dip.pipeline.knowledge.signal_extractor import SignalExtractor

            surfer = ResilientWebSurfer()
            extractor = SignalExtractor()
            country = getattr(state_context, "country", None)

            for rfi in rfi_items[:3]:  # Cap at 3 per minister to avoid runaway
                search_query = rfi.split(":", 1)[1].strip()
                observations = await surfer.search(
                    query=search_query,
                    country_code=country,
                    max_results=3,
                )
                for obs in observations:
                    desc = f"[{self.minister_name} RFI] {obs.content}"
                    new_evidence.append(desc)
                    # Convert raw observation to structured signals
                    signals = await extractor.extract_signals(obs.content)
                    if signals:
                        state_context.current_signals.extend(signals)
        except Exception as e:
            import logging
            logging.getLogger("DIP.Layer4").warning(f"Minister autonomous search failed: {e}")

        return new_evidence

    async def produce_hypothesis(self, state_context: StateContext) -> Hypothesis:
        """Run heuristic-first, schema-constrained LLM refinement.

        If the LLM refinement emits RFI: queries in critical_signal_refs,
        the minister autonomously searches the web, injects new signals,
        and re-runs the heuristic + merge to incorporate fresh evidence.
        """

        heuristic = self._heuristic_proposal(state_context)
        llm = await self._llm_refinement(state_context, heuristic)
        decision = self._merge_dual_mode(heuristic, llm)
        final = decision.final

        # ── Per-Minister Autonomous Search Loop ──
        # If the LLM flagged RFI queries, search the web and re-evaluate
        rfi_refs = getattr(final, "critical_signal_refs", []) or []
        rfi_queries = [r for r in rfi_refs if isinstance(r, str) and r.upper().startswith("RFI:")]

        if rfi_queries:
            new_evidence = await self._autonomous_search(rfi_queries, state_context)
            if new_evidence:
                # Re-run heuristic with enriched state context
                heuristic = self._heuristic_proposal(state_context)
                decision = self._merge_dual_mode(heuristic, llm)
                final = decision.final
                # Remove consumed RFI queries from critical_signal_refs
                final.critical_signal_refs = [
                    r for r in (final.critical_signal_refs or [])
                    if not r.upper().startswith("RFI:")
                ] + [f"RESOLVED: {e[:80]}" for e in new_evidence[:5]]

        return Hypothesis(
            minister=self.minister_name,
            hypothesis_type=self.hypothesis_type,
            predicted_signals=final.predicted_signals,
            matched_signals=final.matched_signals,
            missing_signals=final.missing_signals,
            confidence=round(final.confidence, 3),
            rationale=getattr(final, "rationale", "Calibrated from source-weighted intelligence signals."),
            critical_signal_refs=getattr(final, "critical_signal_refs", []),
            decision_mode=decision.resolution_action,
            heuristic_confidence=decision.heuristic.confidence,
            llm_confidence=decision.llm.confidence if decision.llm else None,
            agreement_score=decision.agreement_score,
            disagreement_notes=decision.disagreement_notes,
        )

    async def critique_peers(self, ctx: StateContext, peers: List[Hypothesis]) -> List[DebateCritique]:
        """Review peer hypotheses and issue Concur/Non-Concur critiques (Round 2)."""
        critiques = []
        for peer in peers:
            if peer.minister == self.minister_name:
                continue
                
            prompt = (
                f"{self.minister_name}, review the following hypothesis by {peer.minister}:\n"
                f"Hypothesis: {peer.hypothesis_type}\n"
                f"Confidence: {peer.confidence}\n"
                f"Rationale: {', '.join(peer.matched_signals)}\n\n"
                f"Does this align with your domain's perspective? Do you Concur or Non-Concur?"
            )
            resp = await structured_acompletion(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                output_model=MinisterCritiqueOutput,
                temperature=0.2,
            )
            concur = resp.concurrence if resp else "Concur with Comment"
            just = resp.justification if resp else "Critique generation failed."
                
            critiques.append(DebateCritique(
                critiquing_minister=self.minister_name,
                target_minister=peer.minister,
                concurrence=concur,
                justification=just
            ))
        return critiques

    async def recalibrate_confidence(self, ctx: StateContext, my_hypothesis: Hypothesis, peer_critiques: List[DebateCritique]) -> Hypothesis:
        """Update confidence based on peer critiques (Round 3)."""
        if not peer_critiques:
            return my_hypothesis
            
        critique_block = "\\n".join([f"[{c.critiquing_minister}] {c.concurrence}: {c.justification}" for c in peer_critiques])
        prompt = (
            f"Your initial hypothesis confidence was {my_hypothesis.confidence}.\n"
            f"Here are the critiques from your peers:\n{critique_block}\n\n"
            "Given this feedback, update your confidence score. Lower it if flaws were found. Raise it if others independently corroborated it."
        )
        resp = await structured_acompletion(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            output_model=MinisterRecalibrationOutput,
            temperature=0.1,
        )
        if resp:
            # Bound recalibration to prevent wild swings
            delta = resp.recalibrated_confidence - my_hypothesis.confidence
            bounded_delta = max(-0.25, min(0.25, delta))
            my_hypothesis.recalibrated_confidence = round(my_hypothesis.confidence + bounded_delta, 3)
            my_hypothesis.recalibration_rationale = resp.recalibration_rationale
                
        return my_hypothesis

