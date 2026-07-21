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
import secrets
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import assistant, fleet, flow, studio_state, vault, voice
from .config import load_config, resolve
from .site import STATUS_ORDER

# Friendly breadcrumb label per action, for the "Recently" trail.
TRAIL_LABEL = {"brief": "Read the song", "make": "Planned the panels",
               "advance": "Advanced a stage", "site": "Updated the site"}

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
background:#0a1420;color:var(--ink);font-size:.9rem;font-family:inherit;color-scheme:dark}
option{background:#0a1420;color:#eae6ff}
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
.hint{color:var(--mut);font-size:.85rem;margin:.1rem 0 .7rem}
.muted{color:var(--mut)}
#cstatus{font-family:var(--fm);font-size:.66rem;vertical-align:middle}
details#connect summary{cursor:pointer;color:var(--teal);font-size:.9rem;padding:.3rem 0}
.steps-sm{margin:.5rem 0;padding-left:1.2rem;font-size:.86rem;color:var(--mut)}
.steps-sm li{margin:.3rem 0}.steps-sm a{color:var(--teal)}
.steps-sm code{font-family:var(--fm);font-size:.85em;background:rgba(255,255,255,.06);
padding:.05rem .3rem;border-radius:5px}
.trail{list-style:none;padding:0;margin:.3rem 0 0}
.trail li{display:flex;gap:.5rem;align-items:baseline;padding:.3rem 0;
border-bottom:1px solid rgba(160,150,210,.08);font-size:.86rem}
.trail .tw{color:var(--ink);font-weight:600}
.trail .ts{color:var(--teal);flex:1}
.trail .tt{color:var(--mut);font-family:var(--fm);font-size:.72rem;white-space:nowrap}
.phone{font-size:.88rem;padding:.5rem .7rem;border-radius:10px;margin-bottom:.6rem;
background:rgba(124,77,255,.1);border:1px solid var(--line)}
.phone b{color:var(--teal)}
.fhead{font-family:var(--fm);font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;
color:var(--mut);margin:.7rem 0 .3rem}
.fitem{display:flex;align-items:center;gap:.5rem;padding:.4rem 0;
border-bottom:1px solid rgba(160,150,210,.08);flex-wrap:wrap}
.fdot{width:.6rem;height:.6rem;border-radius:50%;flex:none;box-shadow:0 0 6px currentColor}
.fname{font-weight:600}
.fkind{font-family:var(--fm);font-size:.64rem;color:var(--mut);
border:1px solid var(--line);border-radius:999px;padding:0 .4rem}
.froles{display:flex;gap:.25rem;flex-wrap:wrap;flex:1}
.frole{font-family:var(--fm);font-size:.62rem;color:#cfc9e6;background:rgba(255,255,255,.05);
border-radius:999px;padding:.05rem .4rem}
.fact{margin-left:auto}
.fbtn{padding:.3rem .6rem;font-size:.78rem;border-radius:8px}
.flink{color:var(--teal);font-size:.82rem}
.fin{color:var(--teal);font-size:.8rem;font-family:var(--fm)}
.answer{margin-top:.8rem;padding:.8rem .9rem;border-radius:11px;font-size:.95rem;
line-height:1.5;background:rgba(43,227,194,.06);border:1px solid rgba(43,227,194,.25)}
.answer.muted{background:rgba(255,255,255,.02);border-color:var(--line)}
.vline{display:flex;align-items:center;gap:.5rem;margin-top:.7rem;font-size:.85rem;color:var(--mut)}
.vline input{width:auto}
"""

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Infinity Engine control</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>__CSS__</style></head><body>
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

<div class="card">
  <h2>Assistant</h2>
  <p class="hint">Ask where you're up to, what's next, or what's due. Tick
  the box to have answers read aloud.</p>
  <div class="row">
    <button data-ask="where">Where are we up to?</button>
    <button data-ask="next">What's next?</button>
    <button data-ask="due">What's due?</button>
    <button class="ghost" data-ask="explain">Explain this step</button>
  </div>
  <div id="answer" class="answer muted">Ask me anything above.</div>
  <label class="vline"><input type="checkbox" id="speak"> <span></span></label>
</div>

<div class="card">
  <h2>Rendering box <span id="cstatus" class="pill">checking...</span></h2>
  <p class="hint">This is where real pictures get made. With no box, every
  step still works in preview. Hire one only when you want images.</p>
  <details id="connect"><summary>Connect a rendering box</summary>
    <ol class="steps-sm">
      <li>Rent an hourly GPU box (Vast.ai or RunPod) and start ComfyUI on it,
      or run <code>pod_bootstrap.sh</code>. Full walkthrough:
      <a href="https://auraofintelligence.github.io/infinity-engine/gpu-setup.html"
      target="_blank">Set up a GPU &rarr;</a></li>
      <li>Open the tunnel from your machine, then paste the address below and
      press Test &amp; connect. It is remembered until you disconnect.</li>
    </ol>
    <label>box address</label>
    <input id="cserver" placeholder="http://127.0.0.1:8188 (via tunnel) or http://POD_IP:8188">
    <div class="row">
      <button id="ctest">Test &amp; connect</button>
      <button class="ghost" id="cdrop">Disconnect</button>
    </div>
  </details>
</div>

<div class="card">
  <h2>Your devices &amp; accounts</h2>
  <p class="hint">Everything you own or can hire. A green dot means it is
  live right now. Edit the list in <code>catalog/fleet.yaml</code>.</p>
  <div id="phoneline"></div>
  <div id="fleet"></div>
</div>

<div class="card">
  <h2>Recently</h2>
  <p class="hint">Your last few moves, so you always know where you were.</p>
  <ul class="trail" id="trail"><li class="muted">nothing yet</li></ul>
</div>

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
  songs=await (await fetch('/api/songs')).json();
  const home=await (await fetch('/api/home')).json();
  gpu=home.gpu;
  paintGpu(home.server);
  renderTrail(home.trail);
  renderFleet();
  const vspan=document.querySelector('.vline span');
  if(home.voice&&home.voice.tts){vspan.textContent='read answers aloud (offline voice)';}
  else{vspan.textContent='read aloud (not available on this machine)';
    document.getElementById('speak').disabled=true;}
  renderList(songs);
  if(home.continue){
    await select(home.continue.slug);
    working.innerHTML='Welcome back. You were on <b>'+home.continue.title
      +'</b>. Press the glowing button to keep going, or pick another song.';
  }
}
function paintGpu(server){
  const b=document.getElementById('reach');
  b.textContent=gpu?'GPU connected':'no GPU (preview mode)';
  b.className='badge '+(gpu?'on':'off');
  const cs=document.getElementById('cstatus');
  cs.textContent = gpu ? ('connected'+(server?' · '+server:'')) : 'not connected';
  document.getElementById('banner').innerHTML = gpu ? '' :
    '<div class="banner">No rendering box connected, so you can do everything '
    +'except make real pictures. That is fine to start. When you want real '
    +'images, open <b>Rendering box</b> below and connect one.</div>';
}
function renderTrail(trail){
  const ul=document.getElementById('trail'); ul.innerHTML='';
  if(!trail||!trail.length){ul.innerHTML='<li class="muted">nothing yet</li>';return;}
  trail.forEach(e=>{const li=document.createElement('li');
    const when=(e.t||'').replace('T',' ');
    li.innerHTML='<span class="tw"></span><span class="ts"></span><span class="tt"></span>';
    li.querySelector('.tw').textContent=e.what;
    li.querySelector('.ts').textContent=e.song?(' - '+e.song):'';
    li.querySelector('.tt').textContent=when;
    ul.appendChild(li);});
}
const DOT={online:'#2be3c2',connected:'#2be3c2',ready:'#7c4dff',
  offline:'#ff5fd1',declared:'#a89fce'};
function fleetRow(e){
  const div=document.createElement('div'); div.className='fitem';
  const dot='<span class="fdot" style="background:'+(DOT[e.status]||'#888')+'"></span>';
  const roles=(e.roles||[]).map(r=>'<span class="frole">'+r+'</span>').join('');
  let act='';
  if(e.reach==='comfy'){
    if(e.status==='connected') act='<span class="fin">in use</span>';
    else if(e.address) act='<button class="fbtn" data-addr="'+e.address+'">Connect</button>';
    else act='<span class="muted" style="font-size:.78rem">add its address in fleet.yaml</span>';
  } else if(e.reach==='browser'){
    act=phoneUrl?'<span class="fin">open '+phoneUrl+'</span>'
      :'<span class="muted" style="font-size:.78rem">start with --lan to use</span>';
  } else if(e.signin){
    act='<a class="flink" href="'+e.signin+'" target="_blank">sign in &rarr;</a>';
  }
  div.innerHTML=dot+'<span class="fname"></span><span class="fkind"></span>'
    +'<span class="froles">'+roles+'</span><span class="fact">'+act+'</span>';
  div.querySelector('.fname').textContent=e.name;
  div.querySelector('.fkind').textContent=e.owned==='hired'?'hired':'yours';
  return div;
}
let phoneUrl=null;
async function renderFleet(){
  const f=await (await fetch('/api/fleet')).json();
  phoneUrl=f.phone_url;
  const pl=document.getElementById('phoneline');
  pl.innerHTML=phoneUrl
    ?'<div class="phone">On your phone (same wifi), open <b>'+phoneUrl+'</b></div>'
    :'<div class="phone muted">To use your phone as a screen, start with '
     +'"Infinity Engine (phone).cmd" or <code>engine gui --lan</code>.</div>';
  const box=document.getElementById('fleet'); box.innerHTML='';
  [['Your devices',f.devices],['Hired accounts',f.accounts]].forEach(([label,items])=>{
    if(!items||!items.length) return;
    const h=document.createElement('div'); h.className='fhead'; h.textContent=label;
    box.appendChild(h);
    items.forEach(e=>box.appendChild(fleetRow(e)));
  });
  box.querySelectorAll('.fbtn').forEach(b=>b.onclick=()=>connect(b.dataset.addr));
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
  songs=await (await fetch('/api/songs')).json();
  const home=await (await fetch('/api/home')).json();
  renderTrail(home.trail);
  await select(sel);
}
async function connect(server){
  const out2=document.getElementById('out');
  out2.innerHTML='<span class="spin">testing the box...</span>';
  const j=await (await fetch('/api/connect',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({server})})).json();
  out2.textContent=j.message||'';
  gpu=j.alive; paintGpu(j.server);
  renderFleet();                       // dots + "in use" refresh
  if(sel) await select(sel);           // re-plan: preview vs real render
}
document.getElementById('ctest').onclick=()=>connect(document.getElementById('cserver').value);
document.getElementById('cdrop').onclick=()=>connect('');
async function ask(q){
  const a=document.getElementById('answer');
  a.className='answer'; a.textContent='...';
  let step=''; if(plan) step=plan.steps[plan.current].key;
  const u='/api/ask?q='+q+'&slug='+encodeURIComponent(sel||'')+'&step='+step;
  const j=await (await fetch(u)).json();
  a.textContent=j.answer;
  if(document.getElementById('speak').checked)
    fetch('/api/speak',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:j.answer})});
}
document.querySelectorAll('button[data-ask]').forEach(b=>b.onclick=()=>ask(b.dataset.ask));
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


LOGIN_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Infinity Engine</title><meta name="viewport"
content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="/favicon.svg"><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;
font-family:system-ui,Segoe UI,sans-serif;color:#eae6ff;
background:radial-gradient(1000px 700px at 60% -10%,rgba(124,77,255,.18),transparent),#05070c}
.box{border:1px solid rgba(160,150,210,.2);border-radius:16px;padding:1.6rem 1.8rem;
background:rgba(124,77,255,.08);max-width:340px;text-align:center}
.mk{width:44px;height:44px;border-radius:50%;margin:0 auto .7rem;
background:radial-gradient(circle at 35% 30%,#b79bff,#7c4dff 55%,#2a1a5e)}
h1{font-size:1.2rem;margin:.2rem 0}p{color:#a89fce;font-size:.86rem}
input{width:100%;padding:.6rem;margin:.6rem 0;border-radius:10px;font-size:1.1rem;
text-align:center;letter-spacing:.2em;border:1px solid rgba(160,150,210,.3);
background:rgba(0,0,0,.3);color:#eae6ff}
button{width:100%;padding:.7rem;border:none;border-radius:10px;font-weight:700;
font-size:1rem;color:#05070c;background:linear-gradient(135deg,#2be3c2,#ffcf6e)}
.err{color:#ffcf6e;font-size:.85rem;min-height:1rem}
</style></head><body><form class="box" action="/login" method="get">
<div class="mk"></div><h1>Infinity Engine</h1>
<p>Enter the access code shown on your studio machine.</p>
<div class="err">__ERR__</div>
<input name="key" placeholder="code" autofocus autocomplete="off">
<button type="submit">Open the studio</button></form></body></html>"""


class Handler(BaseHTTPRequestHandler):
    cfg = None
    phone_url = None    # set when serving on the LAN (--lan)
    access_code = None  # required for non-localhost devices in --lan mode

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

    def _server(self, override: str | None = None) -> str:
        """The ComfyUI URL in effect: an explicit override, else the box you
        connected (saved), else the recipe default."""
        if override:
            return override
        saved = studio_state.load(self.cfg).get("comfy_server")
        if saved:
            return saved
        from . import worker
        return worker.load_comfy_config(self.cfg["_root"]).get(
            "server", "http://127.0.0.1:8188")

    def _alive(self, server: str) -> bool:
        from . import comfy
        return comfy.ComfyClient(server).alive()

    # --- access control: localhost is always open (airgap); other devices
    #     need the code, so the panel is safe to reach over a tunnel/5G. ---
    def _is_local(self) -> bool:
        return self.client_address[0] in ("127.0.0.1", "::1")

    def _cookie_key(self):
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            if part.strip().startswith("iek="):
                return part.strip()[4:]
        return None

    def _authed(self, qs: dict) -> bool:
        if self._is_local() or not Handler.access_code:
            return True
        key = self._cookie_key() or (qs.get("key") or [None])[0]
        return key == Handler.access_code

    def _login(self, qs: dict):
        key = (qs.get("key") or [None])[0]
        if key and key == Handler.access_code:
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", f"iek={key}; Path=/; SameSite=Lax")
            self.end_headers()
            return
        body = LOGIN_PAGE.replace("__ERR__",
                                  "wrong code, try again" if key else "")
        self._send(200 if not key else 401, body, "text/html; charset=utf-8")

    def _challenge(self, path: str):
        if path.startswith("/api/"):
            return self._send(401, json.dumps({"error": "locked"}))
        self._send(200, LOGIN_PAGE.replace("__ERR__", ""),
                   "text/html; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)
        if path == "/favicon.svg":
            # The studio uses its own sibling icon (with the live pip) so its
            # tab is distinct from the public site's.
            p = self.cfg["_root"] / "docs" / "assets" / "favicon-studio.svg"
            data = p.read_bytes() if p.exists() else b""
            return self._send(200 if data else 404, data, "image/svg+xml")
        if path == "/login":
            return self._login(qs)
        if not self._authed(qs):
            return self._challenge(path)
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
            server = self._server((qs.get("server") or [""])[0] or None)
            return self._send(200, json.dumps(
                {"alive": self._alive(server), "server": server}))
        if path == "/api/fleet":
            saved = studio_state.load(self.cfg).get("comfy_server")
            view = fleet.fleet_view(self.cfg["_root"], saved)
            view["phone_url"] = self.phone_url
            return self._send(200, json.dumps(view))
        if path == "/api/ask":
            q = (qs.get("q") or ["where"])[0]
            slug = (qs.get("slug") or [""])[0]
            step = (qs.get("step") or [""])[0] or None
            note = next((n for n in self._notes() if n.slug == slug), None)
            ans = assistant.answer(self.cfg, q, note=note, step_key=step)
            return self._send(200, json.dumps({"answer": ans}))
        if path == "/api/home":
            state = studio_state.load(self.cfg)
            server = self._server()
            alive = self._alive(server)
            cont = None
            last = state.get("last_song")
            if last and any(n.slug == last for n in self._notes()):
                note = next(n for n in self._notes() if n.slug == last)
                cont = {"slug": last, "title": note.meta.get("title", last)}
            return self._send(200, json.dumps(
                {"continue": cont, "trail": state.get("trail", [])[:8],
                 "server": state.get("comfy_server"), "gpu": alive,
                 "voice": {"tts": voice.tts_available(),
                           "stt": voice.stt_available()}}))
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
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length) or "{}")
        if not self._authed({}):
            return self._send(401, json.dumps({"error": "locked"}))
        if path == "/api/connect":
            return self._connect(req)
        if path == "/api/speak":
            spoke = voice.say(req.get("text", ""))
            return self._send(200, json.dumps({"spoke": spoke}))
        if path != "/api/run":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            args = self._build_args(req)
        except ValueError as exc:
            return self._send(200, json.dumps({"output": f"cannot run: {exc}"}))
        proc = subprocess.run([sys.executable, "-m", "engine", *args],
                              cwd=self.cfg["_root"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        output = (proc.stdout or "") + (proc.stderr or "")
        self._record(req)
        self._send(200, json.dumps({"output": output.strip() or "(done)"}))

    def _connect(self, req: dict):
        """Test a GPU box and, if it answers, remember it so every render
        uses it until you disconnect."""
        server = (req.get("server") or "").strip()
        if not server:  # disconnect
            studio_state.set_server(self.cfg, None)
            studio_state.record(self.cfg, what="Disconnected compute")
            return self._send(200, json.dumps({"alive": False, "server": None,
                              "message": "Disconnected. Renders will preview only."}))
        if not server.startswith("http"):
            return self._send(200, json.dumps(
                {"alive": False, "message": "Address must start with http."}))
        alive = self._alive(server)
        if alive:
            studio_state.set_server(self.cfg, server)
            studio_state.record(self.cfg, what="Connected compute")
            msg = "Connected. The engine will render on this box."
        else:
            msg = ("No answer from that address. Is ComfyUI running on the "
                   "box, and the tunnel open?")
        self._send(200, json.dumps({"alive": alive, "server": server,
                                    "message": msg}))

    def _record(self, req: dict):
        """Drop a breadcrumb for the action just run."""
        cmd = req.get("cmd")
        if cmd == "work":
            what = ("Previewed the plan" if req.get("flag") == "--offline"
                    else "Made the pictures")
        else:
            what = TRAIL_LABEL.get(cmd)
        if not what:
            return  # read-only (doctor/jobs), no breadcrumb
        slug = req.get("slug")
        title = ""
        if slug:
            note = next((n for n in self._notes() if n.slug == slug), None)
            title = note.meta.get("title", slug) if note else slug
        studio_state.record(self.cfg, song=slug, song_title=title, what=what)

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
                return args
            # An explicit URL wins; otherwise use the box you connected.
            server = (req.get("server") or "").strip()
            if not server and req.get("extra") != "server":
                server = studio_state.load(self.cfg).get("comfy_server") or ""
            if server:
                if not server.startswith("http"):
                    raise ValueError("server must be an http URL")
                args += ["--server", server]
            return args
        raise ValueError(f"unknown action '{cmd}'")


def serve(host="127.0.0.1", port=8765, open_browser=True, lan=False):
    Handler.cfg = load_config()
    bind = "0.0.0.0" if lan else host
    open_url = f"http://127.0.0.1:{port}/"
    if lan:
        state = studio_state.load(Handler.cfg)
        code = state.get("access_code") or secrets.token_hex(3)
        if state.get("access_code") != code:
            state["access_code"] = code
            studio_state.save(Handler.cfg, state)
        Handler.access_code = code
        ip = fleet.lan_ip()
        Handler.phone_url = f"http://{ip}:{port}/" if ip else None
    httpd = ThreadingHTTPServer((bind, port), Handler)
    print(f"Infinity Engine studio: {open_url}")
    if lan and Handler.phone_url:
        print(f"\nOn another device (phone/tablet/laptop):")
        print(f"  1. open   {Handler.phone_url}")
        print(f"  2. code   {Handler.access_code}")
        print(f"  one-tap link: {Handler.phone_url}login?key={Handler.access_code}")
        print("(Other devices need the code; this machine never does.)")
    print("Leave this window open. Close it to stop.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(open_url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
