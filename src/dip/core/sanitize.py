"""Trust boundary for adversary-controlled text (prompt-injection defense).

Data flow: web crawl / OSINT feed (untrusted) -> Layer-1 observations ->
Layer-2 extraction prompts -> Layer-4 minister prompts. Every hop that
embeds ingested text into an LLM prompt must pass through
:func:`sanitize_text` first.

What it does:
  - strips control characters and normalizes whitespace,
  - truncates to a bounded length (prompts must not grow unbounded),
  - neutralizes instruction-override phrases (``ignore previous
    instructions`` and friends) by redacting the directive while keeping
    the surrounding factual content,
  - reports what was redacted so the pipeline can log provenance flags.

What it does NOT do: it is not a full output guardrail. Use the symbolic
guardrails + verifier for output-side safety.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Instruction-override / role-hijack patterns commonly used in prompt
# injection. Matched case-insensitively; the directive clause is redacted,
# the rest of the sentence is preserved.
_INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"forget\s+(all\s+)?(previous|prior)\s+instructions?",
    r"you\s+are\s+now\s+[a-z ]{1,40}",
    r"new\s+instructions?\s*:",
    r"system\s*:",
    r"<\s*system\s*>",
    r"assistant\s+to\s*:",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"confidentia(?:l|ity)\s+breach",
)

_INJECTION_RE = re.compile(
    r"(?:" + r"|".join(_INJECTION_PATTERNS) + r")",
    re.IGNORECASE,
)

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")

DEFAULT_MAX_CHARS = 2000
DEFAULT_SIGNAL_DESC_CHARS = 300


@dataclass
class SanitizeResult:
    text: str
    truncated: bool = False
    redactions: list = field(default_factory=list)


def sanitize_text(text: str | None, max_chars: int = DEFAULT_MAX_CHARS) -> SanitizeResult:
    """Clean untrusted text before it enters an LLM prompt or a Signal."""
    if not text:
        return SanitizeResult(text="")
    cleaned = _CONTROL_RE.sub("", str(text))
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()

    redactions: list = []

    def _redact(match: re.Match) -> str:
        redactions.append(match.group(0)[:80])
        return "[REDACTED-INSTRUCTION]"

    cleaned = _INJECTION_RE.sub(_redact, cleaned)

    truncated = False
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + "…"
        truncated = True
    return SanitizeResult(text=cleaned, truncated=truncated, redactions=redactions)


def sanitize_for_prompt(text: str | None, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Convenience wrapper returning just the cleaned string."""
    return sanitize_text(text, max_chars=max_chars).text
