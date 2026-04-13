"""
Core.legal.legal_reasoner_prompt — LLM Prompt Templates for Legal Analysis
============================================================================

Contains the system prompt, user prompt template, and output schema
for the LLM-based legal applicability reasoner.

The prompts are designed to prevent hallucination:
    - LLM may ONLY use provided evidence
    - LLM may NOT invent treaties or articles
    - LLM must return structured JSON
    - Every conclusion must cite an evidence item from the input

These prompts work with deepseek-r1:8b via Ollama in json_mode.
"""

from __future__ import annotations

from typing import List, Set


# ═══════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT — constrains the LLM to evidence-only reasoning
# ═══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an international law analyst assisting an intelligence assessment.

You are NOT a lawyer writing an essay.
You are evaluating whether SPECIFIC STATE BEHAVIORS are legally justified or legally constrained.

CRITICAL WORKFLOW:
1. Read the INFERRED STATE BEHAVIORS section — these describe WHAT the state is actually doing.
2. Read the LEGAL EVIDENCE — these are the treaty provisions and legal instruments available.
3. For EACH behavior, determine which evidence items apply and whether the behavior is legally constrained.
4. Evaluate the legal question posed for each behavior against the provided evidence.

STRICT RULES:
1. You may ONLY use the provided legal evidence below.
2. If no evidence applies to a behavior, you MUST say "no_applicable_authority".
3. Do NOT invent treaties, articles, or legal doctrines.
4. Do NOT rely on your prior knowledge or training data.
5. Do NOT generalize beyond the actors listed.
6. If actors are not signatories, state that the rule is non-binding.
7. Return ONLY valid JSON matching the required schema.
8. Your "issue" field MUST describe the CONCRETE BEHAVIOR being evaluated, not the abstract signal.

For each behavior-evidence pairing:
Determine whether the behavior is:
- "prohibited" — treaty/law explicitly forbids it
- "permitted" — treaty/law explicitly allows it
- "conditional" — lawful only under specific conditions (state the condition)
- "restricted" — allowed with limitations
- "unclear" — evidence exists but does not resolve the question
- "no_applicable_authority" — no evidence in the provided set addresses this

Return a JSON object with this exact structure:
{
  "legal_constraints": [
    {
      "issue": "<concrete behavior being evaluated — e.g. 'forward military deployment near border'>",
      "status": "<prohibited|permitted|conditional|restricted|unclear|no_applicable_authority>",
      "authority": "<instrument and article from evidence>",
      "applies_to": ["<actor ISO codes>"],
      "condition": "<condition text if status is conditional, else null>",
      "confidence": <0.0-1.0>,
      "reasoning": "<1-2 sentence explanation linking the specific behavior to the legal provision>"
    }
  ]
}

Return ONLY the JSON object. No preamble, no markdown, no explanation outside the JSON."""


# ═══════════════════════════════════════════════════════════════════════
# USER PROMPT TEMPLATE — dynamically assembled by the reasoner
# ═══════════════════════════════════════════════════════════════════════

USER_PROMPT_TEMPLATE = """ACTORS:
State A (subject): {subject_country}
State B (target): {target_country}

TRIGGERING SIGNALS:
{signals_text}

INFERRED STATE BEHAVIORS:
The following concrete state behaviors have been inferred from the observed signals.
Evaluate EACH behavior against the legal evidence provided below.
{behaviors_block}

QUESTION:
Based ONLY on the legal evidence below, what legal constraints or justifications exist for EACH of the inferred state behaviors listed above? Match each behavior to the most relevant legal provision in the evidence. If a behavior has no matching evidence, state "no_applicable_authority".

LEGAL EVIDENCE:
{evidence_block}

Return your analysis as the JSON object described in your instructions."""


def build_user_prompt(
    subject_country: str,
    target_country: str,
    active_signals: Set[str],
    evidence_block: str,
    behaviors_block: str = "",
) -> str:
    """
    Assemble the user prompt from dynamic pipeline data.

    Parameters
    ----------
    subject_country : str
        ISO code or name of the subject actor (e.g. "IRN", "Iran")
    target_country : str
        ISO code or name of the target actor (e.g. "USA")
    active_signals : set[str]
        Signal codes that triggered legal retrieval.
    evidence_block : str
        Pre-formatted evidence text from ``evidence_to_prompt_block()``.
    behaviors_block : str, optional
        Pre-formatted inferred behaviors from ``behaviors_to_prompt_block()``.
        If empty, a default message is used.

    Returns
    -------
    str
        The complete user prompt ready for LLM submission.
    """
    signals_text = "\n".join(f"- {sig}" for sig in sorted(active_signals)) or "- (none)"

    if not behaviors_block:
        behaviors_block = "(No specific behaviors inferred — evaluate signals against evidence directly.)"

    return USER_PROMPT_TEMPLATE.format(
        subject_country=subject_country or "UNKNOWN",
        target_country=target_country or "UNKNOWN",
        signals_text=signals_text,
        behaviors_block=behaviors_block,
        evidence_block=evidence_block,
    )
