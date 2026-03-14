"""
sms_parser.py — SMS keyword extraction and skill-matching engine.

Flow
----
1. Clean and tokenise the incoming SMS text.
2. Try multi-word phrases first (longest-match strategy) against the
   skill_aliases table.
3. Fall back to single-word token matching if no phrase matches.
4. Return the canonical skill name (or None when nothing is found).
"""

import re
from typing import List, Optional, Tuple

from app.database import resolve_skill

# Words that carry no skill meaning and should be stripped before matching
_STOP_WORDS = {
    "need", "chahiye", "koi", "mujhe", "mujhko", "hai", "hain", "do", "ek",
    "de", "bata", "lagao", "lagana", "repair", "fix", "help", "please",
    "urgent", "asap", "jaldi", "abhi", "kal", "aaj", "the", "a", "an",
    "for", "me", "i", "want", "required", "require", "find", "search",
    "looking", "bhejo", "send", "number", "contact", "worker", "wala",
}


def _clean(text: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenise(text: str) -> List[str]:
    return text.split()


def _remove_stop_words(tokens: List[str]) -> List[str]:
    return [t for t in tokens if t not in _STOP_WORDS]


def _ngrams(tokens: List[str], n: int) -> List[str]:
    """Return all n-word phrases from the token list."""
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def parse_sms(
    message: str,
    db_path: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse an incoming SMS message and return ``(canonical_skill, matched_phrase)``.

    - ``canonical_skill`` is the skill name from the database (e.g. ``"tractor mechanic"``)
      or ``None`` if no skill could be identified.
    - ``matched_phrase`` is the exact alias that triggered the match (useful for logging).

    The function tries phrases of decreasing length (longest-match wins) so that
    "tractor mechanic" beats a plain "mechanic" match.
    """
    if not message or not message.strip():
        return None, None

    cleaned = _clean(message)
    tokens = _tokenise(cleaned)

    # --- Phase 1: try with all tokens (including stop-words) for long phrases ---
    for phrase_len in range(min(4, len(tokens)), 0, -1):
        for phrase in _ngrams(tokens, phrase_len):
            skill = resolve_skill(phrase, db_path)
            if skill:
                return skill, phrase

    # --- Phase 2: remove stop-words and retry ---
    filtered = _remove_stop_words(tokens)
    for phrase_len in range(min(4, len(filtered)), 0, -1):
        for phrase in _ngrams(filtered, phrase_len):
            skill = resolve_skill(phrase, db_path)
            if skill:
                return skill, phrase

    return None, None


def extract_location(message: str) -> Optional[str]:
    """
    Very lightweight location extractor.

    Looks for the pattern ``"in <location>"`` or ``"at <location>"`` or
    ``"near <location>"`` inside the message (case-insensitive).
    Returns the capitalised location string or None.

    Example: "Need tractor mechanic in Sitapur" → "Sitapur"
    """
    pattern = r"\b(?:in|at|near|from)\s+([A-Za-z][A-Za-z\s]{1,30})"
    match = re.search(pattern, message, re.IGNORECASE)
    if match:
        return match.group(1).strip().title()
    return None
