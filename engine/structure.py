"""Lyric structure analysis: turn a raw lyric blob into labelled sections
with per-section keywords and song-wide motifs.

This is the nuance layer the analyse step was missing. Detecting the
verse/chorus/bridge shape and the salient images in each part lets the
brief drive set, scene and flow from the song's actual dynamics rather
than one flat summary. Deterministic and local; no model needed.
"""
from __future__ import annotations

import re
from collections import Counter

# Words that carry no visual or topical signal.
STOPWORDS = {
    "the", "and", "you", "your", "yours", "that", "this", "with", "for",
    "are", "but", "not", "all", "was", "were", "have", "has", "had", "will",
    "would", "could", "should", "there", "their", "they", "them", "then",
    "than", "from", "what", "when", "where", "who", "how", "our", "out",
    "into", "over", "under", "just", "like", "cant", "dont", "wont", "its",
    "his", "her", "she", "him", "we", "us", "me", "my", "mine", "im", "ive",
    "ill", "youre", "youve", "were", "been", "being", "get", "got", "let",
    "one", "some", "any", "every", "each", "here", "now", "still", "yet",
    "too", "very", "much", "many", "more", "most", "only", "own", "same",
    "so", "up", "down", "in", "on", "at", "to", "of", "as", "by", "off",
    "about", "again", "against", "because", "before", "after", "while",
}
# Vocables / filler that look like words but say nothing.
FILLER = {"oh", "ooh", "ohh", "yeah", "yea", "na", "nah", "la", "hey", "whoa",
          "woah", "mmm", "mm", "uh", "ah", "ha", "hmm", "ohh", "aah", "doo"}


def _content_words(text: str) -> list[str]:
    words = re.findall(r"[a-z']+", text.lower())
    return [w.strip("'") for w in words
            if len(w) > 3 and w not in STOPWORDS and w not in FILLER]


def _keywords(text: str, n: int = 6) -> list[str]:
    counts = Counter(_content_words(text))
    return [w for w, _ in counts.most_common(n)]


def _norm_line(line: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9\s]", "", line.lower()).split())


# Explicit section markers, as annotated lyrics use them.
MARKER_RE = re.compile(
    r"^\s*[\[(]?\s*(intro|verse|pre[- ]?chorus|chorus|post[- ]?chorus|bridge"
    r"|outro|refrain|hook|interlude|breakdown|drop|coda)\s*"
    r"([0-9]+|[ivx]+|[a-z])?\s*[\])]?\s*[:.]?\s*$", re.I)
# Section-label words never count as content keywords.
STOPWORDS |= {"verse", "chorus", "bridge", "intro", "outro", "refrain",
              "hook", "prechorus", "postchorus", "interlude", "coda"}


def _marker_label(m: "re.Match") -> str:
    base = m.group(1).lower().replace(" ", "").replace("-", "")
    fix = {"prechorus": "pre-chorus", "postchorus": "post-chorus"}
    base = fix.get(base, base)
    num = (m.group(2) or "").strip().lower()
    return f"{base} {num}".strip()


def _parse_by_markers(lyrics: str) -> list[dict]:
    sections: list[dict] = []
    cur_label = None
    cur_lines: list[str] = []
    verse_n = 0

    def flush():
        content = [ln for ln in cur_lines if ln.strip()]
        if cur_label is None and not content:
            return
        hook = content[0].strip() if content else (cur_label or "")
        sections.append({"section": cur_label or "intro", "hook": hook,
                         "keywords": _keywords("\n".join(content))})

    for line in lyrics.splitlines():
        m = MARKER_RE.match(line)
        if m:
            flush()
            cur_lines = []
            label = _marker_label(m)
            if label == "verse":            # bare "Verse" -> auto-number
                verse_n += 1
                label = f"verse {verse_n}"
            cur_label = label
        else:
            cur_lines.append(line)
    flush()
    return sections


def parse_structure(lyrics: str) -> dict:
    """Return {sections: [{section, hook, keywords}], motifs: [...]}.

    Choruses in real songs recur as repeated LINES, not identical blocks
    (the same hook returns with different verse lines around it). So we
    detect the recurring hook line, mark the stanzas that carry it as the
    chorus, short all-repeated stanzas as refrains, and number the rest as
    verses. Motifs are the images that recur across the whole song.
    """
    all_lines = lyrics.splitlines()
    marker_count = sum(1 for ln in all_lines if MARKER_RE.match(ln))
    if marker_count >= 2:
        # Annotated lyrics: trust the author's own section labels.
        return {"sections": _parse_by_markers(lyrics),
                "motifs": _keywords(lyrics, 8)}

    stanzas = [s.strip() for s in re.split(r"\n\s*\n", lyrics.strip())
               if s.strip()]
    if not stanzas:
        return {"sections": [], "motifs": []}

    line_counts: Counter = Counter()
    for stanza in stanzas:
        for line in stanza.splitlines():
            nl = _norm_line(line)
            if len(nl.split()) >= 2:
                line_counts[nl] += 1
    hook_lines = {ln for ln, c in line_counts.items() if c >= 2}
    # The dominant recurring line anchors the chorus.
    anchor = (max(hook_lines, key=lambda ln: line_counts[ln])
              if hook_lines else None)

    sections = []
    verse_n = 0
    for stanza in stanzas:
        lines = [_norm_line(ln) for ln in stanza.splitlines()
                 if _norm_line(ln)]
        hooks_here = [ln for ln in lines if ln in hook_lines]
        hook = stanza.splitlines()[0].strip()
        if anchor and anchor in lines:
            label = "chorus"
        elif hooks_here and len(lines) <= 2:
            label = "refrain"
        elif hooks_here and len(hooks_here) >= max(2, len(lines) // 2):
            # Mostly made of repeated lines but not the main hook: a
            # secondary chorus / post-chorus.
            label = "chorus"
        else:
            verse_n += 1
            label = f"verse {verse_n}"
        sections.append({"section": label, "hook": hook,
                         "keywords": _keywords(stanza)})
    return {"sections": sections, "motifs": _keywords(lyrics, 8)}


def structure_digest(structure: dict) -> str:
    """A compact human/LLM-readable rendering of the parsed structure."""
    lines = []
    for s in structure.get("sections", []):
        kw = ", ".join(s.get("keywords") or []) or "-"
        lines.append(f"[{s['section']}] \"{s['hook']}\" | keys: {kw}")
    motifs = ", ".join(structure.get("motifs") or []) or "-"
    return "\n".join(lines) + f"\nMotifs across song: {motifs}"
