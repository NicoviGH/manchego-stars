#!/usr/bin/env python3
"""banim_palette.py -- a local, offline, in-browser editor for an imported battle anim's
OWN 15 colours, with the animation playing live as you edit them (#25).

Why this exists, and why neither existing tool did it: `map_sprite_swapper` remaps INDICES
against the locked cast palette, and `map_sprite_editor` paints INDICES against a locked
palette too. Both hold the colours still and move the pixels. A vendored community anim
arrives on the author's own palette, and the thing we need to change is the COLOURS --
Ravisin ships auburn-haired in a BLUE robe, and an enemy must read red/frost without
touching her hair, which is the entire reason her animation was chosen.

Why it is not a recolour FUNCTION: the author's index-aligned "enemy" swatch was tried and
rejected on sight because the art does not use those indices the way the swatch suggests --
it turned her hair teal. A ramp cannot be guessed from RGB; it has to be looked at. So this
hands the 15 swatches to Nicolas, the way the map sprites were handed over (`decisions.md`
Art & Audio, and Sahnar's `map_sprite.recipe`: "final index swaps applied by Nicolas").

  usage: banim_palette.py <anim_dir> [--txt Magic.txt] [--port N] [--no-browser]
         banim_palette.py --unit ravisin            # shortcut for a campaign anim dir

ORDER IS LOAD-BEARING. The swatches are read from `feditor_to_banim._palette` itself -- the
same derivation the injector runs at build time -- so swatch N here is index N in the ROM.
Never re-derive that ordering locally (`_palette`'s `1<<24` bound is load-bearing for the
same reason; see its comment).

Apply writes `palette.json` beside the frames: the full ordered NATIVE palette plus the
edited entries. The frame PNGs are never touched, so this is reversible and re-runnable --
the injector applies the edit as `build_import(recolor=...)`, which recolours the agbpal
ONLY and leaves every sheet index alone. A hand edit is a look call, not a re-import.
"""
import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feditor_to_banim as fb  # noqa: E402  (_palette / parse_feditor / _load_frame)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANIMS = os.path.join(REPO, 'campaigns', 'rime-of-the-frostmaiden', 'battle_anims')
EDIT_NAME = 'palette.json'
PAD = 2                      # window margin around the union of every frame's art


def gba_quantize(rgb):
    """Snap a colour to what the GBA can actually show (BGR555, 5 bits a channel).

    A hand-picked colour must be quantized at PICK time, not silently at link time. The
    hardware keeps the top 5 bits of each channel, so #404052 and #404050 are the SAME
    halfword -- and two swatches chosen as distinct ramp steps can collapse into one.
    That is this tool's own "a ramp must stay a ramp" failure, reachable through the tool
    that documents it, so the editor previews and stores only reachable colours."""
    return tuple((c >> 3) << 3 for c in rgb)


def _hex(rgb):
    return '#%02x%02x%02x' % tuple(rgb)


def _unhex(s):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def edit_path(anim_dir):
    return os.path.join(anim_dir, EDIT_NAME)


def save_edit(path, native, edited):
    """Write a hand edit: the ordered NATIVE palette + {index: new rgb} for what changed.

    `native` is recorded in full because the edit is stored per-INDEX: if the frames are
    ever re-vendored and the derived palette shifts, a loader that only kept index->colour
    would repoint every entry silently. Keeping the native colours makes that detectable."""
    blob = {'native': [_hex(c) for c in native],
            'edited': {str(i): _hex(gba_quantize(c)) for i, c in sorted(edited.items())}}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(blob, f, indent=2)
        f.write('\n')


def load_recolor(path):
    """`palette.json` -> an rgb->rgb map for build_import's `recolor` (identity elsewhere).

    Keyed by the native COLOUR, not by index, so it composes with build_import's own
    derivation without either side having to agree on anything but the pixels. A missing
    file raises: a typo'd `palette_edit:` must fail the build, not quietly ship native."""
    with open(path, encoding='utf-8') as f:
        blob = json.load(f)
    native = blob['native']
    table = {_unhex(native[int(i)]): _unhex(c) for i, c in blob['edited'].items()}
    seen = set()

    def recolor(rgb):
        rgb = tuple(rgb)
        if rgb in table:
            seen.add(rgb)
        return table.get(rgb, rgb)
    recolor.edited = table            # what the file asked for
    recolor.seen = seen               # what the live palette actually offered
    recolor.path = path
    return recolor


