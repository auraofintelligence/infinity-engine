"""Public Pages site: a live monitor of where every song sits.

Generates a static multi-page site into docs/ from the vault plus the
universe repo's catalogue. Metadata only, never lyrics. Regenerate with
`python -m engine site` and push; GitHub Pages serves the result.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

STATUS_ORDER = ["ingested", "analysed", "briefed", "panels", "keyframes",
                "video", "published"]

STATUS_BLURB = {
    "ingested": "lyrics and context are in the vault",
    "analysed": "themes, mood and story seed mapped",
    "briefed": "Luke has approved a visual direction",
    "panels": "comic pre-viz panels exist",
    "keyframes": "panels promoted to video keyframes",
    "video": "video shots generated",
    "published": "released to a platform",
}

UNIVERSE_BASE = "https://auraofintelligence.github.io/i-C-infinity-music-universe"
REPO_BASE = "https://github.com/auraofintelligence/infinity-engine"

CSS = """
:root{--bg:#0e0e16;--panel:#171725;--line:#262640;--ink:#e9e9f2;--mut:#8d8da6;
--a:#7fb4e6}
*{box-sizing:border-box}body{font-family:system-ui,sans-serif;margin:0;
background:var(--bg);color:var(--ink);line-height:1.55}
a{color:var(--a);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1060px;margin:0 auto;padding:0 1.2rem}
header{border-bottom:1px solid var(--line);padding:.9rem 0}
header .wrap{display:flex;gap:1.4rem;align-items:baseline;flex-wrap:wrap}
header strong{font-size:1.05rem}nav{display:flex;gap:1.1rem;flex-wrap:wrap}
h1{font-size:2rem;font-weight:800;margin:2.2rem 0 .4rem}
h2{margin-top:2.4rem}.lead{color:var(--mut);max-width:46rem}
.bar{display:flex;height:16px;border-radius:8px;overflow:hidden;
background:var(--panel);margin:1.2rem 0}
.s-ingested{background:#3a3a58}.s-analysed{background:#1d5573}.s-briefed{background:#7a6600}
.s-panels{background:#63419a}.s-keyframes{background:#8a4477}.s-video{background:#2f7a42}
.s-published{background:#0f8a68}
.pill{display:inline-block;padding:.08rem .6rem;border-radius:999px;
font-size:.78rem;background:var(--panel)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));
gap:1.1rem;margin:1.6rem 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
overflow:hidden}.card img{width:100%;aspect-ratio:1;object-fit:cover;display:block}
.card .pad{padding:.8rem .9rem 1rem}.card h3{margin:.1rem 0 .2rem;font-size:1rem}
.card .muted,.muted{color:var(--mut);font-size:.85rem}
.card .bar{height:8px;margin:.7rem 0 0}
table{border-collapse:collapse;width:100%;margin:1.2rem 0 2.5rem}
th,td{text-align:left;padding:.5rem .7rem;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--mut);font-size:.78rem;text-transform:uppercase;letter-spacing:.06em}
.theme{color:#9ad;font-size:.8rem;margin-right:.45rem;white-space:nowrap}
.legend{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
gap:.7rem;margin:1.4rem 0}
.legend div{background:var(--panel);border:1px solid var(--line);
border-radius:10px;padding:.7rem .9rem;font-size:.9rem}
footer{border-top:1px solid var(--line);margin-top:3.5rem;padding:1.6rem 0 2.4rem;
color:var(--mut);font-size:.9rem}
.stage-flow{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:1.4rem 0}
.stage-flow .pill{font-size:.85rem;padding:.3rem .8rem}
.stage-flow span.arrow{color:var(--mut)}
.doc{max-width:52rem}
.doc h1{margin-top:1.6rem}.doc h2{margin-top:2.4rem;padding-top:1.4rem;
border-top:1px solid var(--line)}.doc h3{margin-top:1.7rem}
.doc p,.doc li{color:#d6d6e4}.doc li{margin:.2rem 0}
.doc code{background:#20203300;background:var(--panel);border:1px solid var(--line);
border-radius:5px;padding:.05rem .35rem;font-size:.88em}
.doc pre{background:#0a0a12;border:1px solid var(--line);border-radius:10px;
padding:1rem 1.1rem;overflow-x:auto}
.doc pre code{background:none;border:none;padding:0;font-size:.82rem;
line-height:1.45;color:#c8c8dc}
.doc blockquote{border-left:3px solid var(--a);margin:1.2rem 0;padding:.3rem 1rem;
color:var(--mut);background:var(--panel);border-radius:0 8px 8px 0}
.doc hr{border:none;border-top:1px solid var(--line);margin:2rem 0}
.doc table{margin:1.2rem 0}.doc td{color:#d6d6e4}
"""


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _page(title: str, body: str, depth: int = 0) -> str:
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en-AU"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} - Infinity Engine</title>
<style>{CSS}</style></head><body>
<header><div class="wrap">
<strong>Infinity Engine</strong>
<nav><a href="{up}index.html">Progress</a>
<a href="{up}pipeline.html">How it works</a>
<a href="{up}workflow.html">Operator guide</a>
<a href="{UNIVERSE_BASE}/">Music universe</a></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">A live monitor of the i C. infinity visual
pipeline. Regenerated from the song vault as pieces complete.
Lyrics live with the music, not here.<br>Luke &times; Claude.</div></footer>
</body></html>"""


def _status_bar(counts: dict, total: int, small: bool = False) -> str:
    if total == 0:
        return ""
    cells = "".join(
        f'<div class="s-{s}" style="width:{100 * counts.get(s, 0) / total}%"'
        f' title="{s}: {counts.get(s, 0)}"></div>'
        for s in STATUS_ORDER if counts.get(s))
    return f'<div class="bar">{cells}</div>'


def _counts(notes: list) -> dict:
    counts: dict = {}
    for note in notes:
        counts[note.status] = counts.get(note.status, 0) + 1
    return counts


def render_site(notes: list, catalogue: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "albums").mkdir(exist_ok=True)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    by_album: dict[str, list] = {}
    for note in notes:
        by_album.setdefault(note.meta.get("album", "Unfiled"), []).append(note)
    written = []

    # Index: overall progress + album cards.
    total_counts = _counts(notes)
    summary = " &middot; ".join(
        f"{s} {total_counts[s]}" for s in STATUS_ORDER if total_counts.get(s))
    cards = []
    for album in catalogue.get("albums", []):
        album_notes = by_album.get(album["title"], [])
        if not album_notes:
            continue
        art = f"{UNIVERSE_BASE}/{album.get('artwork', '')}"
        counts = _counts(album_notes)
        cards.append(
            f'<a class="card" href="albums/{album["slug"]}.html">'
            f'<img src="{art}" alt="{_esc(album["title"])} artwork">'
            f'<div class="pad"><h3>{_esc(album["title"])}</h3>'
            f'<div class="muted">{_esc(album.get("year", ""))} &middot; '
            f'{len(album_notes)} songs</div>'
            f'{_status_bar(counts, len(album_notes), small=True)}'
            "</div></a>")
    index_body = (
        "<h1>Where every song sits</h1>"
        f"<p class='lead'>{len(notes)} songs across {len(cards)} albums are "
        "moving from lyrics towards film: lyric videos, comics, vertical "
        "micro-dramas and more. This page tracks each song through the "
        "stages below and updates as pieces complete.</p>"
        f"{_status_bar(total_counts, len(notes))}"
        f"<p class='muted'>{len(notes)} songs &middot; {summary}</p>"
        "<div class='legend'>" + "".join(
            f"<div><span class='pill s-{s}'>{s}</span><br>"
            f"<span class='muted'>{STATUS_BLURB[s]}</span></div>"
            for s in STATUS_ORDER) + "</div>"
        "<h2>Albums</h2>"
        f"<div class='grid'>{''.join(cards)}</div>")
    path = out_dir / "index.html"
    path.write_text(_page("Progress", index_body), encoding="utf-8")
    written.append(path)

    # One page per album.
    for album in catalogue.get("albums", []):
        album_notes = by_album.get(album["title"], [])
        if not album_notes:
            continue
        album_notes.sort(key=lambda n: n.meta.get("track") or 0)
        rows = []
        for note in album_notes:
            meta = note.meta
            themes = "".join(f'<span class="theme">{_esc(t)}</span>'
                             for t in meta.get("themes") or [])
            title_cell = _esc(meta.get("title", note.slug))
            if meta.get("release_url"):
                title_cell = (f'<a href="{_esc(meta["release_url"])}">'
                              f"{title_cell}</a>")
            rows.append(
                "<tr>"
                f"<td>{meta.get('track') or ''}</td>"
                f"<td><strong>{title_cell}</strong></td>"
                f"<td><span class='pill s-{note.status}'>{note.status}</span></td>"
                f"<td>{_esc(meta.get('mood') or '')}</td>"
                f"<td>{themes}</td>"
                "</tr>")
        counts = _counts(album_notes)
        body = (
            f"<h1>{_esc(album['title'])}</h1>"
            f"<p class='lead'>{_esc(album.get('summary', ''))}</p>"
            f"<p class='muted'>Visual world: {_esc(album.get('visual_world', ''))}</p>"
            f"{_status_bar(counts, len(album_notes))}"
            "<table><tr><th>#</th><th>Song</th><th>Status</th><th>Mood</th>"
            "<th>Themes</th></tr>" + "".join(rows) + "</table>")
        path = out_dir / "albums" / f"{album['slug']}.html"
        path.write_text(_page(album["title"], body, depth=1), encoding="utf-8")
        written.append(path)

    # Pipeline explainer.
    flow = "<div class='stage-flow'>" + "<span class='arrow'>&rarr;</span>".join(
        f"<span class='pill s-{s}'>{s}</span>" for s in STATUS_ORDER) + "</div>"
    pipeline_body = (
        "<h1>How the engine works</h1>"
        "<p class='lead'>Songs become visuals through a fixed set of stages. "
        "The cheap thinking happens first in text; a human direction point "
        "sits in the middle; the expensive video generation only ever renders "
        "already-approved ideas.</p>"
        + flow +
        "<h2>The stages</h2><div class='legend'>" + "".join(
            f"<div><span class='pill s-{s}'>{s}</span><br>"
            f"<span class='muted'>{STATUS_BLURB[s]}</span></div>"
            for s in STATUS_ORDER) + "</div>"
        "<h2>What exists today</h2>"
        "<p>The vault, the ideation loop and this monitor are live. Comic "
        "pre-viz, video generation, voice and lip-sync are designed and "
        "would run on rented GPUs against open-weight models; they come "
        "online stage by stage, and this site will show each song advance "
        "as they do.</p>"
        "<h2>Five lanes, one spine</h2>"
        "<p class='muted'>Lyric videos, comics and graphic novels, "
        "avatar-presented course videos, vertical micro-dramas, and whole-"
        "album aggregates all share the same early stages, so work done "
        "once serves every format.</p>")
    path = out_dir / "pipeline.html"
    path.write_text(_page("How it works", pipeline_body), encoding="utf-8")
    written.append(path)

    # Operator guide: render docs/WORKFLOW.md into a styled page so it
    # lives on the site itself, WORKFLOW.md staying the single source.
    guide = out_dir / "WORKFLOW.md"
    if guide.exists():
        from .markdown import render as render_md
        body = render_md(guide.read_text(encoding="utf-8"))
        # Cross-doc .md links have no on-site page; send them to the
        # GitHub blob, which renders markdown. workflow.html self-links
        # are not emitted by the doc, so nothing to special-case.
        body = re.sub(r'href="([\w./-]+\.md)"',
                      rf'href="{REPO_BASE}/blob/main/docs/\1"', body)
        path = out_dir / "workflow.html"
        path.write_text(_page("Operator guide",
                              f"<div class='doc'>{body}</div>"),
                        encoding="utf-8")
        written.append(path)

    # Prune stale album pages: if an album drops out of the allowlist,
    # its old page must not linger on the live site.
    kept = {p.name for p in written if p.parent.name == "albums"}
    for old in (out_dir / "albums").glob("*.html"):
        if old.name not in kept:
            old.unlink()

    return written


def load_catalogue(pack_dir: Path) -> dict:
    return json.loads(
        (pack_dir / "data" / "catalogue.json").read_text(encoding="utf-8"))
