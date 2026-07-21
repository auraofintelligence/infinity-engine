"""Text cleanup and a review scanner for lyrics.

Two jobs:
  1. clean() applies only UNAMBIGUOUS fixes: strip markdown-escape
     backslashes that leaked from the source (\\! -> !), and revert
     confirmed phonetic-for-Suno spellings that were never corrected.
  2. scan() flags the judgement calls (odd hyphenation, phonetic-looking
     tokens, escapes) for Luke to confirm before they enter CORRECTIONS.

Merch and posters print these lines verbatim, so a typo becomes a printed
typo. Confirmed fixes are added to CORRECTIONS; nothing is guessed silently.
"""
from __future__ import annotations

import re

# Confirmed phonetic-for-Suno spellings, reverted for print. Extend as Luke
# confirms flags from `engine review`.
CORRECTIONS = {
    "Minjerribaa": "Minjerribah",
    "minjerribaa": "minjerribah",
    "Care-ih-bee-uhn": "Caribbean",
    "Gee-Ay-Jay-Are-Ay": "GAJRA",
    "jee-ay-jay-ar-ay": "GAJRA",
}

_ESCAPE_RE = re.compile(r"\\([!?.,;:'\"()\[\]{}&\-])")


def clean(s: str) -> str:
    s = _ESCAPE_RE.sub(r"\1", str(s))
    for wrong, right in CORRECTIONS.items():
        s = s.replace(wrong, right)
    return s


# Patterns that MIGHT be errors and want a human eye (art vs typo).
_SUSPECTS = [
    (re.compile(r"\\[!?.,;:'\"()\[\]{}&\-]"), "leaked escape (\\)"),
    (re.compile(r"\b[A-Za-z]+(?:-[A-Za-z]+){2,}\b"), "multi-hyphen (phonetic?)"),
    (re.compile(r"\b\w*([A-Za-z])\1{2,}\w*\b"), "repeated letters"),
    (re.compile(r"\b[A-Z][a-z]+a{2,}\b"), "double-a ending"),
]


def scan(text: str) -> list[tuple[str, str]]:
    """Return (reason, matched-token) pairs for suspicious tokens in text,
    skipping anything already covered by CORRECTIONS."""
    hits = []
    for rx, reason in _SUSPECTS:
        for m in rx.finditer(text):
            tok = m.group(0)
            if tok in CORRECTIONS or clean(tok) != tok:
                continue
            hits.append((reason, tok))
    return hits
