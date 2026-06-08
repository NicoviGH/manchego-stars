#!/usr/bin/env python3
"""Generate a self-contained HTML tile-map editor for the Prologue (and reusable for any
chapter): embeds the winter metatile atlas + current layout + terrain data. Nicolas paints
in-browser and exports a layout JSON, which we compile_layout() directly."""
import sys, os, struct, collections, json, io, base64
DEC='/Users/Yonick/Projects/manchego-stars/fireemblem8u'
ROOT='/Users/Yonick/Projects/manchego-stars'
sys.path.insert(0, os.path.join(ROOT,'tools'))
from map_tileset_tool import _tileset_from_dir, Tileset
from PIL import Image

win=_tileset_from_dir(os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps/tilesets/snowy-bern'))
van=Tileset(os.path.join(DEC,'graphics/map/ObjectType1.4bpp'),
            os.path.join(DEC,'graphics/map/MapPalette1.gbapal'),
            os.path.join(DEC,'graphics/map/TileConfiguration1.bin'))
lay=open(os.path.join(DEC,'graphics/map/layout/PrologueMap.bin'),'rb').read()
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
remap={int(k):v for k,v in json.load(open(os.path.join(ROOT,'map-review/_remap.json'))).items()} if os.path.exists(os.path.join(ROOT,'map-review/_remap.json')) else {}
manual=json.load(open(os.path.join(ROOT,'map-review/_manual.json'))) if os.path.exists(os.path.join(ROOT,'map-review/_manual.json')) else {}
def lbl(i): x,y=i%W,i//W; return '%s%d'%(chr(ord('A')+x),y+1)
grid=[]
for i in range(W*H):
    t=manual.get(lbl(i), resolved[i]); grid.append(remap.get(t,t))

# atlas image: 32 cols x 32 rows of 16px tiles (clean, contiguous)
ACOLS=32; AROWS=32
atlas=Image.new('RGB',(ACOLS*16, AROWS*16))
for m in range(1024):
    atlas.paste(win.metatile_image(m), ((m%ACOLS)*16,(m//ACOLS)*16))
buf=io.BytesIO(); atlas.save(buf,'PNG'); ATLAS=base64.b64encode(buf.getvalue()).decode()

def nonempty(m): return any(struct.unpack_from('<H',win.cfg,m*8+s*2)[0]&0x3FF for s in range(4))
TERR=[win.terrain(m) for m in range(1024)]
PAL=[m for m in range(1024) if nonempty(m)]
TNAME={0x00:'(none)',0x01:'Plains',0x02:'Road',0x05:'House',0x0a:'Fort',0x0b:'Gate',
0x0c:'Forest',0x0d:'Thicket',0x10:'River',0x11:'Mountain',0x12:'Peak',0x13:'Bridge',
0x15:'Sea',0x17:'Floor',0x19:'Fence',0x1a:'Wall',0x1e:'Door',0x25:'Ruins',0x26:'Cliff',0x3c:'Water'}

HTML=r'''<!doctype html><html><head><meta charset="utf-8"><title>Prologue Map Editor</title>
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
  <span id="brush" class="hint"></span>
 </div>
 <canvas id="map"></canvas>
 <div class="hint" id="cell">hover a cell…</div>
 <div class="bar" style="margin-top:8px"><b>How to use:</b> 1) pick a tile on the right (it becomes your brush) &nbsp; 2) click/drag on the map to paint &nbsp; 3) <b>Export</b> → a <i>prologue-layout.json</i> downloads &nbsp; 4) tell Claude "exported" and it compiles + renders.</div>
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
const MC=48, PC=34, PCOLS=16;
const map=document.getElementById('map'), mx=map.getContext('2d');
const pal=document.getElementById('pal'), px=pal.getContext('2d');
map.width=W*MC; map.height=H*MC;
let brush=PAL[0], hist=[], curFilter='all', palList=PAL.slice();

function tileSrc(m){return [(m%ACOLS)*T,(Math.floor(m/ACOLS))*T];}
function drawMap(){
 for(let i=0;i<W*H;i++){const m=GRID[i],x=(i%W)*MC,y=(Math.floor(i/W))*MC;
  const[s,t]=tileSrc(m); mx.drawImage(atlas,s,t,T,T,x,y,MC,MC);
  mx.strokeStyle=WALK.has(TERR[m])?'#28d228':'#eb2d2d'; mx.lineWidth=2;
  mx.strokeRect(x+1,y+1,MC-2,MC-2);}
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
map.onmousemove=e=>{const i=cellAt(e);if(i>=0){const x=i%W,y=Math.floor(i/W);document.getElementById('cell').textContent=String.fromCharCode(65+x)+(y+1)+'  tile i'+GRID[i]+' ('+(TNAME[TERR[GRID[i]]]||TERR[GRID[i]])+')';if(down)paintAt(i);}};
window.onmouseup=()=>down=false;
pal.onmousedown=e=>{const r=pal.getBoundingClientRect();const k=Math.floor((e.clientY-r.top)/PC)*PCOLS+Math.floor((e.clientX-r.left)/PC);if(k>=0&&k<palList.length)setBrush(palList[k]);};
document.getElementById('undo').onclick=()=>{if(hist.length){GRID=hist.pop();drawMap();}};
window.onkeydown=e=>{if(e.key==='z'){if(hist.length){GRID=hist.pop();drawMap();}}};
document.getElementById('export').onclick=()=>{
 const js=JSON.stringify({width:W,height:H,grid:GRID});
 const ta=document.getElementById('out');ta.style.display='block';ta.value=js;
 const b=new Blob([js],{type:'application/json'});const a=document.createElement('a');
 a.href=URL.createObjectURL(b);a.download='prologue-layout.json';a.click();
};
atlas.onload=()=>{drawMap();buildFilter();drawPal();setBrush(brush);};
</script></body></html>'''

out=(HTML.replace('__W__',str(W)).replace('__H__',str(H)).replace('__ACOLS__',str(ACOLS))
     .replace('__GRID__',json.dumps(grid)).replace('__TERR__',json.dumps(TERR))
     .replace('__PAL__',json.dumps(PAL)).replace('__TNAME__',json.dumps({str(k):v for k,v in TNAME.items()}))
     .replace('__ATLAS__',ATLAS))
# TNAME keys must be numeric in JS object -> emit as numbers
out=out.replace(json.dumps({str(k):v for k,v in TNAME.items()}),
                '{'+','.join('%d:%s'%(k,json.dumps(v)) for k,v in TNAME.items())+'}')
path=os.path.join(ROOT,'map-review/editor.html')
open(path,'w').write(out)
print('wrote',path,'(%d KB)'%(len(out)//1024))
