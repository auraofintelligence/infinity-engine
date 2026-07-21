"""A local control panel, so the engine is buttons not a terminal.

`python -m engine gui` (or double-click "Infinity Engine.cmd") starts a
tiny web server on 127.0.0.1 and opens a browser. Every button runs a real
engine command and shows its output. Nothing here is deployed: this panel
touches the vault and starts renders, so it is LOCAL ONLY, never the public
site.

Stdlib only (http.server + subprocess), so it runs on a fresh Python with
no extra installs, matching the rest of the engine.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import webbrowser
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import vault
from .config import load_config, resolve
from .site import STATUS_ORDER

# What the panel is allowed to run. The GUI can NEVER run anything not
# listed here, so a stray localhost request can't do arbitrary things.
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
.wrap{max-width:1000px;margin:0 auto;padding:1.5rem clamp(1rem,4vw,2rem) 4rem}
header{display:flex;align-items:center;gap:.8rem;margin:.4rem 0 1.4rem}
.mark{width:38px;height:38px;border-radius:50%;
background:radial-gradient(circle at 35% 30%,#b79bff,var(--violet) 55%,#2a1a5e)}
h1{font-size:1.5rem;margin:0}
h1 small{display:block;font-family:var(--fm);font-size:.7rem;letter-spacing:.15em;
text-transform:uppercase;color:var(--mut)}
.badge{margin-left:auto;font-family:var(--fm);font-size:.8rem;padding:.3rem .7rem;
border-radius:999px;border:1px solid var(--line)}
.badge.on{color:var(--teal);border-color:rgba(43,227,194,.5);background:rgba(43,227,194,.08)}
.badge.off{color:var(--gold);border-color:rgba(255,207,110,.4);background:rgba(255,207,110,.06)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}
.card{border:1px solid var(--line);border-radius:16px;padding:1.1rem 1.2rem;
background:linear-gradient(180deg,var(--panel),rgba(255,255,255,.02))}
.card h2{font-size:1.05rem;margin:0 0 .2rem}
.card p{color:var(--mut);font-size:.85rem;margin:.1rem 0 .8rem}
label{display:block;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;
color:var(--mut);margin:.6rem 0 .2rem;font-family:var(--fm)}
select,input{width:100%;padding:.5rem .6rem;border-radius:9px;border:1px solid var(--line);
background:rgba(0,0,0,.25);color:var(--ink);font-size:.9rem;font-family:inherit}
.row{display:flex;gap:.5rem}.row>*{flex:1}
button{cursor:pointer;border:1px solid var(--line);border-radius:10px;padding:.55rem .8rem;
font-size:.88rem;font-weight:600;color:var(--void);margin-top:.7rem;width:100%;
background:linear-gradient(135deg,var(--teal),var(--gold));transition:transform .1s,filter .2s}
button:hover{filter:brightness(1.08)}button:active{transform:translateY(1px)}
button.ghost{background:transparent;color:var(--ink);font-weight:500}
button:disabled{opacity:.5;cursor:wait}
.songs{max-height:230px;overflow:auto;border:1px solid var(--line);border-radius:10px}
.songs table{width:100%;border-collapse:collapse;font-size:.82rem}
.songs td{padding:.3rem .5rem;border-bottom:1px solid rgba(160,150,210,.08)}
.songs tr{cursor:pointer}.songs tr:hover td{background:rgba(43,227,194,.06)}
.songs tr.sel td{background:rgba(124,77,255,.18)}
.pill{font-family:var(--fm);font-size:.66rem;padding:.06rem .4rem;border-radius:999px;
background:rgba(255,255,255,.08)}
.sel-note{font-size:.82rem;color:var(--teal);min-height:1.1rem;margin:.3rem 0}
#out{white-space:pre-wrap;font-family:var(--fm);font-size:.8rem;color:#d7e5ff;
background:#04060b;border:1px solid var(--line);border-radius:12px;padding:1rem;
margin-top:1.2rem;min-height:3rem;max-height:340px;overflow:auto}
.spin{color:var(--gold)}
.full{grid-column:1/-1}
"""

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Infinity Engine control</title><style>__CSS__</style></head><body>
<div class="wrap">
<header><span class="mark"></span>
<h1>Infinity Engine<small>local control panel</small></h1>
<span id="reach" class="badge">checking ComfyUI...</span></header>

