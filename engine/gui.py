"""A local control panel, so the engine is buttons not a terminal.

`python -m engine gui` (or double-click "Infinity Engine.cmd") starts a
tiny web server on 127.0.0.1 and opens a browser. Default view is "Guide
me": it reads each song's real state and shows the ONE next step as a
single big button, in plain words, no jargon. Expert mode keeps every
control for when you want them.

Nothing here is deployed: this panel touches the vault and starts renders,
so it is LOCAL ONLY, never the public site. Stdlib only (http.server +
subprocess), so it runs on a fresh Python with no extra installs.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import flow, vault
from .config import load_config, resolve
from .site import STATUS_ORDER

KINDS = ["panels", "keyframes", "video", "tts", "lipsync", "avatar"]
TIERS = ["draft", "standard", "premium"]

CSS = """
:root{--void:#05070c;--deep:#0a1420;--panel:rgba(124,77,255,.08);
--line:rgba(160,150,210,.18);--ink:#eae6ff;--mut:#a89fce;--violet:#7c4dff;
--gold:#ffcf6e;--teal:#2be3c2;--plasma:#ff5fd1;--fm:ui-monospace,"Cascadia Code",monospace}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,Segoe UI,sans-serif;color:var(--ink);
background:radial-gradient(1200px 800px at 70% -10%,rgba(124,77,255,.14),transparent),
radial-gradient(900px 700px at -10% 20%,rgba(43,227,194,.08),transparent),var(--void);
min-height:100vh;line-height:1.5}
.wrap{max-width:760px;margin:0 auto;padding:1.5rem clamp(1rem,4vw,2rem) 5rem}
header{display:flex;align-items:center;gap:.8rem;margin:.4rem 0 1.2rem}
.mark{width:38px;height:38px;border-radius:50%;flex:none;
background:radial-gradient(circle at 35% 30%,#b79bff,var(--violet) 55%,#2a1a5e)}
h1{font-size:1.4rem;margin:0}
h1 small{display:block;font-family:var(--fm);font-size:.68rem;letter-spacing:.15em;
text-transform:uppercase;color:var(--mut)}
.badge{margin-left:auto;font-family:var(--fm);font-size:.78rem;padding:.3rem .7rem;
border-radius:999px;border:1px solid var(--line);white-space:nowrap}
.badge.on{color:var(--teal);border-color:rgba(43,227,194,.5);background:rgba(43,227,194,.08)}
.badge.off{color:var(--gold);border-color:rgba(255,207,110,.4);background:rgba(255,207,110,.06)}
.card{border:1px solid var(--line);border-radius:16px;padding:1.2rem 1.3rem;margin-bottom:1rem;
background:linear-gradient(180deg,var(--panel),rgba(255,255,255,.02))}
.card h2{font-size:1.1rem;margin:0 0 .3rem}
.banner{border:1px solid rgba(255,207,110,.35);background:rgba(255,207,110,.07);
border-radius:14px;padding:.8rem 1rem;margin-bottom:1rem;font-size:.9rem;color:#ffe6b0}
.banner a{color:var(--gold)}
.working{font-size:1.05rem;margin:.2rem 0 .8rem}
.working b{color:var(--teal)}
.row{display:flex;gap:.6rem;flex-wrap:wrap}
.row>*{flex:1;min-width:150px}
button{cursor:pointer;border:1px solid var(--line);border-radius:11px;padding:.6rem .9rem;
font-size:.9rem;font-weight:600;color:var(--void);
background:linear-gradient(135deg,var(--teal),var(--gold));transition:transform .1s,filter .2s}
button:hover{filter:brightness(1.08)}button:active{transform:translateY(1px)}
button.ghost{background:transparent;color:var(--ink);font-weight:500}
button:disabled{opacity:.5;cursor:wait}
.mega{width:100%;font-size:1.15rem;padding:1rem;margin-top:1rem;border:none;
box-shadow:0 0 0 1px rgba(43,227,194,.4),0 8px 30px rgba(43,227,194,.18)}
.stepper{list-style:none;counter-reset:st;padding:0;margin:1rem 0 0}
.step{position:relative;padding:.7rem .8rem .7rem 3rem;border:1px solid var(--line);
border-radius:12px;margin-bottom:.5rem;background:rgba(255,255,255,.02)}
.step::before{counter-increment:st;content:counter(st);position:absolute;left:.75rem;top:.7rem;
width:1.6rem;height:1.6rem;display:grid;place-items:center;border-radius:50%;
font-family:var(--fm);font-size:.82rem;font-weight:700;color:var(--ink);
background:rgba(255,255,255,.07);border:1px solid var(--line)}
.step.done::before{content:"\\2713";color:var(--void);background:var(--teal);border:none}
.step.current{border-color:rgba(43,227,194,.6);background:rgba(43,227,194,.06)}
.step.current::before{color:var(--void);background:linear-gradient(135deg,var(--teal),var(--gold));border:none}
.step .t{font-weight:600}
.step .h{color:var(--mut);font-size:.84rem;margin-top:.1rem}
.step .n{color:var(--gold);font-size:.8rem;margin-top:.2rem}
.songs{max-height:220px;overflow:auto;border:1px solid var(--line);border-radius:10px;margin-top:.5rem}
.songs table{width:100%;border-collapse:collapse;font-size:.83rem}
.songs td{padding:.32rem .55rem;border-bottom:1px solid rgba(160,150,210,.08)}
.songs tr{cursor:pointer}.songs tr:hover td{background:rgba(43,227,194,.06)}
.songs tr.sel td{background:rgba(124,77,255,.2)}
.pill{font-family:var(--fm);font-size:.64rem;padding:.06rem .4rem;border-radius:999px;background:rgba(255,255,255,.08)}
input{width:100%;padding:.5rem .6rem;border-radius:9px;border:1px solid var(--line);
background:rgba(0,0,0,.25);color:var(--ink);font-size:.9rem;font-family:inherit;margin-top:.5rem}
label{display:block;font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;
color:var(--mut);margin:.6rem 0 .2rem;font-family:var(--fm)}
select{width:100%;padding:.5rem .6rem;border-radius:9px;border:1px solid var(--line);
background:rgba(0,0,0,.25);color:var(--ink);font-size:.9rem;font-family:inherit}
#out{white-space:pre-wrap;font-family:var(--fm);font-size:.8rem;color:#d7e5ff;background:#04060b;
border:1px solid var(--line);border-radius:12px;padding:1rem;margin-top:1rem;min-height:2.5rem;
max-height:300px;overflow:auto}
.spin{color:var(--gold)}
details.expert summary{cursor:pointer;color:var(--mut);font-family:var(--fm);font-size:.85rem;
padding:.5rem 0}
.exgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:.8rem;margin-top:.6rem}
.exgrid .card{margin:0}
.exgrid button{width:100%;margin-top:.6rem}
.done-all{text-align:center;color:var(--teal);font-size:1.05rem;padding:.6rem}
"""

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Infinity Engine control</title><style>__CSS__</style></head><body>
<div class="wrap">
<header><span class="mark"></span>
<h1>Infinity Engine<small>your studio</small></h1>
<span id="reach" class="badge">checking...</span></header>

<div id="banner"></div>

<div class="card">
  <h2>Your next step</h2>
  <div class="working" id="working">Let me find something to work on.</div>
  <div class="row">
    <button id="pick">Pick a song to work on</button>
    <button class="ghost" id="toggleList">Choose from a list</button>
  </div>
  <div id="songwrap" style="display:none">
    <input id="filter" placeholder="type to filter...">
    <div class="songs"><table id="songs"><tbody></tbody></table></div>
  </div>
  <ol class="stepper" id="stepper"></ol>
  <button class="mega" id="mega" style="display:none"></button>
</div>

<pre id="out">Press "Pick a song to work on" and follow the glowing button.</pre>

<details class="expert">
  <summary>Expert mode (all the individual controls)</summary>
  <div class="exgrid">
    <div class="card"><h2>Analyse</h2>
      <button data-cmd="brief" data-need="slug">Analyse selected</button>
      <button class="ghost" data-cmd="site">Rebuild site</button></div>
    <div class="card"><h2>Make a job</h2>
      <label>kind</label><select id="kind">__KINDS__</select>
      <label>tier</label><select id="tier">__TIERS__</select>
      <button data-cmd="make" data-need="slug">Make job</button></div>
    <div class="card"><h2>Render</h2>
      <label>pod ComfyUI URL</label><input id="server" placeholder="http://POD_IP:8188">
      <button data-cmd="work" data-flag="--offline">Render offline</button>
      <button data-cmd="work" data-extra="server">Render on pod</button></div>
    <div class="card"><h2>Advance / info</h2>
      <label>new stage</label><select id="status">__STATUSES__</select>
      <button data-cmd="advance" data-need="slug">Advance selected</button>
      <button class="ghost" data-cmd="doctor">Show wiring</button>
      <button class="ghost" data-cmd="jobs">Show jobs</button></div>
  </div>
</details>
</div>
<script>
let sel=null, songs=[], plan=null, gpu=false;
const out=document.getElementById('out');
const working=document.getElementById('working');

async function boot(){
  const s=await (await fetch('/api/songs')).json(); songs=s;
  const rr=await (await fetch('/api/reach')).json(); gpu=rr.alive;
  const b=document.getElementById('reach');
  b.textContent=gpu?'GPU connected':'no GPU (preview mode)';
  b.className='badge '+(gpu?'on':'off');
  document.getElementById('banner').innerHTML = gpu ? '' :
    '<div class="banner">You have no GPU connected yet, so you can do '
    +'everything except make real pictures. That is fine to start. When you '
    +'want real images, <a href="https://auraofintelligence.github.io/'
    +'infinity-engine/gpu-setup.html" target="_blank">connect a GPU (2 min) &rarr;</a></div>';
  renderList(songs);
}
function renderList(list){
  const tb=document.querySelector('#songs tbody'); tb.innerHTML='';
  list.forEach(s=>{const tr=document.createElement('tr');
    const t=document.createElement('td'); t.textContent=s.title;
    const p=document.createElement('td'); p.innerHTML='<span class="pill"></span>';
    p.firstChild.textContent=s.status;
    tr.append(t,p);
    tr.onclick=()=>select(s.slug);
    if(s.slug===sel) tr.classList.add('sel');
    tb.appendChild(tr);});
}
async function select(slug){
  sel=slug;
  plan=await (await fetch('/api/plan?slug='+encodeURIComponent(slug)+'&gpu='+gpu)).json();
  working.innerHTML='Working on: <b>'+plan.title+'</b>';
  renderStepper();
  renderList(songs);
}
function renderStepper(){
  const ol=document.getElementById('stepper'); ol.innerHTML='';
  plan.steps.forEach(st=>{
    const li=document.createElement('li');
    li.className='step'+(st.done?' done':'')+(st.current?' current':'');
    li.innerHTML='<div class="t"></div><div class="h"></div>'+(st.note?'<div class="n"></div>':'');
    li.querySelector('.t').textContent=st.title;
    li.querySelector('.h').textContent=st.help;
    if(st.note) li.querySelector('.n').textContent='('+st.note+')';
    ol.appendChild(li);
  });
  const cur=plan.steps[plan.current];
  const mega=document.getElementById('mega');
  mega.style.display='block';
  mega.textContent=cur.button;
  mega.onclick=()=>runStep(cur);
}
async function runStep(step){
  const btns=document.querySelectorAll('button'); btns.forEach(b=>b.disabled=true);
  out.innerHTML='<span class="spin">working on: '+step.title+' ...</span>';
  try{const j=await (await fetch('/api/run',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(step.action)})).json();
    out.textContent=j.output||'(done)';}
  catch(e){out.textContent='error: '+e;}
  btns.forEach(b=>b.disabled=false);
  const s=await (await fetch('/api/songs')).json(); songs=s;
  await select(sel);
}
document.getElementById('pick').onclick=async()=>{
  const j=await (await fetch('/api/next?gpu='+gpu)).json();
  if(j.slug){await select(j.slug);
    out.textContent='Picked "'+plan.title+'". Press the glowing button below.';}
};
document.getElementById('toggleList').onclick=()=>{
  const w=document.getElementById('songwrap');
  w.style.display=w.style.display==='none'?'block':'none';
};
document.getElementById('filter').oninput=e=>{
  const q=e.target.value.toLowerCase();
  renderList(songs.filter(s=>s.title.toLowerCase().includes(q)));
};
document.querySelectorAll('button[data-cmd]').forEach(btn=>{
  btn.onclick=async()=>{
    if(btn.dataset.need==='slug' && !sel){out.textContent='Pick a song first.';return;}
    const body={cmd:btn.dataset.cmd,slug:sel,flag:btn.dataset.flag||'',
      extra:btn.dataset.extra||'',
      kind:(document.getElementById('kind')||{}).value,
      tier:(document.getElementById('tier')||{}).value,
      status:(document.getElementById('status')||{}).value,
      server:(document.getElementById('server')||{}).value};
    const btns=document.querySelectorAll('button'); btns.forEach(b=>b.disabled=true);
    out.innerHTML='<span class="spin">running '+btn.dataset.cmd+' ...</span>';
    try{const j=await (await fetch('/api/run',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
      out.textContent=j.output||'(done)';}catch(e){out.textContent='error: '+e;}
    btns.forEach(b=>b.disabled=false);
    if(sel) select(sel);
  };
});
boot();
</script></body></html>"""


def _options(values, sel=None):
    return "".join(f'<option{" selected" if v == sel else ""}>{v}</option>'
                   for v in values)


class Handler(BaseHTTPRequestHandler):
    cfg = None

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _notes(self):
        notes = vault.all_notes(resolve(self.cfg, "vault_dir"))
        notes.sort(key=lambda n: (n.meta.get("album", ""),
                                  n.meta.get("track") or 0))
        return notes

    def do_GET(self):
        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)
        if path == "/":
            page = (PAGE.replace("__CSS__", CSS)
                    .replace("__KINDS__", _options(KINDS))
                    .replace("__TIERS__", _options(TIERS, "standard"))
                    .replace("__STATUSES__", _options(STATUS_ORDER)))
            return self._send(200, page, "text/html; charset=utf-8")
        if path == "/api/songs":
            data = [{"slug": n.slug, "title": n.meta.get("title", n.slug),
                     "status": n.status} for n in self._notes()]
            return self._send(200, json.dumps(data))
        if path == "/api/reach":
            from . import comfy, worker
            ccfg = worker.load_comfy_config(self.cfg["_root"])
            alive = comfy.ComfyClient(ccfg.get("server", "")).alive()
            return self._send(200, json.dumps({"alive": alive}))
        if path == "/api/plan":
            slug = (qs.get("slug") or [""])[0]
            gpu = (qs.get("gpu") or ["false"])[0] == "true"
            note = next((n for n in self._notes() if n.slug == slug), None)
            if not note:
                return self._send(404, json.dumps({"error": "no such song"}))
            return self._send(200, json.dumps(
                flow.song_steps(self.cfg, note, gpu)))
        if path == "/api/next":
            gpu = (qs.get("gpu") or ["false"])[0] == "true"
            slug = flow.next_song(self.cfg, self._notes(), gpu)
            return self._send(200, json.dumps({"slug": slug}))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if urlparse(self.path).path != "/api/run":
            return self._send(404, json.dumps({"error": "not found"}))
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length) or "{}")
        try:
            args = self._build_args(req)
        except ValueError as exc:
            return self._send(200, json.dumps({"output": f"cannot run: {exc}"}))
        proc = subprocess.run([sys.executable, "-m", "engine", *args],
                              cwd=self.cfg["_root"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        output = (proc.stdout or "") + (proc.stderr or "")
        self._send(200, json.dumps({"output": output.strip() or "(done)"}))

    def _build_args(self, req: dict) -> list:
        cmd, slug = req.get("cmd"), req.get("slug")
        if cmd == "doctor":
            return ["doctor"]
        if cmd == "jobs":
            return ["jobs"]
        if cmd == "site":
            return ["site"]
        if cmd == "brief":
            if not slug:
                raise ValueError("no song selected")
            return ["brief", slug, "--run-claude"]
        if cmd == "make":
            if not slug:
                raise ValueError("no song selected")
            kind, tier = req.get("kind"), req.get("tier")
            if kind not in KINDS or tier not in TIERS:
                raise ValueError("bad kind/tier")
            return ["make", slug, kind, "--tier", tier]
        if cmd == "advance":
            if not slug:
                raise ValueError("no song selected")
            if req.get("status") not in STATUS_ORDER:
                raise ValueError("bad status")
            return ["advance", slug, req["status"]]
        if cmd == "work":
            args = ["work"]
            if req.get("flag") == "--offline":
                args.append("--offline")
            elif req.get("extra") == "server":
                server = (req.get("server") or "").strip()
                if server:
                    if not server.startswith("http"):
                        raise ValueError("server must be an http URL")
                    args += ["--server", server]
            return args
        raise ValueError(f"unknown action '{cmd}'")


def serve(host="127.0.0.1", port=8765, open_browser=True):
    Handler.cfg = load_config()
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"Infinity Engine studio: {url}")
    print("Leave this window open. Close it to stop.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
