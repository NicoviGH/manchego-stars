#!/usr/bin/env python3
"""Generate a self-contained HTML tile-map editor for any chapter map: embeds the winter
metatile atlas + a winter-reskinned vanilla layout as the starting point + terrain data.
Nicolas paints in-browser and exports a layout JSON, which import_map_layout.py compiles.

Usage: gen_map_editor.py [vanilla_layout=PrologueMap] [out_html=editor.html] [download=prologue-layout.json]
e.g.   gen_map_editor.py Ch13EirikaMap 21-iron-trail/editor.html ch01-layout.json"""
import sys, os, struct, collections, json, io, base64
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (worktree-aware)
DEC=os.path.join(ROOT,'fireemblem8u')
sys.path.insert(0, os.path.join(ROOT,'tools'))
from map_tileset_tool import _tileset_from_dir, Tileset
from PIL import Image

LAYOUT=sys.argv[1] if len(sys.argv)>1 else 'PrologueMap'
OUT_HTML=sys.argv[2] if len(sys.argv)>2 else 'editor.html'
DOWNLOAD=sys.argv[3] if len(sys.argv)>3 else 'prologue-layout.json'

win=_tileset_from_dir(os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps/tilesets/snowy-bern'))
# `van` is consulted ONLY for .terrain(m) (vanilla tileset-1 terrain table) to decide which
# reskinned cells diverge; its gfx/pal are never rendered. The decomp's raw vanilla gfx
# (ObjectType1.4bpp / MapPalette1.gbapal) are build-only artifacts and may be absent, so we
# feed the winter gfx/pal (irrelevant) alongside the real vanilla config.
SNOW=os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps/tilesets/snowy-bern')
van=Tileset(os.path.join(SNOW,'snowy-bern.4bpp'),
            os.path.join(SNOW,'snowy-bern.gbapal'),
            os.path.join(DEC,'graphics/map/TileConfiguration1.bin'))
lay=open(os.path.join(DEC,f'graphics/map/layout/{LAYOUT}.bin'),'rb').read()
W,H=lay[0],lay[1]
cells=[struct.unpack_from('<H',lay,2+i*2)[0]//4 for i in range(W*H)]

# current final grid (base iron-out + remap + manual)  -> editor starting point
def divergent(m): return win.terrain(m)!=van.terrain(m)
modec=collections.defaultdict(collections.Counter)
for m in cells:
    if not divergent(m): modec[van.terrain(m)][m]+=1
MODE={t:c.most_common(1)[0][0] for t,c in modec.items()}
FB={0x01:6,0x0c:192,0x10:568,0x12:418,0x13:2}
resolved=[0]*(W*H)
for y in range(H):
    for x in range(W):
        m=cells[y*W+x]
        if not divergent(m): resolved[y*W+x]=m; continue
        vt=van.terrain(m); nb=collections.Counter()
        for dy in(-1,0,1):
            for dx in(-1,0,1):
                if dx==0 and dy==0: continue
                nx,ny=x+dx,y+dy
                if 0<=nx<W and 0<=ny<H:
                    nm=cells[ny*W+nx]
                    if not divergent(nm) and van.terrain(nm)==vt: nb[nm]+=1
        resolved[y*W+x]=nb.most_common(1)[0][0] if nb else MODE.get(vt,FB.get(vt,m))
# Learned reskin: Nicolas's hand-retiles (reskin-learned.json) override the naive auto-reskin
# for any vanilla metatile he's already taught, so each new chapter inherits his conventions
# (villages, mountains, forests...) as the starting point instead of the smeared default.
_learned_path=os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps/reskin-learned.json')
_learned=json.load(open(_learned_path)).get('map',{}) if os.path.exists(_learned_path) else {}
for i in range(W*H):
    w=_learned.get(str(cells[i]))
    if w is not None: resolved[i]=w
# prologue-era hand overrides apply only to the original PrologueMap session
_isproto = LAYOUT=='PrologueMap'
remap={int(k):v for k,v in json.load(open(os.path.join(ROOT,'map-review/_remap.json'))).items()} if _isproto and os.path.exists(os.path.join(ROOT,'map-review/_remap.json')) else {}
manual=json.load(open(os.path.join(ROOT,'map-review/_manual.json'))) if _isproto and os.path.exists(os.path.join(ROOT,'map-review/_manual.json')) else {}
def lbl(i): x,y=i%W,i//W; return '%s%d'%(chr(ord('A')+x),y+1)
grid=[]
for i in range(W*H):
    t=manual.get(lbl(i), resolved[i]); grid.append(remap.get(t,t))

# Optional 4th arg: seed the editable grid from an existing compiled .mar so Nicolas
# continues editing the CURRENT chapter map (gate, prior hand-retiles) instead of a
# fresh reskin of the vanilla layout. The .mar stores metatile<<5 (see compile_layout);
# its sibling .json carries the dims, which must match the chosen layout.
SEED_MAR=sys.argv[4] if len(sys.argv)>4 else None
if SEED_MAR:
    SEED_MAR=os.path.expanduser(SEED_MAR)
    seed=open(SEED_MAR,'rb').read()
    sj=json.load(open(os.path.splitext(SEED_MAR)[0]+'.json'))
    if (sj['width'],sj['height'])!=(W,H):
        sys.exit('ERROR: seed .mar is %dx%d but layout %s is %dx%d'
                 %(sj['width'],sj['height'],LAYOUT,W,H))
    grid=[struct.unpack_from('<H',seed,i*2)[0]>>5 for i in range(W*H)]
    print('seeded editable grid from',SEED_MAR)

# atlas image: 32 cols x 32 rows of 16px tiles (clean, contiguous)
ACOLS=32; AROWS=32
atlas=Image.new('RGB',(ACOLS*16, AROWS*16))
for m in range(1024):
    atlas.paste(win.metatile_image(m), ((m%ACOLS)*16,(m//ACOLS)*16))
buf=io.BytesIO(); atlas.save(buf,'PNG'); ATLAS=base64.b64encode(buf.getvalue()).decode()

# vanilla-art reference: the ORIGINAL FE8 layout in its native tileset, for side-by-side
# comparison while painting. The raw .4bpp/.gbapal are build-only artifacts often absent
# in a fresh tree, so build them on demand with the decomp's OWN gbagfx (authoritative;
# a hand-rolled PNG/JASC decode gets the palette wrong), then render via the standard path.
import subprocess
def _ensure_built(src, dst):
    if not os.path.exists(dst):
        subprocess.run([os.path.join(DEC,'tools/gbagfx/gbagfx'), src, dst], check=True)
_ensure_built(os.path.join(DEC,'graphics/map/ObjectType1.png'),  os.path.join(DEC,'graphics/map/ObjectType1.4bpp'))
_ensure_built(os.path.join(DEC,'graphics/map/MapPalette1.pal'),  os.path.join(DEC,'graphics/map/MapPalette1.gbapal'))
vanart=Tileset(os.path.join(DEC,'graphics/map/ObjectType1.4bpp'),
               os.path.join(DEC,'graphics/map/MapPalette1.gbapal'),
               os.path.join(DEC,'graphics/map/TileConfiguration1.bin'))
vref=Image.new('RGB',(W*16,H*16))
for i,m in enumerate(cells):
    vref.paste(vanart.metatile_image(m),((i%W)*16,(i//W)*16))
vbuf=io.BytesIO(); vref.save(vbuf,'PNG'); VANREF=base64.b64encode(vbuf.getvalue()).decode()

def nonempty(m): return any(struct.unpack_from('<H',win.cfg,m*8+s*2)[0]&0x3FF for s in range(4))
def is_filler(m):
    """A solid-orange placeholder slot in the community tileset (not a paintable tile)."""
    d=win.metatile_image(m).getdata()
    if len(set(d))>3: return False
    r,g,b=collections.Counter(d).most_common(1)[0][0]
    return r>180 and 90<g<190 and b<90
TERR=[win.terrain(m) for m in range(1024)]
# palette = real, paintable tiles only — drop empty + orange-filler slots that just clutter it
PAL=[m for m in range(1024) if nonempty(m) and not is_filler(m)]
# friendly names for EVERY terrain id present (decomp's terrains.h ids, named for a winter map
# so the unnamed "Tile 2C/2E/Stairs/Ruins" slots that actually hold frozen BUILDINGS read clearly)
TNAME={0x00:'(empty)',0x01:'Snow ground',0x02:'Road / path',0x03:'Village (visit)',
0x04:'Village (used)',0x05:'House',0x06:'Armory',0x07:'Vendor',0x08:'Arena',0x0a:'Fort / cairn',
0x0b:'Gate',0x0c:'Pines (forest)',0x0d:'Thicket',0x10:'River / ice',0x11:'Mountain',
0x12:'Peak (impass.)',0x13:'Bridge',0x15:'Sea / ice',0x17:'Floor',0x19:'Fence',
0x1a:'Wall (impass.)',0x1b:'Wall (broken)',0x1d:'Pillar',0x1e:'Door',0x1f:'Throne',
0x20:'Chest (empty)',0x21:'Chest',0x25:'Ruins / wall',0x26:'Cliff (impass.)',
0x2c:'Building edge',0x2d:'Stairs / floor',0x2e:'Building / roof',0x32:'Fence',
0x34:'Bridge',0x36:'Deep ice',0x3c:'Water',0x3f:'Ship / brace'}

HTML=r'''<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__ Map Editor</title>
<style>
 body{font-family:-apple-system,sans-serif;margin:0;background:#1d1f23;color:#e8e8e8;display:flex;height:100vh;overflow:hidden}
 #left{padding:10px;overflow:auto}#right{flex:1;padding:10px;overflow:auto;border-left:1px solid #3a3d44;min-width:360px}
 canvas{image-rendering:pixelated;background:#000}
 .bar{padding:8px;background:#2a2d33;border-radius:6px;margin-bottom:8px;line-height:1.8}
 button,select{font-size:13px;padding:4px 8px;margin:2px;background:#3a3d44;color:#eee;border:1px solid #555;border-radius:4px;cursor:pointer}
 button:hover{background:#4a4e57}.hint{font-size:12px;color:#9aa}
 b{color:#ffd84d}
</style></head><body>
<div id="left">
 <div class="bar">
  <b>MAP</b> &nbsp; mode:
  <select id="mode"><option value="one">paint one cell</option><option value="all">replace ALL matching (global)</option></select>
  <button id="undo">undo (z)</button>
  <button id="export">⬇ Export layout</button>
  <label style="margin-left:8px"><input type="checkbox" id="grid" checked> grid &amp; terrain borders (g)</label>
  <span id="brush" class="hint"></span>
 </div>
 <div style="display:flex;gap:14px;align-items:flex-start">
  <div><div class="hint" style="margin-bottom:4px"><b>VANILLA</b> reference (read-only)</div><canvas id="ref"></canvas></div>
  <div><div class="hint" style="margin-bottom:4px"><b>YOUR MAP</b> — paint here</div><canvas id="map"></canvas></div>
 </div>
 <div class="hint" id="cell">hover a cell…</div>
 <div class="bar" style="margin-top:8px"><b>How to use:</b> 1) pick a tile on the right (it becomes your brush) &nbsp; 2) click/drag on the map to paint &nbsp; 3) <b>Export</b> → a <i>__DOWNLOAD__</i> downloads &nbsp; 4) tell Claude "exported" and it compiles + renders.</div>
 <textarea id="out" style="width:680px;height:70px;display:none;background:#111;color:#6f6"></textarea>
</div>
<div id="right">
 <div class="bar"><b>TILE PALETTE</b> — click to pick brush. filter:
  <select id="filter"></select> &nbsp;<span class="hint">green=walkable border on map</span></div>
 <canvas id="pal"></canvas>
</div>
<script>
const W=__W__,H=__H__,T=16,ACOLS=__ACOLS__;
let GRID=__GRID__; const TERR=__TERR__,PAL=__PAL__,TNAME=__TNAME__;
const WALK=new Set([0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x0a,0x0b,0x0c,0x0d,0x0e,0x13,0x17,0x1f]);
const atlas=new Image(); atlas.src="data:image/png;base64,__ATLAS__";
const vanref=new Image(); vanref.src="data:image/png;base64,__VANREF__";
const MC=48, PC=34, PCOLS=16;
const map=document.getElementById('map'), mx=map.getContext('2d');
const ref=document.getElementById('ref'), rx=ref.getContext('2d');
const pal=document.getElementById('pal'), px=pal.getContext('2d');
map.width=W*MC; map.height=H*MC;
ref.width=W*MC; ref.height=H*MC; rx.imageSmoothingEnabled=false;
function drawRef(hl){
 if(vanref.complete) rx.drawImage(vanref,0,0,W*MC,H*MC);
 if(showGrid) for(let i=0;i<W*H;i++){const x=(i%W)*MC,y=(Math.floor(i/W))*MC;
  rx.strokeStyle='rgba(255,255,255,0.12)';rx.lineWidth=1;rx.strokeRect(x+0.5,y+0.5,MC,MC);}
 if(hl>=0){const x=(hl%W)*MC,y=(Math.floor(hl/W))*MC;
  rx.strokeStyle='#ffd84d';rx.lineWidth=3;rx.strokeRect(x+1,y+1,MC-2,MC-2);}
}
let brush=PAL[0], hist=[], curFilter='all', palList=PAL.slice(), showGrid=true;

function tileSrc(m){return [(m%ACOLS)*T,(Math.floor(m/ACOLS))*T];}
function drawMap(){
 for(let i=0;i<W*H;i++){const m=GRID[i],x=(i%W)*MC,y=(Math.floor(i/W))*MC;
  const[s,t]=tileSrc(m); mx.drawImage(atlas,s,t,T,T,x,y,MC,MC);
  if(showGrid){mx.strokeStyle=WALK.has(TERR[m])?'#28d228':'#eb2d2d'; mx.lineWidth=2;
   mx.strokeRect(x+1,y+1,MC-2,MC-2);}}
}
function buildFilter(){
 const f=document.getElementById('filter'); const terrs=[...new Set(PAL.map(m=>TERR[m]))].sort((a,b)=>a-b);
 f.innerHTML='<option value="all">all ('+PAL.length+')</option>'+terrs.map(t=>{
   const n=PAL.filter(m=>TERR[m]===t).length; return '<option value="'+t+'">'+(TNAME[t]||('0x'+t.toString(16)))+' ('+n+')</option>';}).join('');
 f.onchange=()=>{curFilter=f.value; palList=(curFilter==='all')?PAL.slice():PAL.filter(m=>TERR[m]===+curFilter); drawPal();};
}
function drawPal(){
 const rows=Math.ceil(palList.length/PCOLS); pal.width=PCOLS*PC; pal.height=rows*PC;
 px.clearRect(0,0,pal.width,pal.height);
 palList.forEach((m,k)=>{const x=(k%PCOLS)*PC,y=Math.floor(k/PCOLS)*PC;const[s,t]=tileSrc(m);
  px.drawImage(atlas,s,t,T,T,x,y,PC-2,PC-2);
  if(m===brush){px.strokeStyle='#ffd84d';px.lineWidth=3;px.strokeRect(x+1,y+1,PC-4,PC-4);}});
}
function setBrush(m){brush=m;document.getElementById('brush').textContent='brush = tile i'+m+' ('+(TNAME[TERR[m]]||TERR[m])+')';drawPal();}
function paintAt(i){
 hist.push(GRID.slice());
 if(document.getElementById('mode').value==='all'){const old=GRID[i];for(let j=0;j<GRID.length;j++)if(GRID[j]===old)GRID[j]=brush;}
 else GRID[i]=brush;
 drawMap();
}
let down=false;
function cellAt(e){const r=map.getBoundingClientRect();const x=Math.floor((e.clientX-r.left)/MC),y=Math.floor((e.clientY-r.top)/MC);return (x>=0&&x<W&&y>=0&&y<H)?y*W+x:-1;}
map.onmousedown=e=>{down=true;const i=cellAt(e);if(i>=0)paintAt(i);};
map.onmousemove=e=>{const i=cellAt(e);if(i>=0){const x=i%W,y=Math.floor(i/W);document.getElementById('cell').textContent=String.fromCharCode(65+x)+(y+1)+'  tile i'+GRID[i]+' ('+(TNAME[TERR[GRID[i]]]||TERR[GRID[i]])+')';drawRef(i);if(down)paintAt(i);}};
map.onmouseleave=()=>drawRef(-1);
window.onmouseup=()=>down=false;
pal.onmousedown=e=>{const r=pal.getBoundingClientRect();const k=Math.floor((e.clientY-r.top)/PC)*PCOLS+Math.floor((e.clientX-r.left)/PC);if(k>=0&&k<palList.length)setBrush(palList[k]);};
document.getElementById('undo').onclick=()=>{if(hist.length){GRID=hist.pop();drawMap();}};
document.getElementById('grid').onchange=e=>{showGrid=e.target.checked;drawMap();drawRef(-1);};
window.onkeydown=e=>{
 if(e.key==='z'){if(hist.length){GRID=hist.pop();drawMap();}}
 if(e.key==='g'){const g=document.getElementById('grid');g.checked=!g.checked;showGrid=g.checked;drawMap();drawRef(-1);}
};
document.getElementById('export').onclick=()=>{
 const js=JSON.stringify({width:W,height:H,grid:GRID});
 const ta=document.getElementById('out');ta.style.display='block';ta.value=js;
 const b=new Blob([js],{type:'application/json'});const a=document.createElement('a');
 a.href=URL.createObjectURL(b);a.download='__DOWNLOAD__';a.click();
};
atlas.onload=()=>{drawMap();buildFilter();drawPal();setBrush(brush);drawRef(-1);};
vanref.onload=()=>drawRef(-1);
</script></body></html>'''

out=(HTML.replace('__W__',str(W)).replace('__H__',str(H)).replace('__ACOLS__',str(ACOLS))
     .replace('__GRID__',json.dumps(grid)).replace('__TERR__',json.dumps(TERR))
     .replace('__PAL__',json.dumps(PAL)).replace('__TNAME__',json.dumps({str(k):v for k,v in TNAME.items()}))
     .replace('__ATLAS__',ATLAS).replace('__VANREF__',VANREF)
     .replace('__DOWNLOAD__',DOWNLOAD).replace('__TITLE__',LAYOUT))
# TNAME keys must be numeric in JS object -> emit as numbers
out=out.replace(json.dumps({str(k):v for k,v in TNAME.items()}),
                '{'+','.join('%d:%s'%(k,json.dumps(v)) for k,v in TNAME.items())+'}')
path=os.path.join(ROOT,'map-review',OUT_HTML)
os.makedirs(os.path.dirname(path),exist_ok=True)
open(path,'w').write(out)
print('wrote',path,'(%d KB)'%(len(out)//1024))

# Dump the auto-reskinned starting grid as an importable layout JSON (so the faithful
# winter reskin can be compiled/rendered immediately, before any hand-painting), and
# render a PNG preview of it so the starting point is visible without opening the editor.
start_json=os.path.join(ROOT,'map-review',DOWNLOAD)
json.dump({'width':W,'height':H,'grid':grid},open(start_json,'w'))
print('wrote starting layout',start_json)
Z=4*16
prev=Image.new('RGB',(W*Z,H*Z))
for i,m in enumerate(grid):
    prev.paste(win.metatile_image(m).resize((Z,Z),Image.NEAREST),((i%W)*Z,(i//W)*Z))
png=os.path.join(ROOT,'map-review',os.path.splitext(os.path.basename(OUT_HTML))[0]+'-start.png')
prev.save(png)
print('rendered start preview',png)
