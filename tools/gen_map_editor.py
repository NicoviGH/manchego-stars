#!/usr/bin/env python3
"""Generate a self-contained HTML tile-map editor for any chapter map: embeds a
tileset's metatile atlas + a starting layout + terrain data. Nicolas paints
in-browser and exports a layout JSON, which import_map_layout.py compiles.

Two modes:
1. Vanilla reskin (the ch00-ch02 flow): a winter-reskinned vanilla layout is the
   starting point, the vanilla map renders in the reference pane.
     gen_map_editor.py [vanilla_layout=PrologueMap] [out_html] [download] [seed.mar]
2. Vendored tileset + custom canvas (#40, ch03+): a blank (or seeded) canvas on a
   community tileset; --ref puts any image (e.g. the book map crop) in the
   reference pane. No vanilla layout, no decomp gbagfx needed.
     gen_map_editor.py --tileset=cave-interior --blank=22x30 [--fill=N] \
         [--ref=path.png] [out_html] [download] [seed.mar]"""
import sys, os, struct, collections, json, io, base64
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (worktree-aware)
DEC=os.path.join(ROOT,'fireemblem8u')
sys.path.insert(0, os.path.join(ROOT,'tools'))
from map_tileset_tool import (_tileset_from_dir, preserved_terrain_targets,
                              render_grid, Tileset, vanilla_layout_data)
from PIL import Image

KNOWN_FLAGS={'--tileset','--blank','--fill','--ref','--vanilla'}
FLAGS={}
ARGS=[]
for a in sys.argv[1:]:
    if a.startswith('--'):
        k,_,v=a.partition('=')
        if k not in KNOWN_FLAGS:
            sys.exit('ERROR: unknown flag %r (known: %s)'%(a,' '.join(sorted(KNOWN_FLAGS))))
        if not _:
            sys.exit('ERROR: flags take the --name=value form (got %r)'%a)
        FLAGS[k]=v
    else:
        ARGS.append(a)
TILESET=FLAGS.get('--tileset','snowy-bern')
BLANK=FLAGS.get('--blank')
VANILLA_REF=FLAGS.get('--vanilla')  # blank mode: render this vanilla layout in the reference pane
if BLANK:
    LAYOUT='%s (custom canvas)'%TILESET
    OUT_HTML=ARGS[0] if len(ARGS)>0 else 'editor.html'
    DOWNLOAD=ARGS[1] if len(ARGS)>1 else '%s-layout.json'%TILESET
    SEED_ARG=ARGS[2] if len(ARGS)>2 else None
else:
    LAYOUT=ARGS[0] if len(ARGS)>0 else 'PrologueMap'
    OUT_HTML=ARGS[1] if len(ARGS)>1 else 'editor.html'
    DOWNLOAD=ARGS[2] if len(ARGS)>2 else 'prologue-layout.json'
    SEED_ARG=ARGS[3] if len(ARGS)>3 else None

def _asset_names(dec):
    import re
    names=[]
    with open(os.path.join(dec,'data/data_8B363C.s')) as f:
        for line in f:
            mo=re.match(r'\s*\.word\s+(\w+)',line)
            if mo: names.append(mo.group(1))
    return names


def _gbagfx(dec):
    """Return the decomp converter, building that standalone host tool if absent."""
    import subprocess
    tool_dir=os.path.join(dec,'tools/gbagfx')
    executable=os.path.join(tool_dir,'gbagfx')
    if not os.path.exists(executable):
        subprocess.run(['make','-C',tool_dir],check=True)
    return executable