def assert_all_applied(recolor, who):
    """Every edited colour must have been FOUND in the palette it was applied to.

    The editor edits by INDEX and `load_recolor` applies by COLOUR, and nothing else
    compares the two. Re-vendor the frames and the derived palette can shift: an entry the
    file still names may no longer exist, and that colour would ship NATIVE behind a green
    build, with the editor's preview and the ROM disagreeing and neither complaining. The
    saved `native` block exists precisely so this is detectable -- so detect it."""
    missing = sorted(set(recolor.edited) - recolor.seen)
    if missing:
        sys.exit('ERROR: %s: %s names %d edited colour(s) that are not in the animation\'s '
                 'palette any more (%s) -- the frames were re-vendored under the edit. '
                 'Re-open tools/banim_palette.py on it and re-apply.'
                 % (who, recolor.path, len(missing),
                    ', '.join(_hex(c) for c in missing)))


class Doc:
    """One anim's palette + its frames, as the injector sees them."""

    def __init__(self, anim_dir, txt_name):
        self.anim_dir = anim_dir
        self.txt_name = txt_name
        with open(os.path.join(anim_dir, txt_name), encoding='utf-8') as f:
            self.anim = fb.parse_feditor(f.read())
        self.files = fb.unique_frames(self.anim)
        self.imgs = [fb._load_frame(os.path.join(anim_dir, fn)) for fn in self.files]
        self.palette = fb._palette(self.imgs)          # THE ordering; see module docstring
        self._index = {c: i for i, c in enumerate(self.palette)}
        self.box = self._window()
        self.frames = [self._indices(im) for im in self.imgs]

    def _window(self):
        """ONE box covering every frame's art. Shared, so a pose drawn forward on the
        canvas still reads forward -- the arc IS the motion (banim_paint.crop_window makes
        the same call for the pixel editor, and for the same reason)."""
        boxes = [im.getbbox() for im in self.imgs]
        x0 = min(b[0] for b in boxes) - PAD
        y0 = min(b[1] for b in boxes) - PAD
        x1 = max(b[2] for b in boxes) + PAD
        y1 = max(b[3] for b in boxes) + PAD
        w, h = self.imgs[0].size
        return (max(0, x0), max(0, y0), min(w, x1), min(h, y1))

    def _indices(self, im):
        out = []
        for r, g, b, a in im.crop(self.box).getdata():
            out.append(self._index[(r, g, b)] if a else 0)
        return out

    def timelines(self):
        """Per-mode playback: [(frame slot, duration in 60fps ticks), ...].

        The .txt owns the cadence, so the preview plays at the animation's REAL speed --
        a palette read at the wrong tempo is a different look-test than the one in game."""
        out = {}
        for mode, insns in self.anim.modes.items():
            seq = [[self.files.index(i.file), i.duration]
                   for i in insns if isinstance(i, fb.Frame)]
            if seq:
                out[str(mode)] = seq
        return out

    def data(self):
        counts = [0] * len(self.palette)
        for f in self.frames:
            for p in f:
                counts[p] += 1
        counts[0] = 0                                  # index 0 is transparency, not a colour
        x0, y0, x1, y1 = self.box
        saved = edit_path(self.anim_dir)
        edited = {}
        if os.path.isfile(saved):
            with open(saved, encoding='utf-8') as f:
                edited = json.load(f)['edited']
        return {
            # The browser cache key. NOT the basename: `wildling/unarmed` and
            # `lizardzerker/unarmed` share one, as do every anim's axe/handaxe pair, so a
            # basename key hands one creature's draft to another.
            'key': os.path.relpath(self.anim_dir, REPO),
            'name': os.path.basename(self.anim_dir.rstrip('/')),
            'txt': self.txt_name,
            'w': x1 - x0, 'h': y1 - y0,
            'frames': self.frames,
            'swatches': [{'i': i, 'hex': _hex(c), 'n': counts[i]}
                         for i, c in enumerate(self.palette)],
            'timelines': self.timelines(),
            'edited': edited,
        }