<div class="grid">
  <div class="card">
    <h2>1. Pick a song</h2>
    <p>Click one, then use the actions below.</p>
    <input id="filter" placeholder="filter by title...">
    <div class="songs"><table id="songs"><tbody></tbody></table></div>
    <div class="sel-note" id="sel">nothing selected</div>
  </div>

  <div class="card">
    <h2>2. Analyse</h2>
    <p>Reads the whole lyric for a director's line-by-line read (about a
    minute per song).</p>
    <button data-cmd="brief" data-need="slug" data-flag="--run-claude">Analyse selected song</button>
    <button class="ghost" data-cmd="site">Rebuild the site</button>
  </div>

  <div class="card">
    <h2>3. Make a job</h2>
    <p>Assembles a render job (data, model, compute, direction) for the
    selected song.</p>
    <div class="row">
      <div><label>kind</label><select id="kind">__KINDS__</select></div>
      <div><label>tier</label><select id="tier">__TIERS__</select></div>
    </div>
    <button data-cmd="make" data-need="slug" data-extra="kindtier">Make job</button>
  </div>

  <div class="card">
    <h2>4. Render queued jobs</h2>
    <p>Offline writes the ComfyUI graphs with no GPU. Pod renders for real
    on a box you have running (see Set up a GPU).</p>
    <label>pod ComfyUI URL (optional)</label>
    <input id="server" placeholder="http://POD_IP:8188">
    <div class="row">
      <button data-cmd="work" data-flag="--offline">Render offline</button>
      <button data-cmd="work" data-extra="server">Render on pod</button>
    </div>
  </div>

  <div class="card">
    <h2>5. Advance a stage</h2>
    <p>Move the selected song forward once a piece lands.</p>
    <label>new stage</label><select id="status">__STATUSES__</select>
    <button data-cmd="advance" data-need="slug" data-extra="status">Advance selected song</button>
  </div>

  <div class="card">
    <h2>Wiring</h2>
    <p>Paths, ComfyUI reachability, recipes, runners, jobs.</p>
    <button class="ghost" data-cmd="doctor">Show wiring</button>
    <button class="ghost" data-cmd="jobs">Show jobs</button>
  </div>
</div>

<pre id="out" class="full">Ready. Pick a song, or click "Show wiring".</pre>
</div>
<script>
let sel=null, songs=[];
const out=document.getElementById('out');
function render(list){
  const tb=document.querySelector('#songs tbody'); tb.innerHTML='';
  list.forEach(s=>{const tr=document.createElement('tr');
    const t=document.createElement('td');t.textContent=s.title;
    const p=document.createElement('td');
    p.innerHTML='<span class="pill"></span>';p.firstChild.textContent=s.status;
    tr.appendChild(t);tr.appendChild(p);
    tr.onclick=()=>{sel=s.slug;
      document.querySelectorAll('#songs tr').forEach(r=>r.classList.remove('sel'));
      tr.classList.add('sel');
      document.getElementById('sel').textContent='selected: '+s.title;};
    tb.appendChild(tr);});
}
async function load(){
  const r=await fetch('/api/songs');songs=await r.json();render(songs);
  reach();
}
async function reach(){
  const b=document.getElementById('reach');
  const r=await fetch('/api/reach');const j=await r.json();
  b.textContent=j.alive?'ComfyUI reachable':'ComfyUI not running';
  b.className='badge '+(j.alive?'on':'off');
}
document.getElementById('filter').oninput=e=>{
  const q=e.target.value.toLowerCase();
  render(songs.filter(s=>s.title.toLowerCase().includes(q)));
};
document.querySelectorAll('button[data-cmd]').forEach(btn=>{
  btn.onclick=async()=>{
    const need=btn.dataset.need;
    if(need==='slug' && !sel){out.textContent='Pick a song first.';return;}
    const body={cmd:btn.dataset.cmd,slug:sel,
      flag:btn.dataset.flag||'', extra:btn.dataset.extra||'',
      kind:document.getElementById('kind').value,
      tier:document.getElementById('tier').value,
      status:document.getElementById('status').value,
      server:document.getElementById('server').value};
    const all=document.querySelectorAll('button');all.forEach(b=>b.disabled=true);
    out.innerHTML='<span class="spin">running '+btn.dataset.cmd+' ...</span>';
    try{const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)});const j=await r.json();
      out.textContent=j.output||'(no output)';}
    catch(e){out.textContent='error: '+e;}
    all.forEach(b=>b.disabled=false);
    load();
  };
});
load();
</script></body></html>"""


def _options(values, sel=None):
    return "".join(f'<option{" selected" if v == sel else ""}>{v}</option>'
                   for v in values)


class Handler(BaseHTTPRequestHandler):
    cfg = None  # set in serve()

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            page = (PAGE.replace("__CSS__", CSS)
                    .replace("__KINDS__", _options(KINDS))
                    .replace("__TIERS__", _options(TIERS, "standard"))
                    .replace("__STATUSES__", _options(STATUS_ORDER)))
            return self._send(200, page, "text/html; charset=utf-8")
        if path == "/api/songs":
            notes = vault.all_notes(resolve(self.cfg, "vault_dir"))
            notes.sort(key=lambda n: (n.meta.get("album", ""),
                                      n.meta.get("track") or 0))
            data = [{"slug": n.slug,
                     "title": n.meta.get("title", n.slug),
                     "status": n.status} for n in notes]
            return self._send(200, json.dumps(data))
        if path == "/api/reach":
            from . import comfy, worker
            ccfg = worker.load_comfy_config(self.cfg["_root"])
            alive = comfy.ComfyClient(ccfg.get("server", "")).alive()
            return self._send(200, json.dumps({"alive": alive}))
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
        """Translate a button press into an allow-listed engine command."""
        cmd = req.get("cmd")
        slug = req.get("slug")
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
            kind = req.get("kind")
            tier = req.get("tier")
            if kind not in KINDS or tier not in TIERS:
                raise ValueError("bad kind/tier")
            return ["make", slug, kind, "--tier", tier]
        if cmd == "advance":
            if not slug:
                raise ValueError("no song selected")
            status = req.get("status")
            if status not in STATUS_ORDER:
                raise ValueError("bad status")
            return ["advance", slug, status]
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
    print(f"Infinity Engine control panel: {url}")
    print("Leave this window open. Close it to stop the panel.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
