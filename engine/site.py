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
/* pattern chooser */
.pc-facets{display:flex;flex-direction:column;gap:.7rem;margin:1.4rem 0 1.8rem}
.pc-frow{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center}
.pc-flabel{color:var(--mut);font-size:.72rem;text-transform:uppercase;
letter-spacing:.06em;width:5.2rem;flex:none}
.pc-chip{cursor:pointer;user-select:none;border:1px solid var(--line);
background:var(--panel);color:var(--ink);border-radius:999px;
padding:.28rem .8rem;font-size:.85rem;transition:.15s}
.pc-chip:hover{border-color:var(--a)}
.pc-chip.on{background:var(--a);border-color:var(--a);color:#08131f;font-weight:600}
.pc-chip.lane-recon.on{background:#5aa0d8;border-color:#5aa0d8}
.pc-chip.lane-release.on{background:#d0a23a;border-color:#d0a23a}
.pc-chip.lane-hero.on{background:#c86aa6;border-color:#c86aa6}
.pc-clear{margin-left:auto;color:var(--mut);cursor:pointer;font-size:.82rem;
background:none;border:none;text-decoration:underline}
.pc-count{color:var(--mut);font-size:.9rem;margin:.4rem 0 1rem}
.pc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));
gap:1rem}
.pc-card{background:var(--panel);border:1px solid var(--line);border-radius:13px;
padding:1rem 1.05rem;display:flex;flex-direction:column;gap:.5rem}
.pc-card.hidden{display:none}
.pc-card h3{margin:0;font-size:1.02rem;line-height:1.25}
.pc-badges{display:flex;flex-wrap:wrap;gap:.3rem;align-items:center}
.pc-b{font-size:.68rem;text-transform:uppercase;letter-spacing:.04em;
border-radius:999px;padding:.08rem .5rem}
.pc-b.recon{background:#1d3a52;color:#bfe0ff}.pc-b.release{background:#4d3d0f;color:#ffe6a6}
.pc-b.hero{background:#4d2340;color:#ffc7ec}
.pc-b.tier{background:#2a2a40;color:#c9c9e6}
.pc-b.built{background:#123f2e;color:#8ff0c4}.pc-b.designed{background:#2a2a40;color:#b7b7d6}
.pc-b.planned{background:#3a2440;color:#e0b7f0}
.pc-sum{color:#d3d3e2;font-size:.9rem;margin:0}
.pc-tags{display:flex;flex-wrap:wrap;gap:.3rem}
.pc-tag{font-size:.72rem;color:#9ad;background:#182a3a;border-radius:5px;
padding:.05rem .4rem}
.pc-meta{font-size:.82rem;color:var(--mut)}.pc-meta b{color:#cdd6df;font-weight:600}
.pc-more{border:none;background:none;color:var(--a);cursor:pointer;font-size:.82rem;
text-align:left;padding:0}
.pc-detail{display:none;font-size:.85rem;color:#cdd0dc;border-top:1px solid var(--line);
padding-top:.6rem;margin-top:.2rem}
.pc-detail.open{display:block}.pc-detail p{margin:.25rem 0}
.pc-add{margin-top:.2rem;border:1px solid var(--a);background:none;color:var(--a);
border-radius:8px;padding:.35rem;cursor:pointer;font-size:.85rem;font-weight:600}
.pc-add.added{background:var(--a);color:#08131f}
.pc-tray{position:sticky;top:.6rem;z-index:5;background:#12121e;
border:1px solid var(--line);border-radius:12px;padding:.8rem 1rem;margin:0 0 1.4rem}
.pc-tray h2{margin:.1rem 0 .5rem;font-size:1rem}
.pc-tray-empty{color:var(--mut);font-size:.88rem}
.pc-tray ol{margin:.3rem 0 0;padding-left:1.2rem}
.pc-tray li{margin:.15rem 0;font-size:.9rem}
.pc-tray li button{border:none;background:none;color:#e2758f;cursor:pointer;
font-size:.9rem;margin-left:.3rem}
@media(max-width:560px){.pc-flabel{width:100%}}
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
<a href="{up}patterns.html">Patterns</a>
<a href="{up}models.html">Models</a>
<a href="{up}loras.html">LoRAs</a>
<a href="{up}compute.html">Compute</a>
<a href="{up}recon.html">Recon</a>
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

    # Pattern chooser and the registry pickers (data-driven).
    for builder in (render_patterns, render_models, render_loras,
                    render_compute, render_recon):
        page = builder(out_dir)
        if page:
            written.append(page)

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


LANES = ["recon", "release", "hero"]
STAGES = ["analyse", "cast", "voice", "panels", "motion", "scene", "video",
          "assemble"]
TIERS = ["draft", "standard", "premium"]


def _chip(group: str, value: str, extra: str = "") -> str:
    return (f'<button class="pc-chip {extra}" data-group="{group}" '
            f'data-value="{value}" onclick="pcToggle(this)">'
            f'{_esc(value)}</button>')


def _pattern_card(p: dict) -> str:
    lanes = p.get("lane") or []
    tags = p.get("tags") or []
    status = p.get("status", "designed")
    models = ", ".join(p.get("models") or []) or "-"
    badges = "".join(f'<span class="pc-b {ln}">{ln}</span>' for ln in lanes)
    badges += f'<span class="pc-b tier">{_esc(p.get("tier", ""))}</span>'
    badges += f'<span class="pc-b {status}">{status}</span>'
    tag_html = "".join(f'<span class="pc-tag">{_esc(t)}</span>' for t in tags)
    detail = (
        f"<p><b>Models:</b> {_esc(models)}</p>"
        f"<p><b>Inputs:</b> {_esc(p.get('inputs', ''))}</p>"
        f"<p><b>Outputs:</b> {_esc(p.get('outputs', ''))}</p>"
        f"<p><b>Risk:</b> {_esc(p.get('risk', ''))}</p>")
    return (
        f'<div class="pc-card" data-lane="{" ".join(lanes)}" '
        f'data-stage="{_esc(p.get("stage", ""))}" '
        f'data-tier="{_esc(p.get("tier", ""))}" '
        f'data-tags="{" ".join(tags)}">'
        f'<div class="pc-badges">{badges}</div>'
        f'<h3>{_esc(p.get("name", p["id"]))}</h3>'
        f'<p class="pc-sum">{_esc(p.get("summary", ""))}</p>'
        f'<div class="pc-tags">{tag_html}</div>'
        f'<div class="pc-meta"><b>Cost:</b> {_esc(p.get("cost", "-"))} '
        f'&middot; <b>Stage:</b> {_esc(p.get("stage", ""))}</div>'
        '<button class="pc-more" onclick="pcMore(this)">Details</button>'
        f'<div class="pc-detail">{detail}</div>'
        f'<button class="pc-add" data-id="{p["id"]}" '
        f'data-name="{_esc(p.get("name", p["id"]))}" '
        'onclick="pcAdd(this)">Add to plan</button>'
        '</div>')


def render_patterns(out_dir: Path) -> Path | None:
    import yaml
    src = out_dir.parent / "patterns.yaml"
    if not src.exists():
        return None
    patterns = (yaml.safe_load(src.read_text(encoding="utf-8")) or {}
                ).get("patterns", [])
    all_tags = sorted({t for p in patterns for t in (p.get("tags") or [])})

    def frow(label, group, values, laned=False):
        chips = "".join(
            _chip(group, v, extra=(f"lane-{v}" if laned else ""))
            for v in values)
        return (f'<div class="pc-frow"><span class="pc-flabel">{label}</span>'
                f'{chips}</div>')

    facets = (
        '<div class="pc-facets">'
        + frow("Lane", "lane", LANES, laned=True)
        + frow("Stage", "stage", STAGES)
        + frow("Tier", "tier", TIERS)
        + frow("Capability", "tags", all_tags)
        + '<div class="pc-frow"><button class="pc-clear" '
          'onclick="pcClear()">clear all filters</button></div>'
        + '</div>')
    cards = "".join(_pattern_card(p) for p in patterns)
    id_names = json.dumps({p["id"]: p.get("name", p["id"]) for p in patterns})

    body = (
        "<h1>Pattern chooser</h1>"
        "<p class='lead'>Every tried-and-tested recipe in the engine, as a "
        "card. Filter by lane, stage, tier or capability to find the path "
        "for the work in front of you, then add the ones you want to your "
        "plan. Jump in at any stage; nothing here is a fixed order.</p>"
        '<div class="pc-tray" id="pcTray"></div>'
        + facets
        + '<div class="pc-count" id="pcCount"></div>'
        + f'<div class="pc-grid" id="pcGrid">{cards}</div>'
        + f'<script>const PC_NOUN="pattern";const PC_NAMES={id_names};'
        + f"{_FILTER_CORE_JS}{_PATTERNS_TRAY_JS}</script>")
    path = out_dir / "patterns.html"
    path.write_text(_page("Patterns", body), encoding="utf-8")
    return path


# Group-agnostic filter core, shared by the pattern chooser and every
# picker. pcState is built from whatever data-group chips are on the page,
# so the same code filters any facet set.
_FILTER_CORE_JS = r"""
const pcState={};
document.querySelectorAll('.pc-chip[data-group]').forEach(c=>{
  pcState[c.dataset.group]=pcState[c.dataset.group]||new Set()});
function pcToggle(el){const g=el.dataset.group,v=el.dataset.value;
  const s=pcState[g];if(s.has(v)){s.delete(v);el.classList.remove('on')}
  else{s.add(v);el.classList.add('on')}pcFilter()}
function pcClear(){for(const g in pcState)pcState[g].clear();
  document.querySelectorAll('.pc-chip.on').forEach(c=>c.classList.remove('on'));
  pcFilter()}
function pcMatch(card){for(const g in pcState){const sel=pcState[g];
  if(!sel.size)continue;
  const vals=(card.dataset[g]||'').split(' ').filter(Boolean);
  if(![...sel].some(v=>vals.includes(v)))return false}return true}
function pcFilter(){let n=0;document.querySelectorAll('.pc-card').forEach(c=>{
  const ok=pcMatch(c);c.classList.toggle('hidden',!ok);if(ok)n++});
  document.getElementById('pcCount').textContent=
    n+' '+PC_NOUN+(n===1?'':'s')+' shown'}
function pcMore(b){b.nextElementSibling.classList.toggle('open')}
"""

_PATTERNS_TRAY_JS = r"""
let pcPlan=[];
try{pcPlan=JSON.parse(localStorage.getItem('pcPlan')||'[]')}catch(e){pcPlan=[]}
function pcAdd(b){const id=b.dataset.id;
  if(pcPlan.includes(id)){pcPlan=pcPlan.filter(x=>x!==id)}
  else{pcPlan.push(id)}pcSave();pcRenderTray();pcSyncAdd()}
function pcRemove(id){pcPlan=pcPlan.filter(x=>x!==id);pcSave();
  pcRenderTray();pcSyncAdd()}
function pcSave(){localStorage.setItem('pcPlan',JSON.stringify(pcPlan))}
function pcSyncAdd(){document.querySelectorAll('.pc-add').forEach(b=>{
  const on=pcPlan.includes(b.dataset.id);b.classList.toggle('added',on);
  b.textContent=on?'In your plan':'Add to plan'})}
function pcRenderTray(){const t=document.getElementById('pcTray');
  if(!pcPlan.length){t.innerHTML='<h2>Your plan</h2>'
    +'<div class="pc-tray-empty">No patterns chosen yet. '
    +'Add cards below to build a sequence.</div>';return}
  const items=pcPlan.map(id=>'<li>'+(PC_NAMES[id]||id)
    +'<button title="remove" onclick="pcRemove(\''+id+'\')">&times;</button>'
    +'</li>').join('');
  t.innerHTML='<h2>Your plan ('+pcPlan.length+')</h2><ol>'+items+'</ol>'}
pcRenderTray();pcSyncAdd();pcFilter();
"""


def _facet_row(label: str, group: str, values: list) -> str:
    chips = "".join(_chip(group, v) for v in values)
    return (f'<div class="pc-frow"><span class="pc-flabel">{label}</span>'
            f'{chips}</div>')


def render_picker(out_dir: Path, *, filename: str, title: str, noun: str,
                  lead: str, facet_defs: list, cards: list) -> Path:
    """Generic faceted card picker. facet_defs is a list of
    (label, group, [values]); each card is (attrs_dict, html)."""
    facet_html = "".join(_facet_row(lbl, grp, vals)
                         for lbl, grp, vals in facet_defs if vals)
    facet_html += ('<div class="pc-frow"><button class="pc-clear" '
                   'onclick="pcClear()">clear all filters</button></div>')
    card_html = []
    for attrs, inner in cards:
        data = " ".join(f'data-{k}="{" ".join(v)}"' for k, v in attrs.items())
        card_html.append(f'<div class="pc-card" {data}>{inner}</div>')
    body = (
        f"<h1>{_esc(title)}</h1>"
        f"<p class='lead'>{lead}</p>"
        f'<div class="pc-facets">{facet_html}</div>'
        '<div class="pc-count" id="pcCount"></div>'
        f'<div class="pc-grid">{"".join(card_html)}</div>'
        f'<script>const PC_NOUN="{noun}";{_FILTER_CORE_JS}</script>')
    path = out_dir / filename
    path.write_text(_page(title, body), encoding="utf-8")
    return path


def _load_catalog(out_dir: Path, name: str, key: str) -> list:
    import yaml
    src = out_dir.parent / name
    if not src.exists():
        return []
    return (yaml.safe_load(src.read_text(encoding="utf-8")) or {}).get(key, [])


def _sorted_uniq(items: list, field: str) -> list:
    return sorted({str(i.get(field)) for i in items if i.get(field)})


def render_models(out_dir: Path) -> Path | None:
    models = _load_catalog(out_dir, "catalog/models.yaml", "models")
    if not models:
        return None
    cards = []
    for m in models:
        status = m.get("status", "watching")
        st_class = {"active": "built", "recon": "planned",
                    "watching": "designed"}.get(status, "designed")
        comfy = m.get("comfy", "no")
        inner = (
            f'<div class="pc-badges">'
            f'<span class="pc-b tier">{_esc(m.get("category",""))}</span>'
            f'<span class="pc-b {st_class}">{_esc(status)}</span>'
            + (f'<span class="pc-b built">ComfyUI</span>' if comfy == "yes"
               else "") + '</div>'
            f'<h3>{_esc(m.get("name", m["id"]))}</h3>'
            f'<p class="pc-sum">{_esc(m.get("why",""))}</p>'
            f'<div class="pc-meta"><b>Task:</b> {_esc(m.get("task",""))}<br>'
            f'<b>Licence:</b> {_esc(m.get("licence",""))}<br>'
            f'<b>VRAM:</b> {_esc(m.get("vram_gb","?"))} GB '
            f'&middot; <b>HF likes:</b> {_esc(m.get("likes","?"))}</div>'
            + (f'<a class="pc-more" href="https://huggingface.co/'
               f'{_esc(m.get("hf",""))}" target="_blank" rel="noopener">'
               f'Hugging Face &rarr;</a>' if m.get("hf") else ""))
        attrs = {
            "category": [str(m.get("category", ""))],
            "status": [status],
            "licence": ["commercial" if "Apache" in str(m.get("licence", ""))
                        or "MIT" in str(m.get("licence", "")) else "restricted"],
        }
        cards.append((attrs, inner))
    facet_defs = [
        ("Category", "category", _sorted_uniq(models, "category")),
        ("Status", "status", ["active", "recon", "watching"]),
        ("Licence", "licence", ["commercial", "restricted"]),
    ]
    return render_picker(
        out_dir, filename="models.html", title="Model picker", noun="model",
        lead=("Open-weight models per category, sourced from Hugging Face. "
              "Green means it's in the working stack; recon means it's being "
              "tested; watching means it's on the radar. Licence 'commercial' "
              "is Apache or MIT and safe for the universe; 'restricted' needs "
              "a closer look. The recon watcher keeps this fresh."),
        facet_defs=facet_defs, cards=cards)


def render_loras(out_dir: Path) -> Path | None:
    loras = _load_catalog(out_dir, "catalog/loras.yaml", "loras")
    if not loras:
        return None
    cards = []
    for lo in loras:
        status = lo.get("status", "planned")
        st_class = {"active": "built", "recon": "planned",
                    "planned": "designed"}.get(status, "designed")
        priv = lo.get("private", False)
        inner = (
            '<div class="pc-badges">'
            f'<span class="pc-b tier">{_esc(lo.get("kind",""))}</span>'
            f'<span class="pc-b {st_class}">{_esc(status)}</span>'
            + ('<span class="pc-b hero">private</span>' if priv else "")
            + '</div>'
            f'<h3>{_esc(lo.get("name", lo["id"]))}</h3>'
            f'<p class="pc-sum">{_esc(lo.get("why",""))}</p>'
            f'<div class="pc-meta"><b>Base:</b> {_esc(lo.get("base","?"))} '
            f'&middot; <b>Source:</b> {_esc(lo.get("source","?"))}<br>'
            f'<b>Trigger:</b> <code>{_esc(lo.get("trigger","-"))}</code></div>')
        attrs = {
            "kind": [str(lo.get("kind", ""))],
            "status": [status],
            "visibility": ["private" if priv else "shareable"],
        }
        cards.append((attrs, inner))
    facet_defs = [
        ("Kind", "kind", _sorted_uniq(loras, "kind")),
        ("Status", "status", ["active", "recon", "planned"]),
        ("Visibility", "visibility", ["shareable", "private"]),
    ]
    return render_picker(
        out_dir, filename="loras.html", title="LoRA picker", noun="LoRA",
        lead=("Fine-tunes the pipeline can pull: your own cast and likeness "
              "LoRAs from the foundry, plus style and detail LoRAs the watcher "
              "flags from Hugging Face for you to vet. Private ones never "
              "leave your machine."),
        facet_defs=facet_defs, cards=cards)


def render_compute(out_dir: Path) -> Path | None:
    rows = _load_catalog(out_dir, "catalog/compute.yaml", "compute")
    if not rows:
        return None
    cards = []
    for c in rows:
        best = c.get("best_for", "")
        inner = (
            '<div class="pc-badges">'
            f'<span class="pc-b tier">{_esc(c.get("provider",""))}</span>'
            + (f'<span class="pc-b {"recon" if best=="batch" else "hero"}">'
               f'{_esc(best)}</span>' if best else "")
            + (f'<span class="pc-b release">spot</span>'
               if str(c.get("interruptible","")).startswith(("yes","spot"))
               else "") + '</div>'
            f'<h3>{_esc(c.get("card", c["id"]))}</h3>'
            f'<div class="pc-meta" style="font-size:1.1rem;color:#cdd6df">'
            f'<b>A${_esc(c.get("price_aud_hr","?"))}</b>'
            + ("/hr" if isinstance(c.get("price_aud_hr"), (int, float))
               else "") + '</div>'
            f'<p class="pc-sum">{_esc(c.get("notes",""))}</p>'
            f'<div class="pc-meta"><b>Offering:</b> {_esc(c.get("offering",""))} '
            f'&middot; <b>Billing:</b> {_esc(c.get("billing",""))}<br>'
            f'<b>Spin-up:</b> {_esc(c.get("spinup",""))} '
            f'&middot; <b>Region:</b> {_esc(c.get("region",""))}</div>')
        attrs = {
            "provider": [str(c.get("provider", "")).lower().replace(".", "")],
            "bestfor": [str(best)] if best else [],
            "spinup": [str(c.get("spinup", ""))],
        }
        cards.append((attrs, inner))
    facet_defs = [
        ("Best for", "bestfor", ["immediate", "batch"]),
        ("Spin-up", "spinup", ["fast", "medium", "slow"]),
        ("Provider", "provider", _sorted_uniq(
            [{"p": str(c.get("provider", "")).lower().replace(".", "")}
             for c in rows], "p")),
    ]
    return render_picker(
        out_dir, filename="compute.html", title="Compute comparer",
        noun="option",
        lead=("Where to rent GPUs, compared on what actually matters: fast "
              "spin-up for interactive and hero runs, or cheapest per hour for "
              "off-peak batch. Prices in AUD (converted at AUD/USD 0.70, "
              "2026-07-20); marketplace rates drift, so re-verify before a big "
              "batch."),
        facet_defs=facet_defs, cards=cards)


def render_recon(out_dir: Path) -> Path | None:
    queue = _load_catalog(out_dir, "recon-queue.yaml", "queue")
    cards = []
    for q in queue:
        status = q.get("status", "new")
        st_class = {"new": "designed", "testing": "planned",
                    "adopted": "built", "rejected": "hero"}.get(status,
                                                                "designed")
        inner = (
            '<div class="pc-badges">'
            f'<span class="pc-b tier">{_esc(q.get("category",""))}</span>'
            f'<span class="pc-b {st_class}">{_esc(status)}</span>'
            f'<span class="pc-b release">{_esc(q.get("flagged_reason",""))}</span>'
            '</div>'
            f'<h3>{_esc(q.get("name", q["id"]))}</h3>'
            f'<p class="pc-sum">{_esc(q.get("notes",""))}</p>'
            f'<div class="pc-meta"><b>Flagged:</b> '
            f'{_esc(q.get("flagged_date",""))}</div>'
            + (f'<a class="pc-more" href="{_esc(q.get("link",""))}" '
               'target="_blank" rel="noopener">source &rarr;</a>'
               if q.get("link") else ""))
        attrs = {
            "category": [str(q.get("category", ""))],
            "status": [status],
            "reason": [str(q.get("flagged_reason", ""))],
        }
        cards.append((attrs, inner))
    facet_defs = [
        ("Category", "category", _sorted_uniq(queue, "category")),
        ("Status", "status", ["new", "testing", "adopted", "rejected"]),
        ("Why", "reason", _sorted_uniq(queue, "flagged_reason")),
    ]
    intro = (
        "Candidates the watcher flagged, plus anything you drop in. This is "
        "the inbox of the Recon lane: vet each one on a fast, cheap pass, then "
        "promote the winners into the model registry or reject them. Run "
        "<code>python tools/watch_models.py</code> (or the scheduled task) to "
        "refresh it. See the "
        f'<a href="{REPO_BASE}/blob/main/docs/RECON-WATCHER.md">watcher spec</a>.')
    if not cards:
        intro += " Nothing in the queue right now."
    return render_picker(
        out_dir, filename="recon.html", title="Recon area", noun="candidate",
        lead=intro, facet_defs=facet_defs, cards=cards)
