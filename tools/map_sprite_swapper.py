#!/usr/bin/env python3
"""map_sprite_swapper.py -- a local, offline, in-browser UI for GLOBAL cast-palette
INDEX SWAPS on a cast member's map sprite (idle + walk together).

Why this exists (issue #38 art loop): the cast sheets are indexed on the locked cast
palette, so a "colour swap" is just remapping one cast index to another EVERYWHERE --
which applies to every frame of both the idle and the walk sheet at once, drift-free
(unlike the pixel editor's position-based "all frames"). This serves a tiny single-page
UI to 127.0.0.1: pick from->to swaps, see the live idle+walk preview update, keep the
running swap set in front of you, and Apply it straight into the indexed PNGs.

It is deliberately framework-free (stdlib http.server + Pillow) and nothing leaves the
machine. Swaps are remembered in the browser (localStorage) so a refresh keeps track.

  usage: map_sprite_swapper.py <idle.png> <walk.png> <cast_palette.png> [--port N] [--no-browser]
         map_sprite_swapper.py --trex            # shortcut for the Trex sheets

Apply writes the remap into BOTH PNGs (indices only; the cast palette is untouched).
"""
import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MS = os.path.join(REPO, 'campaigns', 'rime-of-the-frostmaiden', 'map_sprites')

# Which MU (walk) frames make up each direction's cycle (FE8 move sheet = 15x 32x32,
# three 5-frame direction runs). Display-only grouping for the preview.
WALK_DIRS = {'down': [5, 6, 7, 8, 9], 'side': [0, 1, 2, 3, 4], 'up': [10, 11, 12, 13, 14]}


def _sheet(path, fw, fh):
    im = Image.open(path)
    if im.mode != 'P':
        sys.exit('ERROR: %s is mode %s; expected an indexed (mode P) sheet' % (path, im.mode))
    n = im.height // fh
    data = list(im.getdata())
    per = fw * fh
    frames = [data[i * per:(i + 1) * per] for i in range(n)]
    return {'w': fw, 'h': fh, 'n': n, 'frames': frames}


class Doc:
    def __init__(self, idle_path, walk_path, pal_path, idle_fh=16):
        self.idle_path, self.walk_path, self.pal_path = idle_path, walk_path, pal_path
        self.idle_fh = idle_fh
        pal = Image.open(pal_path).getpalette()[:48]
        self.palette = [[pal[3 * i], pal[3 * i + 1], pal[3 * i + 2]] for i in range(16)]

    def data(self):
        return {
            'palette': self.palette,
            'idle': _sheet(self.idle_path, 16, self.idle_fh),
            'walk': _sheet(self.walk_path, 32, 32),
            'walkDirs': WALK_DIRS,
            'names': {'idle': os.path.basename(self.idle_path),
                      'walk': os.path.basename(self.walk_path)},
        }

    def apply(self, idle_swaps, walk_swaps):
        """Per-sheet index remaps: idle_swaps -> the idle sheet, walk_swaps -> the walk sheet
        (single pass each, from the current on-disk indices). Idle and walk are independent."""
        for path, swaps in ((self.idle_path, idle_swaps), (self.walk_path, walk_swaps)):
            remap = {int(k): int(v) for k, v in (swaps or {}).items()}
            if not remap:
                continue
            im = Image.open(path)
            pal = im.getpalette()
            im.putdata([remap.get(px, px) for px in im.getdata()])
            im.putpalette(pal)
            im.save(path)
        return True