def _walkable_terrains(dec):
    """Terrain ids a foot unit can ENTER, read from the engine's OWN move-cost table
    (data_terrains.s, CommonT1Normal). Cost 0 and 255 are the impassable sentinels;
    1..254 is enterable (plains=1, forest=2, ...). Drives the editor's green/red
    passability overlay so it's correct for ANY tileset -- the old hand-list was snow-
    flavored and wrongly flagged the cave floor (0x2a=SHIP_FLAT, cost 1) as impassable."""
    import re
    try:
        src=open(os.path.join(dec,'src/data_terrains.s'),errors='ignore').read()
        m=re.search(r'TerrainTable_MovCost_CommonT1Normal:\s*(.*?)(?=\n\w+:|\n\s*\.global|\Z)',src,re.S)
        vals=[]
        for tok in re.findall(r'\.byte\s+([^\n]+)',m.group(1)):
            for v in tok.split(','):
                v=v.strip()
                if v: vals.append(int(v,0)&0xFF)
        return [i for i,c in enumerate(vals) if 0<c<255]
    except Exception:
        sys.stderr.write('WARN: could not read move-cost table; using the legacy walk list\n')
        return [0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x0a,0x0b,0x0c,0x0d,0x0e,0x13,0x17,0x1f]


def _render_vanilla_layout(dec, layout):
    """Render a vanilla FE8 map layout (e.g. Ch3Map) as a PIL image, using ITS OWN
    tileset. gChapterDataAssetTable (data_8B363C.s) groups each tileset's ObjectType/
    MapPalette/TileConfiguration right before the layouts that ride it, so resolve the
    three by scanning BACKWARD from the layout for the nearest of each -- Ch3Map/Ch4Map
    ride tileset 2, not 1, so hardcoding ObjectType1 would render garbage. The raw
    .4bpp/.gbapal are build-only artifacts, so build any missing one with the decomp's
    own gbagfx (authoritative palette). Returns (image, w, h)."""
    import subprocess
    names=_asset_names(dec); i=names.index(layout)
    obj=pal=cfg=None
    for n in reversed(names[:i]):
        if cfg is None and n.startswith('TileConfiguration'): cfg=n
        elif pal is None and n.startswith('MapPalette'): pal=n
        elif obj is None and n.startswith('ObjectType'): obj=n
        if obj and pal and cfg: break
    if not (obj and pal and cfg):
        raise ValueError('could not resolve tileset assets for %r'%layout)
    g=os.path.join(dec,'graphics/map')
    def ensure(src,dst):
        if not os.path.exists(dst):
            subprocess.run([_gbagfx(dec),src,dst],check=True)
    ensure(os.path.join(g,obj+'.png'), os.path.join(g,obj+'.4bpp'))
    ensure(os.path.join(g,pal+'.pal'), os.path.join(g,pal+'.gbapal'))
    ts=Tileset(os.path.join(g,obj+'.4bpp'),os.path.join(g,pal+'.gbapal'),os.path.join(g,cfg+'.bin'))
    w,h,cells,_=vanilla_layout_data(dec,layout)
    img=Image.new('RGB',(w*16,h*16))
    for j,m in enumerate(cells): img.paste(ts.metatile_image(m),((j%w)*16,(j//w)*16))
    return img,w,h


win=_tileset_from_dir(os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps/tilesets',TILESET))
RETILE_MODE='custom' if BLANK else 'vanilla'
EXPORT_META={'retile_mode':RETILE_MODE}
if not BLANK:
    EXPORT_META['vanilla_layout']=LAYOUT
PROTECTED_TARGETS={}
if BLANK:
    # Custom canvas on a vendored tileset (#40): no vanilla layout to derive from.
    W,H=(int(v) for v in BLANK.lower().split('x'))
    FILL=int(FLAGS.get('--fill','0'))
    grid=[FILL]*(W*H)
else:
    W,H,cells,source_terrain=vanilla_layout_data(DEC,LAYOUT)

    # current final grid (base iron-out + remap + manual)  -> editor starting point
    def divergent(m): return win.terrain(m)!=source_terrain[m]
    modec=collections.defaultdict(collections.Counter)
    for m in cells:
        if not divergent(m): modec[source_terrain[m]][m]+=1
    MODE={t:c.most_common(1)[0][0] for t,c in modec.items()}
    FB={0x01:6,0x0c:192,0x10:568,0x12:418,0x13:2}
    resolved=[0]*(W*H)
    for y in range(H):
        for x in range(W):
            m=cells[y*W+x]
            if not divergent(m): resolved[y*W+x]=m; continue
            vt=source_terrain[m]; nb=collections.Counter()
            for dy in(-1,0,1):
                for dx in(-1,0,1):
                    if dx==0 and dy==0: continue
                    nx,ny=x+dx,y+dy
                    if 0<=nx<W and 0<=ny<H:
                        nm=cells[ny*W+nx]
                        if not divergent(nm) and source_terrain[nm]==vt: nb[nm]+=1
            resolved[y*W+x]=nb.most_common(1)[0][0] if nb else MODE.get(vt,FB.get(vt,m))
    # Learned reskin: Nicolas's hand-retiles (reskin-learned.json) override the naive auto-reskin
    # for any vanilla metatile he's already taught, so each new chapter inherits his conventions
    # (villages, mountains, forests...) as the starting point instead of the smeared default.
    # Its target indices are metatiles in ONE tileset (the `tileset` stamp, snowy-bern) -- applying
    # them onto a different --tileset would map to unrelated cave/etc art, so gate on a match.
    _learned_path=os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps/reskin-learned.json')
    _learned_json=json.load(open(_learned_path)) if os.path.exists(_learned_path) else {}
    _learned=_learned_json.get('map',{}) if _learned_json.get('tileset','snowy-bern')==TILESET else {}
    for i in range(W*H):
        w=_learned.get(str(cells[i]))
        if w is not None: resolved[i]=w
    if TILESET=='snowy-bern':
        try:
            PROTECTED_TARGETS=preserved_terrain_targets(
                cells,source_terrain,win,_learned_json,W)
        except ValueError as error:
            sys.exit('ERROR: %s'%error)
        for cell,target in PROTECTED_TARGETS.items():
            resolved[cell]=target
    # prologue-era hand overrides apply only to the original PrologueMap session
    _isproto = LAYOUT=='PrologueMap'
    scratch=os.path.join('/tmp', 'manchego-stars-review')
    remap={int(k):v for k,v in json.load(open(os.path.join(scratch,'_remap.json'))).items()} if _isproto and os.path.exists(os.path.join(scratch,'_remap.json')) else {}
    manual=json.load(open(os.path.join(scratch,'_manual.json'))) if _isproto and os.path.exists(os.path.join(scratch,'_manual.json')) else {}
    def lbl(i): x,y=i%W,i//W; return '%s%d'%(chr(ord('A')+x),y+1)
    grid=[]
    for i in range(W*H):
        t=manual.get(lbl(i), resolved[i]); grid.append(remap.get(t,t))

# Optional trailing arg: seed the editable grid from an existing compiled .mar so Nicolas
# continues editing the CURRENT chapter map (gate, prior hand-retiles) instead of a
# fresh reskin/blank canvas. The .mar stores metatile<<5 (see compile_layout);
# its sibling .json carries the dims, which must match the chosen canvas.
SEED_MAR=SEED_ARG
if SEED_MAR:
    SEED_MAR=os.path.expanduser(SEED_MAR)
    seed=open(SEED_MAR,'rb').read()
    sj=json.load(open(os.path.splitext(SEED_MAR)[0]+'.json'))
    if (sj['width'],sj['height'])!=(W,H):
        sys.exit('ERROR: seed .mar is %dx%d but layout %s is %dx%d'
                 %(sj['width'],sj['height'],LAYOUT,W,H))
    if sj.get('tileset','snowy-bern')!=TILESET:
        sys.exit('ERROR: seed .mar was painted on tileset %r but this canvas is %r '
                 '-- its metatile indices would reinterpret as the wrong art/terrain'
                 %(sj.get('tileset','snowy-bern'),TILESET))
    grid=[struct.unpack_from('<H',seed,i*2)[0]>>5 for i in range(W*H)]
    print('seeded editable grid from',SEED_MAR)

forest_errors=[]
for cell,expected in PROTECTED_TARGETS.items():
    if grid[cell]!=expected:
        forest_errors.append('forest sequence at (%d, %d) is tile %d; expected tile %d'
                             %(cell%W,cell//W,grid[cell],expected))
if forest_errors:
    sys.exit('ERROR: %s'%'; '.join(forest_errors))

# atlas image: 32 cols x 32 rows of 16px tiles (clean, contiguous)
ACOLS=32; AROWS=32
atlas=Image.new('RGB',(ACOLS*16, AROWS*16))
for m in range(1024):
    atlas.paste(win.metatile_image(m), ((m%ACOLS)*16,(m//ACOLS)*16))
buf=io.BytesIO(); atlas.save(buf,'PNG'); ATLAS=base64.b64encode(buf.getvalue()).decode()

# Eyedropper source (#40, ch03+): if this tileset ships a Tiled demo map (Cynon's
# hand-painted mineshaft for cave-interior), render it in the right pane so Nicolas grabs
# tiles straight off finished art -- click a cell, that metatile becomes the brush -- instead
# of hunting the raw metatile bank. Tilesets with no demo map (snowy-bern's reskin flow) keep
# the palette. Both draw from the same `win` atlas, so a demo cell and a painted cell match.
from map_tileset_tool import tmx_grid
_demo_tmx=os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps/tilesets',TILESET,'test-map.tmx')
if os.path.exists(_demo_tmx):
    _dg=tmx_grid(_demo_tmx); DH_DEMO=len(_dg); DW_DEMO=len(_dg[0]); DEMO=[m for row in _dg for m in row]
    print('eyedropper demo map: %s (%dx%d)'%(os.path.basename(_demo_tmx),DW_DEMO,DH_DEMO))
else:
    DEMO=[]; DW_DEMO=0; DH_DEMO=0

# Reference pane. Custom-canvas mode embeds --ref (any image, e.g. the flattened
# book-map blockout) stretched to the canvas so the yellow hover-highlight lines up;
# without --ref it stays a dark placeholder. Reskin mode renders the ORIGINAL FE8
# layout in its native tileset for side-by-side comparison while painting. The raw
# .4bpp/.gbapal are build-only artifacts often absent in a fresh tree, so build them
# on demand with the decomp's OWN gbagfx (authoritative; a hand-rolled PNG/JASC
# decode gets the palette wrong), then render via the standard path.
if BLANK:
    REF_IMG=FLAGS.get('--ref')
    if VANILLA_REF:
        # Render the vanilla layout this canvas repaints (e.g. Ch3Map = vanilla Borgo) so
        # Nicolas matches the original geometry cell-for-cell while painting. Resize to the
        # canvas only if dims differ (a faithful repaint keeps them equal, so hover aligns).
        vref,_vw,_vh=_render_vanilla_layout(DEC,VANILLA_REF)
        if (_vw,_vh)!=(W,H): vref=vref.resize((W*16,H*16),Image.NEAREST)
        print('vanilla reference: %s (%dx%d)'%(VANILLA_REF,_vw,_vh))
    elif REF_IMG:
        vref=Image.open(os.path.expanduser(REF_IMG)).convert('RGB').resize(
            (W*16,H*16),Image.LANCZOS)
    else:
        vref=Image.new('RGB',(W*16,H*16),(28,30,36))
else:
    import subprocess
    def _ensure_built(src, dst):
        if not os.path.exists(dst):
            subprocess.run([_gbagfx(DEC), src, dst], check=True)
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
# Non-winter tilesets (--tileset=cave-interior, ...): strip the snow flavor from the
# shared terrain ids so the hover/palette labels don't describe a mine in snowfield
# terms. Terrain SEMANTICS are the tileset's own terrain bytes either way.
if TILESET!='snowy-bern':
    TNAME.update({0x01:'Ground',0x0c:'Cover (forest-type)',0x10:'River / stream',
                  0x11:'Rock / rough',0x15:'Water (impass.)',0x36:'Deep water'})

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
 <div class="bar" style="margin-top:8px"><b>How to use:</b> 1) click a tile on the <b>demo map</b> (right) to grab it as your brush &nbsp; 2) click/drag on the map to paint &nbsp; 3) <b>Export</b> → a <i>__DOWNLOAD__</i> downloads &nbsp; 4) tell Claude "exported" and it compiles + renders.</div>
 <textarea id="out" style="width:680px;height:70px;display:none;background:#111;color:#6f6"></textarea>
</div>
<div id="right">
 <div id="demoWrap" style="display:none">
  <div class="bar"><b>MINE DEMO MAP</b> — click any tile to grab it as your <b>brush</b> (eyedropper). &nbsp;<span class="hint">yellow = current brush · cyan = hover</span></div>
  <div class="hint" id="demoReadout" style="margin-bottom:6px">hover the demo map…</div>
  <canvas id="demo"></canvas>
 </div>
 <div id="palWrap" style="display:none">
  <div class="bar"><b>TILE PALETTE</b> — click to pick brush. filter:
   <select id="filter"></select> &nbsp;<span class="hint">green=walkable border on map</span></div>
  <canvas id="pal"></canvas>
 </div>
</div>
<script>
const W=__W__,H=__H__,T=16,ACOLS=__ACOLS__;
let GRID=__GRID__; const TERR=__TERR__,PAL=__PAL__,TNAME=__TNAME__;
const WALK=new Set(__WALK__);  // enterable terrains, from the engine's move-cost table
const atlas=new Image(); atlas.src="data:image/png;base64,__ATLAS__";
const vanref=new Image(); vanref.src="data:image/png;base64,__VANREF__";
const MC=48, PC=34, PCOLS=16, DC=22;
const DEMO=__DEMO__, DW=__DW__, DH=__DH__;
const EXPORT_META=__EXPORT_META__;
const map=document.getElementById('map'), mx=map.getContext('2d');
const ref=document.getElementById('ref'), rx=ref.getContext('2d');
const pal=document.getElementById('pal'), px=pal.getContext('2d');
const demo=document.getElementById('demo'), dcx=demo.getContext('2d');
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
  if(showGrid){mx.strokeStyle=WALK.has(TERR[m])?'#28d228':'#eb2d2d'; mx.lineWidth=1;
   mx.strokeRect(x+0.5,y+0.5,MC-1,MC-1);}}
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
let lastDemoHover=-1;
function drawDemo(hl){
 if(hl===undefined)hl=lastDemoHover; lastDemoHover=hl;
 demo.width=DW*DC; demo.height=DH*DC; dcx.imageSmoothingEnabled=false;
 for(let i=0;i<DEMO.length;i++){const m=DEMO[i],x=(i%DW)*DC,y=Math.floor(i/DW)*DC;
  const[s,t]=tileSrc(m); dcx.drawImage(atlas,s,t,T,T,x,y,DC,DC);
  if(m===brush){dcx.strokeStyle='#ffd84d';dcx.lineWidth=2;dcx.strokeRect(x+1,y+1,DC-2,DC-2);}}
 if(hl>=0){const x=(hl%DW)*DC,y=Math.floor(hl/DW)*DC;dcx.strokeStyle='#4dd2ff';dcx.lineWidth=2;dcx.strokeRect(x+1,y+1,DC-2,DC-2);}
}
function demoCellAt(e){const r=demo.getBoundingClientRect();const x=Math.floor((e.clientX-r.left)/DC),y=Math.floor((e.clientY-r.top)/DC);return(x>=0&&x<DW&&y>=0&&y<DH)?y*DW+x:-1;}
if(DEMO.length){
 demo.onmousedown=e=>{const i=demoCellAt(e);if(i>=0)setBrush(DEMO[i]);};
 demo.onmousemove=e=>{const i=demoCellAt(e);if(i>=0){const m=DEMO[i];
  document.getElementById('demoReadout').textContent='tile i'+m+'  ('+(TNAME[TERR[m]]||('0x'+TERR[m].toString(16)))+')  — click to grab';drawDemo(i);}};
 demo.onmouseleave=()=>drawDemo(-1);
}
function refreshBrushPanel(){if(DEMO.length)drawDemo();else drawPal();}
function setBrush(m){brush=m;document.getElementById('brush').textContent='brush = tile i'+m+' ('+(TNAME[TERR[m]]||TERR[m])+')';refreshBrushPanel();}
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
 const js=JSON.stringify({...EXPORT_META,tileset:'__TILESET__',width:W,height:H,grid:GRID});
 const ta=document.getElementById('out');ta.style.display='block';ta.value=js;
 const b=new Blob([js],{type:'application/json'});const a=document.createElement('a');
 a.href=URL.createObjectURL(b);a.download='__DOWNLOAD__';a.click();
};
atlas.onload=()=>{drawMap();
 if(DEMO.length){document.getElementById('demoWrap').style.display='block';drawDemo(-1);}
 else{document.getElementById('palWrap').style.display='block';buildFilter();drawPal();}
 setBrush(brush);drawRef(-1);};
vanref.onload=()=>drawRef(-1);
</script></body></html>'''

out=(HTML.replace('__W__',str(W)).replace('__H__',str(H)).replace('__ACOLS__',str(ACOLS))
     .replace('__GRID__',json.dumps(grid)).replace('__TERR__',json.dumps(TERR))
     .replace('__PAL__',json.dumps(PAL)).replace('__TNAME__',json.dumps({str(k):v for k,v in TNAME.items()}))
     .replace('__ATLAS__',ATLAS).replace('__VANREF__',VANREF)
     .replace('__DEMO__',json.dumps(DEMO)).replace('__DW__',str(DW_DEMO)).replace('__DH__',str(DH_DEMO))
     .replace('__EXPORT_META__',json.dumps(EXPORT_META))
     .replace('__WALK__',json.dumps(_walkable_terrains(DEC)))
     .replace('__DOWNLOAD__',DOWNLOAD).replace('__TITLE__',LAYOUT)
     .replace('__TILESET__',TILESET))
# TNAME keys must be numeric in JS object -> emit as numbers
out=out.replace(json.dumps({str(k):v for k,v in TNAME.items()}),
                '{'+','.join('%d:%s'%(k,json.dumps(v)) for k,v in TNAME.items())+'}')
def review_output(value):
    # Absolute paths pass through (write beside a caller-chosen editor location);
    # relative names land under the shared review/ scratch dir.
    return value if os.path.isabs(value) else os.path.join(ROOT,'review',value)


path=review_output(OUT_HTML)
os.makedirs(os.path.dirname(path),exist_ok=True)
open(path,'w').write(out)
print('wrote',path,'(%d KB)'%(len(out)//1024))

# Dump the auto-reskinned starting grid as an importable layout JSON (so the faithful
# winter reskin can be compiled/rendered immediately, before any hand-painting), and
# render a PNG preview of it so the starting point is visible without opening the editor.
start_json=review_output(DOWNLOAD)
os.makedirs(os.path.dirname(start_json),exist_ok=True)
start_payload=dict(EXPORT_META,tileset=TILESET,width=W,height=H,grid=grid)
json.dump(start_payload,open(start_json,'w'))
print('wrote starting layout',start_json)
png=os.path.join(os.path.dirname(path),os.path.splitext(os.path.basename(path))[0]+'-start.png')
render_grid(win,[grid[r*W:(r+1)*W] for r in range(H)],png,zoom=4)
print('rendered start preview',png)
