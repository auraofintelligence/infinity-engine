"""Ingest song sources into the vault.

Two sources, both optional:
  1. The album-pack repo: catalogue.json for album structure plus one
     HTML page per song carrying lyrics, meaning layer, and dates.
  2. A private local folder of cleaned lyric files (.txt/.md), for the
     production machine where the full knowledge base lives.

Re-ingest is safe: only ingest-owned fields and lyrics are refreshed;
analysis fields and status survive.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .structure import parse_structure
from .vault import INGEST_OWNED, Note, note_path, read_note, write_note

LYRICS_RE = re.compile(r'<pre class="lyrics">(.*?)</pre>', re.DOTALL)
H1_RE = re.compile(r"<h1>(.*?)</h1>")
MEANING_RE = re.compile(r"<h2>Meaning Layer</h2>\s*<p>(.*?)</p>", re.DOTALL)
SONG_DATE_RE = re.compile(r"Song date: ([^<]+)<")
RELEASE_RE = re.compile(r'Release link:</strong><br>\s*<a href="([^"]+)"')

# Machine-assist tagging only: crude keyword hints so ingested notes are
# never blank. The analyse stage (LLM + Luke) owns the real tags.
THEME_HINTS = {
    "AGI": ["ai ", " machine", "algorithm", "circuits", "digital", "code"],
    "Protopia": ["protopia", "build again", "brick by brick", "better world"],
    "GajraEarth": ["gajra", "gaia", "earth mother", "goddess"],
    "Straddie": ["straddie", "minjerribah", "island", "tide", "shore"],
    "Love": ["love", "heart", "kiss", "embrace"],
    "Grief": ["grief", "mourn", "empty chair", "we call their name", "ashes"],
    "Community": ["together", "gather", "community", "circle", "we rise"],
    "Nature": ["ocean", "waves", "moon", "sky", "fire", "forest"],
    "CosmicMyth": ["stars", "cosmic", "celestial", "infinity", "universe"],
    "Governance": ["vote", "democracy", "borders", "nations", "civic"],
}


def guess_themes(lyrics: str) -> list[str]:
    lowered = f" {lyrics.lower()} "
    return [t for t, words in THEME_HINTS.items()
            if any(w in lowered for w in words)]


def _merge(vault_dir: Path, slug: str, fresh_meta: dict, lyrics: str,
           default_lane: str = "lyric-video") -> str:
    """Create or update a note. Returns 'created' or 'updated'."""
    struct = parse_structure(lyrics)
    path = note_path(vault_dir, slug)
    if path.exists():
        note = read_note(path)
        for key in INGEST_OWNED:
            if fresh_meta.get(key) is not None:
                note.meta[key] = fresh_meta[key]
        # Structure is derived from the lyrics, so always refresh it.
        note.meta["structure"] = struct["sections"]
        note.meta["motifs"] = struct["motifs"]
        note.body = lyrics
        write_note(vault_dir, note)
        return "updated"
    meta = {k: v for k, v in fresh_meta.items() if v is not None}
    meta.setdefault("album", "Unfiled")
    meta.setdefault("status", "ingested")
    meta.setdefault("themes", guess_themes(lyrics))
    meta.setdefault("mood", None)
    meta.setdefault("narrative_structure", None)
    meta.setdefault("visual_motifs", [])
    meta["structure"] = struct["sections"]
    meta["motifs"] = struct["motifs"]
    meta.setdefault("lanes", [default_lane])
    write_note(vault_dir, Note(slug=slug, meta=meta, body=lyrics))
    return "created"


def ingest_album_pack(pack_dir: Path, vault_dir: Path,
                      allow_albums: list[str] | None = None) -> dict:
    """Ingest the album-pack repo. If allow_albums is given, only albums
    whose slug is in that list flow into the vault; everything else in
    the catalogue is skipped."""
    catalogue = json.loads(
        (pack_dir / "data" / "catalogue.json").read_text(encoding="utf-8"))
    counts = {"created": 0, "updated": 0, "no_page": 0, "skipped_album": 0}
    for album in catalogue.get("albums", []):
        if allow_albums and album.get("slug") not in allow_albums:
            counts["skipped_album"] += 1
            continue
        for track_no, slug in enumerate(album.get("tracks", []), start=1):
            page = pack_dir / "songs" / slug / "index.html"
            if not page.exists():
                counts["no_page"] += 1
                continue
            text = page.read_text(encoding="utf-8")
            lyrics_m = LYRICS_RE.search(text)
            lyrics = html.unescape(lyrics_m.group(1)).strip() if lyrics_m else ""
            title_m = H1_RE.search(text)
            meaning_m = MEANING_RE.search(text)
            date_m = SONG_DATE_RE.search(text)
            release_m = RELEASE_RE.search(text)
            meta = {
                "title": html.unescape(title_m.group(1)) if title_m else slug,
                "album": album["title"],
                "track": track_no,
                "source": "album-pack",
                "song_date": date_m.group(1).strip() if date_m else None,
                "release_url": release_m.group(1) if release_m else None,
                "meaning": html.unescape(meaning_m.group(1)).strip()
                           if meaning_m else None,
                "album_visual_world": album.get("visual_world"),
            }
            counts[_merge(vault_dir, slug, meta, lyrics)] += 1
    return counts


def ingest_local_lyrics(lyrics_dir: Path, vault_dir: Path) -> dict:
    counts = {"created": 0, "updated": 0}
    for path in sorted(lyrics_dir.iterdir()):
        if path.suffix.lower() not in (".txt", ".md") or not path.is_file():
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
        # album stays None so a re-ingest never clobbers an album Luke
        # has since assigned; new notes fall back to "Unfiled".
        meta = {
            "title": path.stem.replace("-", " ").replace("_", " ").title(),
            "source": "local-lyrics",
        }
        counts[_merge(vault_dir, slug, meta,
                      path.read_text(encoding="utf-8").strip())] += 1
    return counts