DOC = None
PAGE = r"""<!doctype html><html><head><meta charset=utf-8><title>Battle-anim palette</title>
<style>
:root{color-scheme:dark}
body{margin:0;background:#1b1d22;color:#d7dbe0;font:13px/1.4 system-ui,sans-serif}
header{padding:10px 16px;background:#23262d;border-bottom:1px solid #333;font-weight:600}
header small{font-weight:400;color:#9aa2ad}
.wrap{display:flex;gap:20px;padding:16px;flex-wrap:wrap;align-items:flex-start}
.col{display:flex;flex-direction:column;gap:14px}
.card{background:#23262d;border:1px solid #333;border-radius:8px;padding:12px}
.card h3{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#9aa2ad}
canvas{image-rendering:pixelated;border-radius:4px}
.stage{background:#84a584}
.previews{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}
.pv{display:flex;flex-direction:column;align-items:center;gap:4px}
.pv span{font-size:11px;color:#9aa2ad}
.rows{display:flex;flex-direction:column;gap:5px}
.sw{display:flex;align-items:center;gap:8px;padding:4px 6px;border-radius:6px;border:2px solid transparent}
.sw.iso{border-color:#ffd23f;background:#2c3038}
.sw.unused{opacity:.35}
.sw input[type=color]{width:38px;height:26px;padding:0;border:1px solid #4a505a;border-radius:4px;background:none;cursor:pointer}
.sw b{width:18px;text-align:right;color:#9aa2ad;font-weight:600}
.sw .n{width:56px;color:#7f8792;font-size:11px;text-align:right}
.sw .nat{width:16px;height:16px;border-radius:3px;border:1px solid #444}
.sw .eye{cursor:pointer;opacity:.5;padding:0 4px}
.sw.iso .eye{opacity:1}
.sw .rv{cursor:pointer;color:#e2646d;opacity:0;padding:0 3px;font-weight:700}
.sw.dirty .rv{opacity:1}
.sw.dirty b{color:#ffd23f}
button{background:#3a3f48;color:#e7ebf0;border:1px solid #4a505a;border-radius:6px;padding:7px 12px;cursor:pointer;font-size:13px}
button:hover{background:#454b55}
button.primary{background:#2f6f4f;border-color:#3a865f}
button.primary:hover{background:#357a58}
button.on{background:#4a505a;border-color:#6b7280}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.hint{font-size:11px;color:#9aa2ad;margin:6px 0}
#stat{font-size:12px;color:#9aa2ad;margin-left:6px}
</style></head><body>
<header>Battle-anim palette &mdash; <span id=nm></span>
  <small id=sub></small></header>
<div class=wrap>
  <div class=col>
    <div class=card><h3>Live (the .txt's own cadence)</h3><div class=previews id=previews></div>
      <div class=row style="margin-top:8px">
        <span class=hint>Mode</span><span id=modes class=row></span>
        <button id=bg title="Cycle the backdrop: the preview colour is a look-test, and a palette reads differently on grass, snow and the arena stone.">Backdrop</button>
      </div>
    </div>
    <div class=card><h3>Every distinct frame</h3><canvas id=strip></canvas></div>
  </div>
  <div class=col>
    <div class=card><h3>Palette &mdash; click a colour to edit it</h3>
      <div class=rows id=rows></div>
      <div class=hint>👁 isolates one index (everything else greys out) &mdash; that is how you
        tell the HAIR ramp from the ROBE ramp before you move either. Counts are pixels across
        all frames.</div>
    </div>
    <div class=card>
      <div class=row>
        <button class=primary id=apply>Apply to palette.json</button>
        <button id=reset>Revert all</button>
        <span id=stat></span>
      </div>
      <div class=hint>Apply writes the edit beside the frames. The frame PNGs are never
        touched; the injector recolours the palette only.</div>
    </div>
  </div>
</div>
<script>
let D=null, EDIT={}, ISO=null, MODE=null, BG=0;
const BGS=['#84a584','#c8d8e8','#a89880','#282828'];
const $=id=>document.getElementById(id);
/* The GBA keeps 5 bits a channel, so snap every picked colour to what it can SHOW. Picking
   at 8-bit lets two swatches preview as distinct ramp steps and land on one halfword --
   this tool's own "a ramp must stay a ramp" failure. */
const gba=h=>'#'+[1,3,5].map(i=>((parseInt(h.substr(i,2),16)>>3)<<3)
                                .toString(16).padStart(2,'0')).join('');
function cur(i){return (i in EDIT)?EDIT[i]:D.swatches[i].hex}

/* ---- drawing ---- */
function paint(cv,frame,scale){
  cv.width=D.w*scale;cv.height=D.h*scale;
  const x=cv.getContext('2d');
  for(let i=0;i<frame.length;i++){
    const idx=frame[i];if(idx===0)continue;
    if(ISO!==null&&idx!==ISO){x.fillStyle='rgba(120,120,120,.35)';}
    else x.fillStyle=cur(idx);
    x.fillRect((i%D.w)*scale,((i/D.w)|0)*scale,scale,scale);
  }
}
let TIMER=null;
function play(){
  if(TIMER)clearTimeout(TIMER);
  const seq=D.timelines[MODE];let k=0;
  const cv=$('stagecv');
  const step=()=>{
    const [fi,dur]=seq[k%seq.length];
    paint(cv,D.frames[fi],4);
    k++;TIMER=setTimeout(step,dur*1000/60);
  };
  step();
}
function drawStrip(){
  const cv=$('strip'),per=8,sc=2,cols=Math.min(D.frames.length,per);
  const rows=Math.ceil(D.frames.length/per);
  cv.width=cols*D.w*sc;cv.height=rows*D.h*sc;
  const x=cv.getContext('2d');x.fillStyle=BGS[BG];x.fillRect(0,0,cv.width,cv.height);
  D.frames.forEach((f,n)=>{
    const ox=(n%per)*D.w*sc, oy=((n/per)|0)*D.h*sc;
    for(let i=0;i<f.length;i++){
      const idx=f[i];if(idx===0)continue;
      if(ISO!==null&&idx!==ISO){x.fillStyle='rgba(120,120,120,.35)';}
      else x.fillStyle=cur(idx);
      x.fillRect(ox+(i%D.w)*sc,oy+(((i/D.w)|0))*sc,sc,sc);
    }
  });
}
function redraw(){drawStrip();$('stagecv').style.background=BGS[BG];}

/* ---- palette rows ---- */
function rows(){
  const r=$('rows');r.innerHTML='';
  D.swatches.forEach(s=>{
    if(s.i===0)return;                       /* index 0 is transparency */
    const d=document.createElement('div');
    d.className='sw'+(s.n?'':' unused')+(ISO===s.i?' iso':'')+((s.i in EDIT)?' dirty':'');
    const inp=document.createElement('input');inp.type='color';inp.value=cur(s.i);
    inp.oninput=()=>{EDIT[s.i]=gba(inp.value);inp.value=EDIT[s.i];save();rows();redraw();};
    const nat=document.createElement('span');nat.className='nat';nat.style.background=s.hex;
    nat.title='native '+s.hex;
    const b=document.createElement('b');b.textContent=s.i;
    const n=document.createElement('span');n.className='n';n.textContent=s.n?s.n+' px':'unused';
    const eye=document.createElement('span');eye.className='eye';eye.textContent='👁';
    eye.title='Isolate this index';
    eye.onclick=()=>{ISO=(ISO===s.i?null:s.i);rows();redraw();};
    const rv=document.createElement('span');rv.className='rv';rv.textContent='⟲';
    rv.title='Revert this one to native';
    rv.onclick=()=>{delete EDIT[s.i];save();rows();redraw();};
    d.append(b,eye,inp,nat,n,rv);r.appendChild(d);
  });
}
function modes(){
  const m=$('modes');m.innerHTML='';
  Object.keys(D.timelines).sort((a,b)=>a-b).forEach(k=>{
    const b=document.createElement('button');b.textContent=k;
    if(k===MODE)b.className='on';
    b.onclick=()=>{MODE=k;modes();play();};m.appendChild(b);
  });
}
/* The DRAFT is unsaved work; palette.json on disk is the applied truth. A draft is only
   restored when it was taken from the state the disk is still in (`base`), so hitting
   Apply can never write a stale edit back over a newer file -- and it is keyed on the
   anim's repo-relative PATH, since basenames collide across anim folders. */
function save(){localStorage.setItem('banimpal:'+D.key,
    JSON.stringify({base:D.edited,edit:EDIT}));}
function status(t){$('stat').textContent=t;}

/* ---- boot ---- */
fetch('/data').then(r=>r.json()).then(d=>{
  D=d;
  const stored=localStorage.getItem('banimpal:'+D.key);
  EDIT = Object.assign({},D.edited);                     /* disk is the applied truth */
  if(stored){
    const s=JSON.parse(stored);
    /* restore the draft only if it was taken from the state the disk is STILL in */
    if(JSON.stringify(s.base||{})===JSON.stringify(D.edited)) EDIT=s.edit||EDIT;
  }
  $('nm').textContent=D.name;
  $('sub').textContent=' — '+D.txt+', '+D.frames.length+' distinct frames, '
      +(D.swatches.length-1)+' colours';
  const pv=document.createElement('div');pv.className='pv';
  const cv=document.createElement('canvas');cv.id='stagecv';cv.className='stage';
  const cap=document.createElement('span');cap.textContent='playing';
  pv.append(cv,cap);$('previews').appendChild(pv);
  MODE=Object.keys(D.timelines).sort((a,b)=>a-b)[0];
  rows();modes();redraw();play();
});
$('bg').onclick=()=>{BG=(BG+1)%BGS.length;redraw();};
$('reset').onclick=()=>{EDIT={};save();rows();redraw();status('reverted (not yet applied)');};
$('apply').onclick=()=>{
  fetch('/apply',{method:'POST',body:JSON.stringify(EDIT)})
    .then(r=>r.text()).then(t=>status(t));
};
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype='text/html; charset=utf-8'):
        body = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith('/data'):
            self._send(json.dumps(DOC.data()), 'application/json')
        else:
            self._send(PAGE)

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        edit = json.loads(self.rfile.read(n) or '{}')
        edited = {int(k): _unhex(v) for k, v in edit.items()}
        path = edit_path(DOC.anim_dir)
        save_edit(path, DOC.palette, edited)
        print('  wrote %s (%d edited entr%s)'
              % (path, len(edited), 'y' if len(edited) == 1 else 'ies'))
        self._send('applied %d → %s' % (len(edited), EDIT_NAME), 'text/plain')

    def log_message(self, *a):
        pass


def main():
    global DOC
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('anim_dir', nargs='?')
    ap.add_argument('--unit', help='campaign battle_anims/<unit> shortcut')
    ap.add_argument('--txt', help='the FEditor script (default: the only .txt in the dir)')
    ap.add_argument('--port', type=int, default=8767)
    ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args()

    adir = a.anim_dir or (os.path.join(ANIMS, a.unit) if a.unit else None)
    if not adir or not os.path.isdir(adir):
        sys.exit('usage: banim_palette.py <anim_dir> | --unit <id>')
    txt = a.txt
    if not txt:
        found = sorted(f for f in os.listdir(adir) if f.endswith('.txt'))
        if len(found) != 1:
            sys.exit('ERROR: %d .txt scripts in %s; pass --txt' % (len(found), adir))
        txt = found[0]

    DOC = Doc(adir, txt)
    print('%s: %d distinct frames, %d colours, window %s'
          % (os.path.basename(adir), len(DOC.frames), len(DOC.palette) - 1, DOC.box))
    url = 'http://127.0.0.1:%d/' % a.port
    print('  %s   (Ctrl-C to stop)' % url)
    if not a.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        HTTPServer(('127.0.0.1', a.port), Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nstopped')


if __name__ == '__main__':
    main()
