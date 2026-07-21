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
:root{--void:#05070c;--deep:#0a1420;--panel:rgba(124,77,255,.08);
--violet:#7c4dff;--amethyst:#c9a6ff;--gold:#ffcf6e;--gold-soft:#ffe6b0;
--teal:#2be3c2;--plasma:#ff5fd1;--text:#f6f4ff;--mut:#b9c3d6;
--line:rgba(124,77,255,.28);--max:1120px;--radius:16px;
--fd:"Archivo Var",ui-sans-serif,system-ui,sans-serif;
--fm:"JetBrains Mono Var",Consolas,monospace;color-scheme:dark}
*{box-sizing:border-box;min-width:0}
body{margin:0;color:var(--text);font-family:var(--fd);font-weight:440;
line-height:1.6;background:
radial-gradient(ellipse 60rem 34rem at 14% -6%,rgba(124,77,255,.22),transparent),
radial-gradient(ellipse 64rem 38rem at 90% 2%,rgba(43,227,194,.1),transparent),
radial-gradient(ellipse 78rem 50rem at 50% 116%,rgba(42,20,88,.55),transparent),
linear-gradient(180deg,#0c1220,#080c16 42%,var(--void));
background-attachment:fixed;min-height:100vh;overflow-x:hidden}
body::before{content:"";position:fixed;inset:0;z-index:-2;
background:linear-gradient(90deg,rgba(201,166,255,.045) 1px,transparent 1px),
linear-gradient(0deg,rgba(201,166,255,.045) 1px,transparent 1px);
background-size:56px 56px;
mask-image:linear-gradient(180deg,rgba(0,0,0,.7),rgba(0,0,0,.03) 72%)}
::selection{background:var(--gold);color:#201200}
a{color:var(--amethyst);text-decoration:none}a:hover{color:#fff}
.wrap{max-width:var(--max);margin:0 auto;padding:0 clamp(1rem,4vw,2rem)}
.site-header{position:sticky;top:0;z-index:50;
border-bottom:1px solid var(--line);
background:rgba(8,10,18,.82);backdrop-filter:blur(20px) saturate(1.3)}
.site-header .wrap{display:flex;gap:.8rem 1.4rem;align-items:center;
flex-wrap:wrap;padding:.7rem clamp(1rem,4vw,2rem)}
.brand{display:inline-flex;align-items:center;gap:.65rem;text-decoration:none;
margin-right:auto}
.brand-mark{width:2.3rem;height:2.3rem;border-radius:50%;flex:none;
border:1px solid rgba(255,207,110,.55);
background:radial-gradient(circle at 38% 30%,var(--gold-soft),var(--violet) 46%,#2a1458 82%);
box-shadow:0 0 26px rgba(124,77,255,.5),inset 0 0 12px rgba(255,255,255,.25)}
.brand-text{display:grid;font-family:var(--fm);font-size:.66rem;
text-transform:uppercase;letter-spacing:.06em;color:var(--mut);line-height:1.3}
.brand-text strong{font-family:var(--fd);font-size:.95rem;color:#fff;
text-transform:none;letter-spacing:0}
nav{display:flex;gap:.1rem;flex-wrap:wrap;font-size:.83rem;font-weight:620}
nav a{padding:.42rem .62rem;border-radius:999px;white-space:nowrap;
color:var(--mut);transition:.2s}
nav a:hover{color:#fff;background:rgba(124,77,255,.2)}
h1,h2,h3{font-family:var(--fd);letter-spacing:-.01em;text-wrap:balance}
h1{font-size:clamp(2.1rem,5vw,3.1rem);font-weight:860;line-height:1;
margin:2.2rem 0 .5rem;text-shadow:0 0 40px rgba(124,77,255,.35)}
h2{font-size:clamp(1.4rem,3vw,1.9rem);font-weight:820;margin-top:2.6rem}
h3{font-size:1.05rem;font-weight:740;margin:0 0 .4rem}
.lead{color:var(--mut);max-width:52rem;font-size:1.05rem}
.muted{color:var(--mut);font-size:.85rem}
.bar{display:flex;height:16px;border-radius:999px;overflow:hidden;
background:rgba(255,255,255,.05);margin:1.3rem 0;border:1px solid var(--line)}
.s-ingested{background:#3a3358}.s-analysed{background:#2f5f8a}
.s-briefed{background:#b08a1e}.s-panels{background:#7c4dff}
.s-keyframes{background:var(--plasma)}.s-video{background:#1f9e7a}
.s-published{background:var(--teal)}
.pill{display:inline-block;padding:.12rem .6rem;border-radius:999px;
font-size:.72rem;font-family:var(--fm);text-transform:uppercase;
letter-spacing:.04em;border:1px solid var(--line);background:rgba(255,255,255,.05)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));
gap:1.1rem;margin:1.6rem 0}
.card{border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;
background:linear-gradient(150deg,rgba(124,77,255,.16),rgba(10,10,22,.72));
box-shadow:0 20px 50px rgba(0,0,0,.32);text-decoration:none;
transition:transform .2s,border-color .2s}
.card:hover{transform:translateY(-3px);border-color:rgba(43,227,194,.5)}
.card img{width:100%;aspect-ratio:1;object-fit:cover;display:block}
.card .pad{padding:.85rem .95rem 1.05rem}.card h3{margin:.1rem 0 .25rem;color:#fff}
.card .bar{height:8px;margin:.7rem 0 0}
table{border-collapse:collapse;width:100%;margin:1.2rem 0 2.5rem}
th,td{text-align:left;padding:.55rem .7rem;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--gold);font-family:var(--fm);font-size:.72rem;
text-transform:uppercase;letter-spacing:.08em}
.theme{color:var(--amethyst);font-size:.8rem;margin-right:.45rem;white-space:nowrap}
.legend{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
gap:.7rem;margin:1.4rem 0}
.legend div{border:1px solid var(--line);border-radius:12px;padding:.7rem .9rem;
font-size:.9rem;background:rgba(255,255,255,.03)}
.site-footer{border-top:1px solid var(--line);margin-top:3.5rem;
background:rgba(6,8,14,.6)}
.site-footer .wrap{padding:1.8rem clamp(1rem,4vw,2rem) 2.4rem;
color:var(--mut);font-size:.88rem}
.stage-flow{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:1.4rem 0}
.stage-flow .pill{font-size:.78rem;padding:.28rem .7rem}
.stage-flow span.arrow{color:var(--gold)}
.doc{max-width:52rem}
.doc h1{margin-top:1.6rem}.doc h2{padding-top:1.5rem;border-top:1px solid var(--line)}
.doc h3{margin-top:1.7rem}.doc p,.doc li{color:#dcd8ee}.doc li{margin:.2rem 0}
.doc code{border:1px solid var(--line);border-radius:5px;padding:.05rem .35rem;
font-family:var(--fm);font-size:.84em;background:rgba(124,77,255,.12)}
.doc pre{border:1px solid var(--line);border-radius:12px;padding:1rem 1.1rem;
overflow-x:auto;background:rgba(3,4,10,.6)}
.doc pre code{background:none;border:none;padding:0;font-size:.8rem;
line-height:1.5;color:#cdc8e6}
.doc blockquote{border-left:3px solid var(--gold);margin:1.2rem 0;
padding:.3rem 1rem;color:var(--mut);background:rgba(255,255,255,.03);
border-radius:0 8px 8px 0}
.doc hr{border:none;border-top:1px solid var(--line);margin:2rem 0}
.doc table{margin:1.2rem 0}.doc td{color:#dcd8ee}
/* faceted picker + pattern chooser */
.pc-facets{display:flex;flex-direction:column;gap:.6rem;margin:1.5rem 0 1.4rem;
padding:1rem 1.1rem;border:1px solid var(--line);border-radius:var(--radius);
background:rgba(255,255,255,.03)}
.pc-frow{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center}
.pc-flabel{color:var(--gold);font-family:var(--fm);font-size:.68rem;
text-transform:uppercase;letter-spacing:.1em;width:5.4rem;flex:none}
.pc-chip{cursor:pointer;user-select:none;border:1px solid var(--line);
background:rgba(255,255,255,.05);color:var(--text);border-radius:999px;
padding:.28rem .8rem;font-size:.83rem;transition:.15s}
.pc-chip:hover{border-color:var(--teal)}
.pc-chip.on{background:var(--violet);border-color:var(--violet);color:#fff;
font-weight:640;box-shadow:0 0 18px rgba(124,77,255,.4)}
.pc-chip.lane-recon.on{background:var(--teal);border-color:var(--teal);color:#062f28}
.pc-chip.lane-release.on{background:var(--gold);border-color:var(--gold);color:#241700}
.pc-chip.lane-hero.on{background:var(--plasma);border-color:var(--plasma);color:#2a0620}
.pc-clear{margin-left:auto;color:var(--mut);cursor:pointer;font-size:.82rem;
background:none;border:none;text-decoration:underline}
.pc-count{color:var(--mut);font-family:var(--fm);font-size:.82rem;margin:.2rem 0 1rem}
.pc-group{margin:0 0 2.2rem}
.pc-group-head{display:flex;align-items:baseline;gap:.7rem;flex-wrap:wrap;
margin:1.8rem 0 1rem;padding-bottom:.5rem;border-bottom:1px solid var(--line)}
.pc-group-head h2{margin:0;font-size:1.3rem}
.pc-group-head span{color:var(--mut);font-size:.9rem}
.pc-group.hidden{display:none}
.pc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));
gap:1rem}
.pc-card{border:1px solid var(--line);border-radius:var(--radius);
padding:1.05rem 1.1rem;display:flex;flex-direction:column;gap:.55rem;
background:linear-gradient(155deg,rgba(124,77,255,.14),rgba(10,10,22,.66));
transition:transform .18s,border-color .18s}
.pc-card:hover{transform:translateY(-2px);border-color:rgba(43,227,194,.45)}
.pc-card.hidden{display:none}
.pc-card h3{margin:0;font-size:1.08rem;line-height:1.2;color:#fff}
.pc-kicker{font-family:var(--fm);font-size:.68rem;text-transform:uppercase;
letter-spacing:.12em;color:var(--gold)}
.pc-best{font-size:.96rem;color:#efeaff;margin:0;font-weight:600;line-height:1.35}
.pc-task{display:inline-flex;align-self:flex-start;font-family:var(--fm);
font-size:.75rem;padding:.2rem .6rem;border-radius:8px;color:#062f28;
background:var(--teal);font-weight:700}
.pc-badges{display:flex;flex-wrap:wrap;gap:.3rem;align-items:center}
.pc-b{font-family:var(--fm);font-size:.66rem;text-transform:uppercase;
letter-spacing:.05em;border-radius:999px;padding:.1rem .55rem;
border:1px solid transparent}
.pc-b.recon{background:rgba(43,227,194,.16);color:var(--teal);border-color:rgba(43,227,194,.4)}
.pc-b.release{background:rgba(255,207,110,.16);color:var(--gold-soft);border-color:rgba(255,207,110,.4)}
.pc-b.hero{background:rgba(255,95,209,.16);color:#ffc7ec;border-color:rgba(255,95,209,.4)}
.pc-b.tier{background:rgba(255,255,255,.06);color:#cfc9e6}
.pc-b.built{background:rgba(43,227,194,.16);color:var(--teal);border-color:rgba(43,227,194,.4)}
.pc-b.designed{background:rgba(255,255,255,.06);color:#c9c3e0}
.pc-b.planned{background:rgba(201,166,255,.16);color:var(--amethyst);border-color:rgba(201,166,255,.4)}
.pc-sum{color:#d6d1ea;font-size:.9rem;margin:0}
.pc-tags{display:flex;flex-wrap:wrap;gap:.3rem}
.pc-tag{font-family:var(--fm);font-size:.7rem;color:var(--amethyst);
background:rgba(124,77,255,.14);border-radius:5px;padding:.06rem .4rem}
.pc-meta{font-size:.82rem;color:var(--mut);line-height:1.5}
.pc-meta b{color:#d7d1ea;font-weight:600}
.pc-more{border:none;background:none;color:var(--teal);cursor:pointer;
font-size:.82rem;text-align:left;padding:0}
.pc-detail{display:none;font-size:.85rem;color:#d3cee6;
border-top:1px solid var(--line);padding-top:.6rem;margin-top:.2rem}
.pc-detail.open{display:block}.pc-detail p{margin:.25rem 0}
.pc-add{margin-top:.2rem;border:1px solid var(--teal);background:none;
color:var(--teal);border-radius:8px;padding:.4rem;cursor:pointer;
font-size:.85rem;font-weight:640}
.pc-add.added{background:var(--teal);color:#062f28}
.pc-tray{position:sticky;top:.6rem;z-index:5;
border:1px solid var(--line);border-radius:var(--radius);padding:.85rem 1.05rem;
margin:0 0 1.4rem;background:rgba(12,12,26,.9);backdrop-filter:blur(12px)}
.pc-tray h2{margin:.1rem 0 .5rem;font-size:1.05rem}
.pc-tray-empty{color:var(--mut);font-size:.88rem}
.pc-tray ol{margin:.3rem 0 0;padding-left:1.2rem}
.pc-tray li{margin:.15rem 0;font-size:.9rem}
.pc-tray li button{border:none;background:none;color:var(--plasma);cursor:pointer;
font-size:.9rem;margin-left:.3rem}
@media(max-width:560px){.pc-flabel{width:100%}.brand-text{display:none}}
/* ---- fancy bits: motion + promo ---- */
@view-transition{navigation:auto}
.scroll-progress{position:fixed;top:0;left:0;right:0;z-index:60;height:2px;
pointer-events:none}
.scroll-progress i{display:block;height:100%;width:100%;transform-origin:left;
transform:scaleX(0);background:linear-gradient(90deg,var(--gold),var(--violet),var(--teal))}
.site-header{transition:padding .2s,background .2s,border-color .2s}
.site-header.is-condensed .site-header{padding:.4rem clamp(1rem,4vw,2rem)}
.site-header.is-condensed{box-shadow:0 10px 30px rgba(0,0,0,.35)}
.eyebrow{margin:0 0 .7rem;color:var(--gold);font-family:var(--fm);font-size:.76rem;
font-weight:640;letter-spacing:.2em;text-transform:uppercase}
.eyebrow::before{content:"// ";color:rgba(255,207,110,.55)}
.button{display:inline-flex;align-items:center;gap:.5rem;min-height:2.7rem;
padding:.65rem 1.3rem;border-radius:999px;text-decoration:none;font-weight:720;
border:1px solid transparent;cursor:pointer;transition:transform .2s,box-shadow .2s,
background .2s,border-color .2s}
.button:hover{transform:translateY(-2px)}
.button-primary{background:linear-gradient(135deg,var(--gold),var(--plasma) 60%,var(--violet));
color:#1a0e05;box-shadow:0 8px 30px rgba(255,207,110,.28)}
.button-secondary{border-color:var(--line);background:rgba(255,255,255,.06);color:#fff}
.button-secondary:hover{border-color:rgba(43,227,194,.6);background:rgba(43,227,194,.1)}
.promo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
gap:1.1rem;margin:1.6rem 0}
.promo-card{position:relative;display:flex;flex-direction:column;gap:.6rem;
padding:1.3rem 1.35rem;border:1px solid var(--line);border-radius:var(--radius);
background:linear-gradient(155deg,rgba(124,77,255,.16),rgba(10,10,22,.72));
box-shadow:0 20px 50px rgba(0,0,0,.32);text-decoration:none;
transition:transform .2s,border-color .2s}
.promo-card:hover{transform:translateY(-4px);border-color:rgba(43,227,194,.5)}
.promo-card h3{font-size:1.25rem;color:#fff;margin:0}
.promo-card .tagline{color:var(--gold-soft);font-size:.92rem;margin:0}
.promo-card p{color:var(--mut);font-size:.92rem;margin:0}
.promo-card .promo-foot{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;
margin-top:auto;padding-top:.5rem}
.promo-card .go{color:var(--teal);font-weight:640;font-size:.9rem}
.st{font-family:var(--fm);font-size:.66rem;text-transform:uppercase;
letter-spacing:.06em;border-radius:999px;padding:.12rem .6rem;border:1px solid transparent}
.st-live{background:rgba(43,227,194,.16);color:var(--teal);border-color:rgba(43,227,194,.4)}
.st-development{background:rgba(255,207,110,.16);color:var(--gold-soft);border-color:rgba(255,207,110,.4)}
.st-design{background:rgba(201,166,255,.16);color:var(--amethyst);border-color:rgba(201,166,255,.4)}
.st-concept{background:rgba(255,255,255,.06);color:#c9c3e0}
/* Reveal-on-scroll. Gated on html.js (set synchronously in <head>) so
   there is no first-paint flash. The is-visible resting state is fully
   visible, and a JS fallback timer adds it to everything shortly after
   load, so content can never be stranded invisible if the observer or a
   paused animation misbehaves. */
html.js .pc-card,html.js .card,html.js .reveal{opacity:0;
transform:translateY(18px);
transition:opacity .6s cubic-bezier(.16,1,.3,1),transform .6s cubic-bezier(.16,1,.3,1)}
html.js .pc-card.is-visible,html.js .card.is-visible,html.js .reveal.is-visible{
opacity:1;transform:none}
@media(prefers-reduced-motion:reduce){
html.js .pc-card,html.js .card,html.js .reveal{opacity:1;transform:none;transition:none}
.scroll-progress{display:none}}
"""

_FONT_FACES = (
    '@font-face{{font-family:"Archivo Var";'
    'src:url("{up}assets/fonts/archivo-var.woff2") format("woff2-variations");'
    'font-weight:100 900;font-display:swap}}'
    '@font-face{{font-family:"JetBrains Mono Var";'
    'src:url("{up}assets/fonts/jetbrains-mono-var.woff2") format("woff2-variations");'
    'font-weight:100 800;font-display:swap}}')


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _page(title: str, body: str, depth: int = 0) -> str:
    up = "../" * depth
    fonts = _FONT_FACES.format(up=up)
    return f"""<!doctype html>
<html lang="en-AU"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} - Infinity Engine</title>
<script>document.documentElement.classList.add('js')</script>
<style>{fonts}{CSS}</style></head><body>
<div class="scroll-progress"><i></i></div>
<header class="site-header"><div class="wrap">
<a class="brand" href="{up}index.html">
<span class="brand-mark"></span>
<span class="brand-text"><strong>Infinity Engine</strong>
<span>i C. infinity</span></span></a>
<nav><a href="{up}index.html">Progress</a>
<a href="{up}patterns.html">Patterns</a>
<a href="{up}cast.html">Cast</a>
<a href="{up}models.html">Models</a>
<a href="{up}frontier.html">Frontier</a>
<a href="{up}loras.html">LoRAs</a>
<a href="{up}compute.html">Compute</a>
<a href="{up}recon.html">Recon</a>
<a href="{up}projects.html">Projects</a>
<a href="{up}pipeline.html">How it works</a>
<a href="{up}workflow.html">Operator guide</a>
<a href="{UNIVERSE_BASE}/">Music universe</a></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="site-footer"><div class="wrap">A live monitor of the i C.
infinity visual pipeline. Regenerated from the song vault as pieces
complete. Lyrics live with the music, not here.<br>Luke &times; Claude.</div>
</footer>
<script>
(function(){{var h=document.querySelector('.site-header'),
p=document.querySelector('.scroll-progress i');
function s(){{var y=scrollY||0,d=document.body.scrollHeight-innerHeight;
if(p)p.style.transform='scaleX('+(d>0?Math.min(y/d,1):0)+')';
if(h)h.classList.toggle('is-condensed',y>24)}}
addEventListener('scroll',s,{{passive:true}});s();
var els=document.querySelectorAll('.pc-card,.card,.reveal');
var io=new IntersectionObserver(function(es){{es.forEach(function(e){{
if(e.isIntersecting){{e.target.classList.add('is-visible');io.unobserve(e.target)}}}})}},
{{rootMargin:'0px 0px -6% 0px'}});
els.forEach(function(el){{io.observe(el)}});
// safety net: nothing stays hidden, even if the observer never fires or
// a transition is frozen. Snap instantly (transition:none) so opacity
// can't be stranded mid-interpolation.
setTimeout(function(){{els.forEach(function(el){{
if(!el.classList.contains('is-visible')){{el.style.transition='none';
el.classList.add('is-visible')}}}})}},1400);}})();
</script>
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

    # Pattern chooser, registry pickers and promo (data-driven).
    for builder in (render_patterns, render_cast, render_models, render_loras,
                    render_frontier, render_compute, render_recon,
                    render_projects):
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
document.querySelectorAll('.pc-grid').forEach(g=>{
  Array.prototype.slice.call(g.children).forEach((c,i)=>{c.dataset.idx=i})});
function pcToggle(el){const g=el.dataset.group,v=el.dataset.value;
  const s=pcState[g];if(s.has(v)){s.delete(v);el.classList.remove('on')}
  else{s.add(v);el.classList.add('on')}pcFilter()}
function pcClear(){for(const g in pcState)pcState[g].clear();
  document.querySelectorAll('.pc-chip[data-group].on').forEach(c=>c.classList.remove('on'));
  pcFilter()}
function pcSort(el){document.querySelectorAll('.pc-sort').forEach(b=>b.classList.remove('on'));
  el.classList.add('on');const k=el.dataset.sort,num=el.dataset.num==='1';
  document.querySelectorAll('.pc-grid').forEach(g=>{
    const cs=Array.prototype.slice.call(g.children);
    cs.sort((a,b)=>k==='idx'?(+a.dataset.idx)-(+b.dataset.idx)
      :num?(parseFloat(b.dataset[k]||0))-(parseFloat(a.dataset[k]||0))
      :(a.dataset[k]||'').localeCompare(b.dataset[k]||''));
    cs.forEach(c=>g.appendChild(c))})}
function pcMatch(card){for(const g in pcState){const sel=pcState[g];
  if(!sel.size)continue;
  const vals=(card.dataset[g]||'').split(' ').filter(Boolean);
  if(![...sel].some(v=>vals.includes(v)))return false}return true}
function pcFilter(){let n=0;document.querySelectorAll('.pc-card').forEach(c=>{
  const ok=pcMatch(c);c.classList.toggle('hidden',!ok);if(ok)n++});
  document.querySelectorAll('.pc-group').forEach(g=>{
    const any=[...g.querySelectorAll('.pc-card')].some(c=>!c.classList.contains('hidden'));
    g.classList.toggle('hidden',!any)});
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


def _card_div(attrs: dict, inner: str) -> str:
    data = " ".join(f'data-{k}="{" ".join(v)}"' for k, v in attrs.items())
    return f'<div class="pc-card" {data}>{inner}</div>'


def render_picker(out_dir: Path, *, filename: str, title: str, noun: str,
                  lead: str, facet_defs: list, cards: list | None = None,
                  groups: list | None = None, extra: str = "",
                  sorts: list | None = None) -> Path:
    """Generic faceted card picker. facet_defs is (label, group, [values]);
    each card is (attrs_dict, html). Pass `groups` as a list of
    (label, blurb, [cards]) to render labelled sections instead of a flat
    grid; empty sections hide themselves as filters narrow. `sorts` is a
    list of (label, key, numeric_bool) that adds a sort toggle row."""
    facet_html = "".join(_facet_row(lbl, grp, vals)
                         for lbl, grp, vals in facet_defs if vals)
    if sorts:
        chips = ('<button class="pc-chip pc-sort on" data-sort="idx" '
                 'data-num="0" onclick="pcSort(this)">Default</button>')
        for label, key, numeric in sorts:
            chips += (f'<button class="pc-chip pc-sort" data-sort="{key}" '
                      f'data-num="{1 if numeric else 0}" '
                      f'onclick="pcSort(this)">{_esc(label)}</button>')
        facet_html += (f'<div class="pc-frow"><span class="pc-flabel">Sort</span>'
                       f'{chips}</div>')
    facet_html += ('<div class="pc-frow"><button class="pc-clear" '
                   'onclick="pcClear()">clear all filters</button></div>')
    if groups is not None:
        blocks = []
        for label, blurb, gcards in groups:
            if not gcards:
                continue
            inner = "".join(_card_div(a, h) for a, h in gcards)
            blocks.append(
                f'<section class="pc-group">'
                f'<div class="pc-group-head"><h2>{_esc(label)}</h2>'
                f'<span>{_esc(blurb)}</span></div>'
                f'<div class="pc-grid">{inner}</div></section>')
        grid = "".join(blocks)
    else:
        grid = ('<div class="pc-grid">'
                + "".join(_card_div(a, h) for a, h in (cards or []))
                + '</div>')
    body = (
        f"<h1>{_esc(title)}</h1>"
        f"<p class='lead'>{lead}</p>"
        f'<div class="pc-facets">{facet_html}</div>'
        '<div class="pc-count" id="pcCount"></div>'
        f'{grid}{extra}'
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


# Category -> (heading, what it's for). Drives the grouped model picker.
MODEL_CATEGORIES = {
    "video": ("Video", "Text and image to video, the hero output"),
    "control": ("Control and motion", "Pose, depth, segmentation, directed shots"),
    "image": ("Image", "Keyframes, comic panels, character consistency"),
    "tts": ("Voice (TTS)", "Text to speech and voice cloning"),
    "stt": ("Speech to text", "Transcription and the caption backbone"),
    "lipsync": ("Lip-sync and avatars", "Audio-driven talking performance"),
    "llm": ("Language", "Ideation and scripting"),
    "embeddings": ("Embeddings", "Semantic search over the vault"),
    "worlds": ("3D and worlds", "Meshes, environments and explorable worlds"),
}


WORLDS_SUBTYPES = ["object", "world", "capture", "360"]
SUBTYPE_ORDER = ["object", "world", "capture", "360", "realtime"]


def _subtype(m: dict) -> str | None:
    """A card's sub-type for the Type facet: explicit `subtype:` wins;
    worlds entries infer object/world/capture/360; others have none."""
    if m.get("subtype"):
        return str(m["subtype"])
    if m.get("category") == "worlds":
        return _worlds_subtype(m)
    return None


def _worlds_subtype(m: dict) -> str:
    """Differentiate 3D entries: single asset vs whole world vs capture
    tool vs 360/equirectangular. Explicit `subtype:` wins; else inferred."""
    if m.get("subtype"):
        return str(m["subtype"])
    t = " ".join(str(m.get(k, "")) for k in ("task", "strength", "name")).lower()
    if any(w in t for w in ("360", "panorama", "equirect", "skybox")):
        return "360"
    if any(w in t for w in ("splat", "photogramm", "camera solve", "capture",
                            "realityscan", "polycam", "postshot", "luma")):
        return "capture"
    if any(w in t for w in ("world", "scene", "environment")):
        return "world"
    return "object"


# Content note: is a tool censored, or NSFW-capable. Open weights can be
# run without a provider filter (and uncensored fine-tunes exist), so they
# read "unfiltered"; closed tools enforce a policy ("filtered"), and the
# big labs block NSFW/celebrity/violence hard ("strict"). Geometry, capture,
# STT and embeddings aren't content-gated ("n/a", shown as no badge).
# An explicit `content:` field in the YAML always wins.
CONTENT_BADGE = {"unfiltered": "planned", "filtered": "designed",
                 "strict": "hero"}
_STRICT_FRONTIER = {"sora", "veo-3", "midjourney", "firefly-image",
                    "firefly-video", "gemini-image"}
_NON_CONTENT_CATS = {"worlds", "control", "stt", "embeddings"}


def _content(m: dict, is_open: bool) -> str:
    if m.get("content"):
        return str(m["content"])
    if m.get("category") in _NON_CONTENT_CATS:
        return "n/a"
    if is_open:
        return "unfiltered"
    return "strict" if m.get("id") in _STRICT_FRONTIER else "filtered"


def _content_badge(content: str) -> str:
    if content not in CONTENT_BADGE:
        return ""
    return f'<span class="pc-b {CONTENT_BADGE[content]}">{content}</span>'


def _sort_attrs(m: dict, sortnum) -> dict:
    a = {"sortname": [str(m.get("name", m.get("id", ""))).lower()],
         "sortnum": [str(sortnum or 0)]}
    if m.get("category") == "worlds":
        a["subtype"] = [_worlds_subtype(m)]
    return a


def _model_card(m: dict) -> tuple:
    status = m.get("status", "watching")
    st_class = {"active": "built", "recon": "planned",
                "watching": "designed"}.get(status, "designed")
    comfy = m.get("comfy", "no")
    commercial = ("Apache" in str(m.get("licence", ""))
                  or "MIT" in str(m.get("licence", "")))
    inner = (
        f'<span class="pc-kicker">{_esc(m.get("category",""))}</span>'
        f'<h3>{_esc(m.get("name", m["id"]))}</h3>'
        f'<span class="pc-task">{_esc(m.get("task",""))}</span>'
        f'<p class="pc-best">{_esc(m.get("why",""))}</p>'
        '<div class="pc-badges">'
        f'<span class="pc-b {st_class}">{_esc(status)}</span>'
        + ('<span class="pc-b built">ComfyUI</span>' if comfy == "yes" else "")
        + (f'<span class="pc-b {"built" if commercial else "hero"}">'
           f'{"commercial" if commercial else "restricted"}</span>')
        + _content_badge(_content(m, is_open=True))
        + '</div>'
        f'<div class="pc-meta"><b>Licence:</b> {_esc(m.get("licence",""))}<br>'
        f'<b>VRAM:</b> {_esc(m.get("vram_gb","?"))} GB '
        f'&middot; <b>HF likes:</b> {_esc(m.get("likes","?"))}</div>'
        + (f'<a class="pc-more" href="https://huggingface.co/'
           f'{_esc(m.get("hf",""))}" target="_blank" rel="noopener">'
           f'Hugging Face &rarr;</a>' if m.get("hf")
           else (f'<a class="pc-more" href="{_esc(m.get("repo",""))}" '
                 'target="_blank" rel="noopener">Repo &rarr;</a>'
                 if m.get("repo") else "")))
    content = _content(m, is_open=True)
    attrs = {
        "category": [str(m.get("category", ""))],
        "status": [status],
        "licence": ["commercial" if commercial else "restricted"],
        **_sort_attrs(m, m.get("likes")),
    }
    if content in CONTENT_BADGE:
        attrs["content"] = [content]
    return attrs, inner


def render_models(out_dir: Path) -> Path | None:
    models = _load_catalog(out_dir, "catalog/models.yaml", "models")
    if not models:
        return None
    groups = []
    for cat, (label, blurb) in MODEL_CATEGORIES.items():
        gcards = [_model_card(m) for m in models if m.get("category") == cat]
        groups.append((label, blurb, gcards))
    # any categories not in the map, appended so nothing is dropped
    mapped = set(MODEL_CATEGORIES)
    for cat in _sorted_uniq(models, "category"):
        if cat not in mapped:
            gcards = [_model_card(m) for m in models
                      if m.get("category") == cat]
            groups.append((cat.title(), "", gcards))
    world_types = [s for s in WORLDS_SUBTYPES
                   if any(m.get("category") == "worlds"
                          and _worlds_subtype(m) == s for m in models)]
    facet_defs = [
        ("Category", "category", _sorted_uniq(models, "category")),
        ("3D type", "subtype", world_types),
        ("Status", "status", ["active", "recon", "watching"]),
        ("Licence", "licence", ["commercial", "restricted"]),
        ("Content", "content", ["unfiltered", "filtered", "strict"]),
    ]
    return render_picker(
        out_dir, filename="models.html", title="Model picker", noun="model",
        sorts=[("A-Z", "sortname", False), ("Most liked", "sortnum", True)],
        lead=("Open-weight models grouped by what they do, sourced from "
              "Hugging Face. The teal chip on each card is the task; the line "
              "under it is what it's best at. Status: active is in the working "
              "stack, recon is being tested, watching is on the radar. Filter "
              "to narrow; the recon watcher keeps this fresh."),
        facet_defs=facet_defs, groups=groups)


# Which fine-tune approach each troupe warrants (the tiering: don't LoRA
# everyone). Tier label doubles as the teal chip on the card.
CAST_LORA_TIER = {
    "music-universe": ("hero LoRA",
                       "Train first: the recurring leads that carry the universe"),
    "queens": ("template LoRA",
               "Cultural-translation templates; train a Queen as you use her"),
    "amity-crew": ("reference",
                   "Consistent crew avatars; reference-first, LoRA if they recur on screen"),
    "two-dogs": ("reference", "Podcast hosts; reference or a light LoRA"),
}


def _lora_status_class(status: str) -> str:
    return {"active": "built", "trained": "built", "planned": "designed",
            "recon": "planned", "concept": "planned"}.get(status, "planned")


def render_loras(out_dir: Path) -> Path | None:
    cast = _load_catalog(out_dir, "catalog/cast.yaml", "cast")
    records = _load_catalog(out_dir, "catalog/loras.yaml", "loras")
    if not cast and not records:
        return None
    # Split loras.yaml into trained cast-LoRA records (keyed by character)
    # and external style/detail LoRAs.
    by_char = {r["character"]: r for r in records if r.get("character")}
    external = [r for r in records if not r.get("character")]

    def cast_card(c: dict) -> tuple:
        troupe = c.get("troupe", "")
        tier_label, tier_note = CAST_LORA_TIER.get(troupe, ("reference", ""))
        rec = by_char.get(c["id"])
        status = (rec.get("status") if rec else None) or (
            "planned" if troupe == "music-universe" else "concept")
        priv = c.get("private", False) or (rec.get("private") if rec else False)
        trigger = rec.get("trigger") if rec else None
        meta = f'<b>Role:</b> {_esc(c.get("role",""))}'
        if trigger:
            meta += f'<br><b>Trigger:</b> <code>{_esc(trigger)}</code>'
        if tier_note:
            meta += f'<br><span class="muted">{_esc(tier_note)}</span>'
        inner = (
            f'<span class="pc-kicker">{_esc(c.get("represents",""))}</span>'
            f'<h3>{_esc(c.get("name", c["id"]))}</h3>'
            f'<span class="pc-task">{_esc(tier_label)}</span>'
            f'<p class="pc-best">{_esc(c.get("summary",""))}</p>'
            '<div class="pc-badges">'
            f'<span class="pc-b {_lora_status_class(status)}">{_esc(status)}</span>'
            + ('<span class="pc-b hero">private</span>' if priv else "")
            + '</div>'
            f'<div class="pc-meta">{meta}</div>')
        attrs = {
            "troupe": [troupe],
            "tier": [tier_label.split()[0]],
            "status": [status],
            "visibility": ["private" if priv else "shareable"],
        }
        return attrs, inner

    groups = []
    for troupe, (label, blurb) in CAST_TROUPES.items():
        gcards = [cast_card(c) for c in cast if c.get("troupe") == troupe]
        groups.append((label, blurb, gcards))
    # External style/detail LoRAs.
    ext_cards = []
    for r in external:
        status = r.get("status", "recon")
        inner = (
            f'<span class="pc-kicker">{_esc(r.get("source","hugging face"))}</span>'
            f'<h3>{_esc(r.get("name", r["id"]))}</h3>'
            f'<span class="pc-task">{_esc(r.get("kind","style"))}</span>'
            f'<p class="pc-best">{_esc(r.get("why",""))}</p>'
            '<div class="pc-badges">'
            f'<span class="pc-b {_lora_status_class(status)}">{_esc(status)}</span></div>'
            f'<div class="pc-meta"><b>Base:</b> {_esc(r.get("base","?"))} '
            f'&middot; <b>Trigger:</b> <code>{_esc(r.get("trigger","-"))}</code></div>')
        ext_cards.append(({"troupe": ["external"], "tier": ["style"],
                           "status": [status],
                           "visibility": ["shareable"]}, inner))
    groups.append(("Style and detail (external)",
                   "Style/detail LoRAs the watcher flags from Hugging Face to vet",
                   ext_cards))

    n = len(cast)
    facet_defs = [
        ("Troupe", "troupe", list(CAST_TROUPES) + ["external"]),
        ("Tier", "tier", ["hero", "template", "reference", "style"]),
        ("Status", "status", ["active", "trained", "planned", "concept"]),
        ("Visibility", "visibility", ["shareable", "private"]),
    ]
    return render_picker(
        out_dir, filename="loras.html", title="LoRA picker", noun="LoRA",
        lead=(f"The fine-tune plan across the whole {n}-character map, mirrored "
              "from the Cast. The teal chip is the tier: <b>hero LoRA</b> for "
              "the leads to train first, <b>template LoRA</b> for the Queens as "
              "cultural-translation templates, <b>reference</b> for ensembles "
              "held with reference images until they earn a LoRA. Don't train "
              "everyone; train what recurs. Style and detail LoRAs from Hugging "
              "Face sit at the bottom."),
        facet_defs=facet_defs, groups=groups)


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
        lead=intro, facet_defs=facet_defs, cards=cards,
        extra=_sources_section(out_dir))


SOURCE_TYPES = {
    "leaderboard": ("Leaderboards", "Rank quality and preference"),
    "channel": ("Trusted channels", "Practitioner signal, ahead of the boards"),
    "community": ("Community and discovery", "Raw new releases"),
}


def _sources_section(out_dir: Path) -> str:
    sources = _load_catalog(out_dir, "catalog/sources.yaml", "sources")
    if not sources:
        return ""
    blocks = []
    for kind, (label, blurb) in SOURCE_TYPES.items():
        rows = [s for s in sources if s.get("type") == kind]
        if not rows:
            continue
        items = "".join(
            f'<div><a href="{_esc(s.get("url","#"))}" target="_blank" '
            f'rel="noopener">{_esc(s.get("name",""))}</a> '
            f'<span class="pc-tag">{_esc(s.get("category",""))}</span>'
            f'<br><span class="muted">{_esc(s.get("note",""))}</span></div>'
            for s in rows)
        blocks.append(
            f'<div class="pc-group-head"><h2>{_esc(label)}</h2>'
            f'<span>{_esc(blurb)}</span></div>'
            f'<div class="legend">{items}</div>')
    return ('<h2 style="margin-top:2.8rem">Where candidates come from</h2>'
            "<p class='muted' style='max-width:52rem'>Three kinds of signal, "
            "used together. The watcher automates the popularity scan; these "
            "add quality and practitioner judgement. The funnel stays: "
            "discover, rank, then vet on your own footage.</p>"
            + "".join(blocks))


CAST_TROUPES = {
    "music-universe": ("Music universe cast",
                       "The recurring leads of the i C. infinity songs"),
    "queens": ("The Queens: Council of Aura",
               "24 heritage archetypes; also templates for culturally "
               "translated music"),
    "amity-crew": ("Amity AI film crew",
                   "The AI filmmaking assistants, each an Australian animal spirit"),
    "two-dogs": ("Two Dogs podcast",
                 "Spirit-animal hosts; guests bring their own animal"),
}


def _cast_card(c: dict) -> tuple:
    status = c.get("status", "concept")
    st_class = {"active": "built", "planned": "designed",
                "concept": "planned"}.get(status, "planned")
    priv = c.get("private", False)
    inner = (
        f'<span class="pc-kicker">{_esc(c.get("represents",""))}</span>'
        f'<h3>{_esc(c.get("name", c["id"]))}</h3>'
        f'<span class="pc-task">{_esc(c.get("role",""))}</span>'
        f'<p class="pc-best">{_esc(c.get("summary",""))}</p>'
        '<div class="pc-badges">'
        f'<span class="pc-b {st_class}">{_esc(status)}</span>'
        + ('<span class="pc-b hero">private</span>' if priv else "") + '</div>')
    attrs = {
        "troupe": [str(c.get("troupe", ""))],
        "status": [status],
        "visibility": ["private" if priv else "shareable"],
    }
    return attrs, inner


def render_cast(out_dir: Path) -> Path | None:
    cast = _load_catalog(out_dir, "catalog/cast.yaml", "cast")
    if not cast:
        return None
    groups = []
    for troupe, (label, blurb) in CAST_TROUPES.items():
        gcards = [_cast_card(c) for c in cast if c.get("troupe") == troupe]
        groups.append((label, blurb, gcards))
    n = len(cast)
    facet_defs = [
        ("Troupe", "troupe", list(CAST_TROUPES)),
        ("Status", "status", ["active", "planned", "concept"]),
        ("Visibility", "visibility", ["shareable", "private"]),
    ]
    return render_picker(
        out_dir, filename="cast.html", title="Cast", noun="character",
        lead=(f"The {n} characters of the universe, across troupes. A "
              "character is who is in frame; a LoRA on the LoRAs page is the "
              "fine-tune that locks their look. The teal chip is each one's "
              "role. Filter by troupe to focus, or by visibility to find what "
              "stays private."),
        facet_defs=facet_defs, groups=groups)


FRONTIER_CATEGORIES = {
    "video": ("Video", "Text and image to video"),
    "image": ("Image", "Stills, keyframes and art"),
    "voice": ("Voice", "Text to speech and cloning"),
    "avatar": ("Avatar", "Talking-head and presenter"),
    "music": ("Music", "Song generation"),
    "upscale": ("Upscale and enhance", "Finishing and resolution"),
    "language": ("Language", "Scripting and ideation"),
    "worlds": ("3D and worlds", "Meshes, environments, world models and capture"),
}

_AFFIL = {
    "yes": ("built", "affiliate"),
    "referral": ("release", "referral only"),
    "no": ("designed", "no program"),
    "unknown": ("designed", "checking"),
}


def _frontier_card(m: dict) -> tuple:
    # YAML turns bare yes/no into booleans; normalise back to strings.
    raw = m.get("affiliate_status", "unknown")
    aff = {True: "yes", False: "no"}.get(raw, str(raw))
    aff_class, aff_label = _AFFIL.get(aff, _AFFIL["unknown"])
    links = (f'<a class="pc-more" href="{_esc(m.get("url","#"))}" '
             'target="_blank" rel="noopener">Visit &rarr;</a>')
    if m.get("affiliate_url"):
        links += (f' &middot; <a class="pc-more" href="'
                  f'{_esc(m["affiliate_url"])}" target="_blank" '
                  'rel="noopener">Affiliate program &rarr;</a>')
    terms = (f'<br><b>Affiliate:</b> {_esc(m.get("affiliate_terms",""))}'
             if m.get("affiliate_terms") else "")
    inner = (
        f'<span class="pc-kicker">{_esc(m.get("vendor",""))}</span>'
        f'<h3>{_esc(m.get("name", m["id"]))}</h3>'
        f'<span class="pc-task">{_esc(m.get("category",""))}</span>'
        f'<p class="pc-best">{_esc(m.get("strength",""))}</p>'
        '<div class="pc-badges">'
        f'<span class="pc-b {aff_class}">{aff_label}</span>'
        + _content_badge(_content(m, is_open=False)) + '</div>'
        f'<div class="pc-meta"><b>Access:</b> {_esc(m.get("access",""))} '
        f'&middot; <b>Price:</b> {_esc(m.get("pricing","?"))}{terms}</div>'
        f'{links}')
    aff_rank = {"yes": 3, "referral": 2, "unknown": 1, "no": 0}.get(aff, 0)
    content = _content(m, is_open=False)
    attrs = {
        "category": [str(m.get("category", ""))],
        "access": [str(m.get("access", "")).split("/")[0].strip().lower()],
        "affiliate": [aff],
        **_sort_attrs(m, aff_rank),
    }
    if content in CONTENT_BADGE:
        attrs["content"] = [content]
    return attrs, inner


def render_frontier(out_dir: Path) -> Path | None:
    models = _load_catalog(out_dir, "catalog/frontier.yaml", "frontier")
    if not models:
        return None
    groups = []
    for cat, (label, blurb) in FRONTIER_CATEGORIES.items():
        gcards = [_frontier_card(m) for m in models
                  if m.get("category") == cat]
        groups.append((label, blurb, gcards))
    world_types = [s for s in WORLDS_SUBTYPES
                   if any(m.get("category") == "worlds"
                          and _worlds_subtype(m) == s for m in models)]
    facet_defs = [
        ("Category", "category", [c for c in FRONTIER_CATEGORIES
                                  if any(m.get("category") == c
                                         for m in models)]),
        ("3D type", "subtype", world_types),
        ("Affiliate", "affiliate", ["yes", "referral", "no"]),
        ("Content", "content", ["unfiltered", "filtered", "strict"]),
    ]
    disclosure = (
        "Closed, pay-to-play frontier models: the ones with the deepest "
        "pockets behind them, worth an occasional output comparison, and the "
        "names people drop. The engine stays open-source first for ownership "
        "and cost; this is the other end of the shelf. Some links are "
        "affiliate or referral: sign up through one and the project may earn "
        "a small commission at no extra cost to you. An <b>affiliate</b> badge "
        "means a paid program exists; join it and swap in your own referral "
        "link where the card points.")
    return render_picker(
        out_dir, filename="frontier.html", title="Frontier models",
        noun="model", lead=disclosure, facet_defs=facet_defs, groups=groups,
        sorts=[("A-Z", "sortname", False),
               ("Affiliate first", "sortnum", True)])


PROJECT_STATUS = {"live": "st-live", "development": "st-development",
                  "design": "st-design", "concept": "st-concept"}


def render_projects(out_dir: Path) -> Path | None:
    projects = _load_catalog(out_dir, "projects.yaml", "projects")
    if not projects:
        return None
    cards = []
    for p in projects:
        status = p.get("status", "development")
        st_class = PROJECT_STATUS.get(status, "st-development")
        link = p.get("link", "#")
        external = link.startswith("http")
        target = ' target="_blank" rel="noopener"' if external else ""
        cards.append(
            f'<a class="promo-card reveal" href="{_esc(link)}"{target}>'
            f'<span class="st {st_class}">{_esc(status)}</span>'
            f'<h3>{_esc(p.get("name", p["id"]))}</h3>'
            f'<p class="tagline">{_esc(p.get("tagline",""))}</p>'
            f'<p>{_esc(p.get("blurb","").strip())}</p>'
            f'<div class="promo-foot"><span class="go">'
            f'{_esc(p.get("cta","Open"))} &rarr;</span></div></a>')
    body = (
        "<p class='eyebrow'>The universe</p>"
        "<h1>Projects in development</h1>"
        "<p class='lead'>The creative-universe work this engine feeds or sits "
        "beside. Some are live, most are in development or design; the tag on "
        "each says where it really is. Nothing here is finished being "
        "imagined.</p>"
        f'<div class="promo-grid">{"".join(cards)}</div>')
    path = out_dir / "projects.html"
    path.write_text(_page("Projects", body), encoding="utf-8")
    return path
