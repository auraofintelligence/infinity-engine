"""Current portrait media and performed lyrics for existing song pages."""
from pathlib import Path
from functools import lru_cache
import json,re,html

@lru_cache(maxsize=1)
def registry():
    root=Path(__file__).resolve().parents[1]
    return json.loads((root/'data/portrait-media-2026-10-30.json').read_text(encoding='utf-8'))['songs']

def norm(s):
    return re.sub(r'[^a-z0-9]+',' ',s.lower().replace('’','').replace("'",'')).strip()

def lookup(title='',slug='',album='',track=None):
    n=norm(title);s=slug.lower()
    if not ('protopian' in album.lower() or 'protopian' in s or n.startswith(('hold the light','strange but true'))):
        return None
    key=None
    tests=[('primordial consent','01'),('protopian gambit','02'),('circle and the solitary','03'),('choose your own protopia','04'),('kintsugi protocol','05'),('60 days set in stone','06'),('every border a bridge','07'),('not gods but architects','08'),('eye of the ancestors','09'),('latent space','10'),('hold the light','11'),('strange but true','12'),('adaptable yes','13'),('dont try to fix me','14'),('purple mat','15'),('dont throw a brick','16'),('shifting sands','17'),('heliospheric lantern','18'),('my view of our conversation','21'),('conversations review','21'),('conversation review','21'),('joyful responsible abundance','22'),('dance of the dakini','23')]
    for needle,k in tests:
        if needle in n:key=k;break
    if 'we go beyond' in n:
        key='20' if re.search(r'\b(?:male|he|him)\b',n) or '-22-we-go-beyond' in s or track==22 else '19'
    return next((r for r in registry() if r['key']==key),None)

STYLE='''<style id="network-portrait-style">
.network-portrait-shell{width:min(100%,360px);margin:1.1rem auto;background:#10091b;border:1px solid #75618c;border-radius:14px;overflow:hidden}
.network-portrait-video,video[src*="/assets/protopian-portraits/"],video:has(source[src*="/assets/protopian-portraits/"]){display:block!important;width:100%!important;max-width:360px!important;height:auto!important;min-height:0!important;max-height:none!important;aspect-ratio:9/16!important;object-fit:contain!important;margin-inline:auto!important;background:#08050e;border:0}
.network-portrait-shell p{margin:.55rem .8rem;font-size:.86rem;line-height:1.45}.network-portrait-shell a{color:#e0c5ff;text-decoration:underline}
.phone:has(source[src*="/assets/protopian-portraits/"]),:is(.phone-frame,.phone-screen,.song-frame,.phone-video-wrap,.phone-embed,.video-embed,.phone):has(video[src*="/assets/protopian-portraits/"]),:is(.phone-frame,.phone-screen,.song-frame,.phone-video-wrap,.phone-embed,.video-embed,.phone):has(video[src*="/assets/protopian-portraits/"]),:is(.phone-frame,.phone-screen,.song-frame,.phone-video-wrap,.phone-embed,.video-embed):has(.network-portrait-video){height:auto!important;aspect-ratio:auto!important;min-height:0!important;max-width:380px;margin-inline:auto;overflow:hidden}
</style>'''

def player(r,include_style=True):
    e=html.escape
    warning='<p>Contains strong language.</p>' if r.get('strong_language') else ''
    return (STYLE if include_style else '')+f'''<section class="network-portrait-shell" data-protopian-key="{e(r['key'])}" aria-label="{e(r['title'])}, current portrait lyric video">
<video class="network-portrait-video" controls playsinline preload="none" width="720" height="1280" poster="{e(r['poster_url'])}" aria-label="{e(r['title'])} by i C. infinity"><source src="{e(r['video_url'])}" type="video/mp4"><a href="{e(r['video_url'])}">Open portrait video</a></video>
<p><a href="{e(r['video_url'])}">Open current portrait lyric video</a></p>{warning}</section>'''

def prepare_song(song):
    r=lookup(song.title,getattr(song,'slug',''),getattr(song,'album_slug',''),getattr(song,'track_number',None))
    if r:
        song.lyrics=r['lyrics']
        song.lyric_status='Current portrait performance, 30 October 2026'
        return player(r)
    return ''