DOC = None
PAGE = r"""<!doctype html><html><head><meta charset=utf-8><title>Map-sprite swapper</title>
<style>
:root{color-scheme:dark}
body{margin:0;background:#1b1d22;color:#d7dbe0;font:13px/1.4 system-ui,sans-serif}
header{padding:10px 16px;background:#23262d;border-bottom:1px solid #333;font-weight:600}
.wrap{display:flex;gap:20px;padding:16px;flex-wrap:wrap}
.col{display:flex;flex-direction:column;gap:14px}
.card{background:#23262d;border:1px solid #333;border-radius:8px;padding:12px}
.card h3{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#9aa2ad}
canvas{image-rendering:pixelated;background:#84a584;border-radius:4px}
.previews{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}
.pv{display:flex;flex-direction:column;align-items:center;gap:4px}
.pv span{font-size:11px;color:#9aa2ad}
.pal{display:grid;grid-template-columns:repeat(8,1fr);gap:4px}
.sw{position:relative;height:34px;border-radius:4px;cursor:pointer;border:2px solid transparent;display:flex;align-items:flex-end;justify-content:center}
.sw.sel{border-color:#fff}
.sw.src{border-color:#ffd23f}
.sw b{font-size:10px;background:rgba(0,0,0,.5);padding:0 3px;border-radius:3px}
.sw.unused{opacity:.35}
.hint{font-size:11px;color:#9aa2ad;margin:6px 0}
.chips{display:flex;flex-wrap:wrap;gap:6px;min-height:26px}
.chip{display:flex;align-items:center;gap:6px;background:#2c3038;border:1px solid #3a3f48;border-radius:14px;padding:3px 6px 3px 3px;font-size:12px}
.chip .box{width:14px;height:14px;border-radius:3px;display:inline-block}
.chip .x{cursor:pointer;color:#e2646d;font-weight:700;padding:0 2px}
button{background:#3a3f48;color:#e7ebf0;border:1px solid #4a505a;border-radius:6px;padding:7px 12px;cursor:pointer;font-size:13px}
button:hover{background:#454b55}
button.primary{background:#2f6f4f;border-color:#3a865f}
button.primary:hover{background:#357a58}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
#stat{font-size:12px;color:#9aa2ad;margin-left:6px}
.arrow{color:#9aa2ad}
</style></head><body>
<header>Map-sprite palette swapper &mdash; <span id=names></span></header>
<div class=wrap>
  <div class=col>
    <div class=card><h3>Preview (live)</h3><div class=previews id=previews></div></div>
    <div class=card>
      <h3>Swap target</h3>
      <div class=row id=targetRow>
        <button data-t=both class=primary>Both</button>
        <button data-t=idle>Idle only</button>
        <button data-t=walk>Walk only</button>
        <span class=hint>New swaps apply to the selected sheet(s). Idle and walk keep separate sets.</span>
      </div>
    </div>
    <div class=card>
      <h3>Idle swaps</h3>
      <div class=chips id=chipsIdle></div>
    </div>
    <div class=card>
      <h3>Walk swaps</h3>
      <div class=chips id=chipsWalk></div>
    </div>
    <div class=card>
      <div class=hint>Click a <b style="color:#ffd23f">source</b> swatch, then a target swatch, to add a swap (goes to the selected target sheet). One target per source, per sheet.</div>
      <div class=row>
        <button class=primary id=apply>Apply to files</button>
        <button id=reset>Reset all</button>
        <span id=stat></span>
      </div>
    </div>
  </div>
  <div class=col>
    <div class=card><h3>Cast palette (click to swap)</h3><div class=pal id=pal></div>
      <div class=hint id=palhint></div></div>
  </div>
</div>
<script>
let D=null, SW={idle:{},walk:{}}, src=null, TARGET='both';
const $=id=>document.getElementById(id);
function css(rgb){return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`}
function eff(i,which){const m=SW[which];return (i in m)?m[i]:i}   // effective index after that sheet's swaps
function usedSet(){const u=new Set();for(const s of [D.idle,D.walk])for(const f of s.frames)for(const p of f)u.add(p);return u}
function drawFrame(cv,sheet,fi,scale,which){
  const {w,h}=sheet, f=sheet.frames[fi];
  cv.width=w*scale;cv.height=h*scale;const x=cv.getContext('2d');
  for(let i=0;i<f.length;i++){const idx=eff(f[i],which);if(idx===0)continue;
    x.fillStyle=css(D.palette[idx]);x.fillRect((i%w)*scale,((i/w)|0)*scale,scale,scale);}
}
function mkPreview(label,sheet,frames,scale,dur,which){
  const wrap=document.createElement('div');wrap.className='pv';
  const cv=document.createElement('canvas');const cap=document.createElement('span');cap.textContent=label;
  wrap.appendChild(cv);wrap.appendChild(cap);$('previews').appendChild(wrap);
  let k=0;const tick=()=>{drawFrame(cv,sheet,frames[k%frames.length],scale,which);k++;};
  tick();return {timer:setInterval(tick,dur)};
}
let PVs=[];
function buildPreviews(){
  $('previews').innerHTML='';PVs.forEach(p=>clearInterval(p.timer));PVs=[];
  PVs.push(mkPreview('idle',D.idle,[0,1,2,1],9,300,'idle'));
  for(const [dir,fr] of Object.entries(D.walkDirs)) PVs.push(mkPreview('walk '+dir,D.walk,fr,5,140,'walk'));
}
function renderPalette(){
  const used=usedSet();const pal=$('pal');pal.innerHTML='';
  D.palette.forEach((rgb,i)=>{
    const d=document.createElement('div');d.className='sw'+(used.has(i)?'':' unused')+(src===i?' src':'');
    d.style.background=css(rgb);d.innerHTML=`<b>${i}</b>`;
    d.title=(i===0?'transparent':'')+(used.has(i)?' (used)':' (unused)');
    d.onclick=()=>pick(i);pal.appendChild(d);
  });
  $('palhint').textContent = src===null ?
      ('Target = '+TARGET+'. Pick a SOURCE colour to swap from.') :
      ('Now pick the TARGET colour to map '+src+' → ? in ['+TARGET+'] (or click '+src+' again to cancel).');
}
function targetSheets(){return TARGET==='both'?['idle','walk']:[TARGET]}
function pick(i){
  if(src===null){src=i;}
  else if(i===src){src=null;}
  else{ for(const sh of targetSheets()) SW[sh][src]=i; src=null; save(); }
  renderPalette();renderChips();
}
function chipPanel(which,elId){
  const c=$(elId);c.innerHTML='';const m=SW[which];
  const keys=Object.keys(m).map(Number).sort((a,b)=>a-b);
  if(!keys.length){c.innerHTML='<span class=hint>No '+which+' swaps &mdash; clean recolour.</span>';return;}
  keys.forEach(s=>{const t=m[s];const chip=document.createElement('div');chip.className='chip';
    chip.innerHTML=`<span class=box style="background:${css(D.palette[s])}"></span>${s}<span class=arrow>→</span>`+
      `<span class=box style="background:${css(D.palette[t])}"></span>${t}<span class=x title=remove>✕</span>`;
    chip.querySelector('.x').onclick=()=>{delete m[s];save();renderPalette();renderChips();};
    c.appendChild(chip);});
}
function renderChips(){chipPanel('idle','chipsIdle');chipPanel('walk','chipsWalk');}
function save(){localStorage.setItem('trexswaps2',JSON.stringify(SW));}
function load(){try{const v=JSON.parse(localStorage.getItem('trexswaps2')||'{}');SW={idle:v.idle||{},walk:v.walk||{}}}catch(e){SW={idle:{},walk:{}}}}
function setTarget(t){TARGET=t;src=null;
  for(const b of $('targetRow').querySelectorAll('button')) b.className=(b.dataset.t===t?'primary':'');
  renderPalette();}
async function boot(){
  D=await (await fetch('/data')).json();
  $('names').textContent=D.names.idle+' + '+D.names.walk;
  load();buildPreviews();renderPalette();renderChips();
  for(const b of $('targetRow').querySelectorAll('button')) b.onclick=()=>setTarget(b.dataset.t);
  $('reset').onclick=()=>{SW={idle:{},walk:{}};src=null;save();renderPalette();renderChips();};
  $('apply').onclick=async()=>{
    $('stat').textContent='applying…';
    const r=await (await fetch('/apply',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({idle:SW.idle,walk:SW.walk})})).json();
    if(r.ok){ // baked into the files; reload fresh data and clear pending sets
      SW={idle:{},walk:{}};save();D=await (await fetch('/data')).json();buildPreviews();renderPalette();renderChips();
      $('stat').textContent='applied ✓ baked into '+D.names.idle+' + '+D.names.walk;
    } else $('stat').textContent='error: '+r.error;
  };
}
boot();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='text/html'):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == '/' or self.path.startswith('/index'):
            self._send(200, PAGE)
        elif self.path == '/data':
            self._send(200, json.dumps(DOC.data()), 'application/json')
        else:
            self._send(404, 'not found')

    def do_POST(self):
        if self.path != '/apply':
            return self._send(404, 'not found')
        n = int(self.headers.get('Content-Length', 0))
        try:
            payload = json.loads(self.rfile.read(n) or b'{}')
            DOC.apply(payload.get('idle', {}), payload.get('walk', {}))
            self._send(200, json.dumps({'ok': True}), 'application/json')
        except Exception as exc:  # noqa
            self._send(500, json.dumps({'ok': False, 'error': str(exc)}), 'application/json')


def main():
    global DOC
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('idle', nargs='?')
    ap.add_argument('walk', nargs='?')
    ap.add_argument('palette', nargs='?')
    ap.add_argument('--trex', action='store_true', help='shortcut for the Trex sheets')
    ap.add_argument('--idle-frame-h', type=int, default=16, choices=(16, 32),
                    help='idle frame height (16x16 or 16x32 SMS class)')
    ap.add_argument('--port', type=int, default=8760)
    ap.add_argument('--no-browser', action='store_true')
    args = ap.parse_args()
    if args.trex:
        idle = os.path.join(MS, 'trex.png')
        walk = os.path.join(MS, 'trex_mu.png')
        pal = os.path.join(MS, 'cast_palette.png')
    else:
        if not (args.idle and args.walk and args.palette):
            sys.exit('usage: map_sprite_swapper.py <idle.png> <walk.png> <cast_palette.png>\n'
                     '       map_sprite_swapper.py --trex')
        idle, walk, pal = args.idle, args.walk, args.palette
    DOC = Doc(idle, walk, pal, idle_fh=args.idle_frame_h)
    srv = HTTPServer(('127.0.0.1', args.port), Handler)
    url = 'http://127.0.0.1:%d/' % args.port
    print('map-sprite swapper: %s  (Ctrl-C to stop)' % url)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
