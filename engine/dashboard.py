"""Static HTML dashboard: the whole catalogue at a glance.

Regenerated from the vault on demand; no server, no dependencies, safe
to open from disk. Lyrics are deliberately not included, only metadata.
"""
from __future__ import annotations

import html
from pathlib import Path

STATUS_ORDER = ["ingested", "analysed", "briefed", "panels", "keyframes",
                "video", "published"]

CSS = """
body{font-family:system-ui,sans-serif;margin:2rem;background:#101018;color:#e8e8f0}
h1{font-weight:800} .muted{color:#8a8aa0}
table{border-collapse:collapse;width:100%;margin-top:1rem}
th,td{text-align:left;padding:.45rem .7rem;border-bottom:1px solid #26263a}
th{color:#8a8aa0;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}
.pill{display:inline-block;padding:.1rem .55rem;border-radius:999px;font-size:.78rem;background:#26263a}
.s-ingested{background:#33334d}.s-analysed{background:#1d4d63}.s-briefed{background:#6b5900}
.s-panels{background:#5b3a86}.s-keyframes{background:#7a3d69}.s-video{background:#2e6b3a}
.s-published{background:#0f7a5c}
.theme{color:#9ad;font-size:.8rem;margin-right:.4rem}
.bar{display:flex;height:14px;border-radius:7px;overflow:hidden;margin:.8rem 0 1.6rem}
"""


def render_dashboard(notes: list, out_path: Path) -> None:
    counts = {s: 0 for s in STATUS_ORDER}
    for note in notes:
        counts[note.status] = counts.get(note.status, 0) + 1
    total = max(len(notes), 1)
    bar = "".join(
        f'<div class="s-{s}" style="width:{100 * counts.get(s, 0) / total}%"'
        f' title="{s}: {counts.get(s, 0)}"></div>'
        for s in STATUS_ORDER if counts.get(s))
    rows = []
    for note in sorted(notes, key=lambda n: (n.meta.get("album", ""),
                                             n.meta.get("track") or 0)):
        meta = note.meta
        themes = "".join(f'<span class="theme">{html.escape(t)}</span>'
                         for t in meta.get("themes") or [])
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(meta.get('album', '?')))}</td>"
            f"<td>{meta.get('track') or ''}</td>"
            f"<td><strong>{html.escape(str(meta.get('title', note.slug)))}</strong>"
            f"<br><span class='muted'>{html.escape(note.slug)}</span></td>"
            f"<td><span class='pill s-{note.status}'>{note.status}</span></td>"
            f"<td>{html.escape(str(meta.get('mood') or ''))}</td>"
            f"<td>{themes}</td>"
            "</tr>")
    summary = " &middot; ".join(f"{s} {counts[s]}" for s in STATUS_ORDER
                                if counts.get(s))
    out_path.write_text(
        "<!doctype html><meta charset='utf-8'>"
        "<title>Infinity Engine dashboard</title>"
        f"<style>{CSS}</style>"
        f"<h1>Infinity Engine</h1>"
        f"<p class='muted'>{len(notes)} songs &middot; {summary}</p>"
        f"<div class='bar'>{bar}</div>"
        "<table><tr><th>Album</th><th>#</th><th>Song</th><th>Status</th>"
        "<th>Mood</th><th>Themes</th></tr>"
        + "".join(rows) + "</table>", encoding="utf-8")
