"""
SENTINEL Extractor — THE security heart.

This is the entire defense. It extracts ONLY the first float [0.0-1.0]
from the raw model response. Everything else — jailbreak text, harmful
content, injected instructions — is discarded.

Even if the model is fully compromised and outputs pages of harmful text,
only a single number gets through. The jailbreak has nowhere to go.
"""

import re


class SentinelExtractError(Exception):
    """Raised when no valid score can be extracted."""
    pass


# Matches floats like 0.85, 1.0, 0.0, .5, also integers 0 or 1
_FLOAT_RE = re.compile(r'(?<![a-zA-Z_])([01](?:\.\d+)?|0?\.\d+)(?![a-zA-Z_\d])')

# Matches {"score": 0.85} patterns (the ideal case)
_JSON_SCORE_RE = re.compile(
    r'["\']?score["\']?\s*[:=]\s*([01](?:\.\d+)?|0?\.\d+)'
)


def extract_score(raw_response: str) -> float:
    """
    Extract exactly one float in [0.0, 1.0] from the model response.

    Strategy:
    1. Try to find {"score": X} pattern first (ideal format)
    2. Fall back to first float in [0.0, 1.0] anywhere in text
    3. If nothing found, raise SentinelExtractError

    The raw text is NEVER returned. Only the number.

    Args:
        raw_response: The raw string output from the LLM.

    Returns:
        A float in [0.0, 1.0].

    Raises:
        SentinelExtractError: If no valid score can be extracted.
    """
    if not raw_response or not isinstance(raw_response, str):
        raise SentinelExtractError("Empty or non-string response")

    # Strategy 1: Look for explicit score field
    m = _JSON_SCORE_RE.search(raw_response)
    if m:
        val = float(m.group(1))
        if 0.0 <= val <= 1.0:
            return val

    # Strategy 2: Find first float in [0.0, 1.0]
    for m in _FLOAT_RE.finditer(raw_response):
        val = float(m.group(1))
        if 0.0 <= val <= 1.0:
            return val

    # Nothing found — the defense holds, no output gets through
    raise SentinelExtractError(
        f"No valid score in [0.0, 1.0] found in response "
        f"({len(raw_response)} chars)"
    )


def extract_score_safe(raw_response: str, default: float = 0.5) -> float:
    """Like extract_score but returns a default instead of raising."""
    try:
        return extract_score(raw_response)
    except SentinelExtractError:
        return default
