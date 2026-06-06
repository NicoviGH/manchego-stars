#!/usr/bin/env python3
"""map_sprite_editor.py -- a local, offline, in-browser pixel editor for cast sheets.

Why this exists: directing pixel edits by reading static screenshots isn't interactive
enough (issue #38 art loop). This serves a tiny single-page editor to 127.0.0.1 so the
sheet can be painted by hand against the locked cast palette, with a live animated idle
preview, and saved straight back to the indexed PNG -- exact cast indices preserved (it
is the indices, not the embedded colours, that gbagfx packs to 4bpp; see build_campaign /
decisions.md Art & Audio).

Look & feel borrows from Aseprite / LibreSprite (Nicolas's request): dark charcoal theme,
a left tool column, a checkerboard transparency canvas with zoom + pixel grid, a palette
panel, a bottom frame timeline with real-speed playback + onion skin, and a status bar.
Nothing is invented from scratch; it mirrors those editors' conventions.

The idle preview follows the FE8 decomp exactly (src/bmudisp.c sub_8026FF4 / the
GetGameClock() % 72 ladder): standing sprites animate frames 0,1,2 only, held
32 / 4 / 32 / 4 ticks (frame 0, 1, 2, 1) at 60fps -- a slow two-pose bob.

It is deliberately stdlib-only (http.server) -- no pip installs, no framework, no network
calls, nothing leaves the machine. Sheet-agnostic by design (frame geometry from
map_sprite_tool.sheet_info, --fw/--fh override), so the painting surface carries over to
battle-animation frames later (the anim *scripting* is a separate problem).

  usage: map_sprite_editor.py <sheet.png> <cast_palette.png>
           --donor <ClassName> [--reference donor.png] [--port N] [--no-browser]

The frame size is read from the decomp wait table for --donor (e.g. Cyclops -> 16x32),
never guessed from the PNG. --reference can stand in for --donor (its name is parsed).

Open the printed URL. Ctrl-C to stop.
"""

import argparse
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_sprite_tool  # noqa: E402  (sheet_info + _read_palette)
from PIL import Image  # noqa: E402

# FE8 standing idle, straight from src/bmudisp.c: GetGameClock() % 72 picks frames
# 0,1,2 at the boundaries below. As (frame_index, hold_ticks); 60 ticks/sec.
IDLE_SEQ = [[0, 32], [1, 4], [2, 32], [1, 4]]
TICK_MS = 1000.0 / 60.0


class Doc:
    """The single sheet being edited + (optional) the donor reference behind it."""

    def __init__(self, sheet_path, palette_path, reference_path=None, donor=None,
                 uid=None, base_path=None, geom=None):
        self.sheet_path = sheet_path
        self.id = uid or os.path.splitext(os.path.basename(sheet_path))[0]
        self.base_path = base_path  # pristine clean-recolor snapshot, for reset
        # "finished/approved" marker (gitignored, lives by the base snapshot); Save is a
        # local checkpoint, Finish flags the sheet approved-to-commit.
        self.done_path = (base_path + '.done') if base_path else None
        # Idle frame geometry is read from the decomp wait table for the donor
        # (authoritative), never guessed -- a 16x96 sheet is ambiguous (6x16x16 vs
        # 3x16x32). MU/walk sheets pass an explicit geom=(32,32) (the fixed move-sprite
        # OBJ size; the motion script frames it, the sheet is a 15-frame 32x480 strip).
        if geom is not None:
            self.fw, self.fh = geom
            self.donor_name = donor or (os.path.basename(reference_path) if reference_path else 'MU')
        else:
            src = donor or reference_path
            if not src:
                sys.exit('ERROR: pass --donor <ClassName> (or --reference its vanilla '
                         'sheet) so the frame size can be read from the decomp, not guessed')
            self.donor_name = donor or os.path.basename(src)
            _, self.fw, self.fh = map_sprite_tool.donor_sms_geometry(src)
        im = Image.open(sheet_path)
        w, h = im.size
        if w != self.fw or h % self.fh:
            sys.exit('ERROR: %s is %dx%d but donor %s is %dx%d'
                     % (sheet_path, w, h, src, self.fw, self.fh))
        self.n = h // self.fh
        flat = map_sprite_tool._read_palette(palette_path)
        self.palette = [flat[i * 3:i * 3 + 3] for i in range(16)]
        data = list(im.getdata())
        self.frames = [data[f * self.fw * self.fh:(f + 1) * self.fw * self.fh]
                       for f in range(self.n)]
        self.reference = self._load_reference(reference_path)
        self._motion = None              # computed lazily on first /data (see get_motion)
        self._motion_src = reference_path

    def get_motion(self):
        if self._motion is None:
            self._motion = self._compute_motion(self._motion_src)
        return self._motion

    def _compute_motion(self, reference_path):
        """Per-row 2D offset (dx, dy) between every pair of frames -- so an edit can FOLLOW
        a moving pixel instead of being redone in each frame. Derived from each character's
        OWN donor (the true animation; recolouring preserves geometry), NOT hardcoded to
        any one creature: for each row, the small (dx, dy) shift that best aligns its
        silhouette band to the other frame. Vertical + horizontal, so it's not biased to
        the Cyclops's near-vertical bob -- a donor that sways/flies is measured as it is.
        Where a donor's motion is too complex for a per-row shift (independent limbs/wings),
        the fit degrades and the user verifies via the thumbnails/onion and falls back to
        per-frame. Returns motion[a][b][y] = [dx, dy]."""
        fw, fh, n = self.fw, self.fh, self.n
        src = self.frames
        if reference_path and os.path.isfile(reference_path):
            rim = Image.open(reference_path)
            rim = rim if rim.mode == 'P' else rim.convert('P')
            if rim.size == (fw, n * fh):
                d = list(rim.getdata())
                src = [d[f * fw * fh:(f + 1) * fw * fh] for f in range(n)]
        mask = [[1 if v else 0 for v in fr] for fr in src]

        def band_mismatch(a, b, y, dx, dy):
            # single-row silhouette match (cheap); enough for the per-row offset
            ty = y + dy
            if not (0 <= ty < fh):
                return fw
            ra, rb = mask[a], mask[b]
            tot = 0
            for x in range(fw):
                bx = x + dx
                bv = rb[ty * fw + bx] if 0 <= bx < fw else 0
                if ra[y * fw + x] != bv:
                    tot += 1
            return tot

        maxx, maxy = 2, 3
        motion = [[[[0, 0] for _ in range(fh)] for _ in range(n)] for _ in range(n)]
        for a in range(n):
            for b in range(n):
                if a == b:
                    continue
                for y in range(fh):
                    if not any(mask[a][y * fw:y * fw + fw]):
                        continue  # empty row -> no motion
                    best, bd = [0, 0], None
                    for dy in range(-maxy, maxy + 1):
                        for dx in range(-maxx, maxx + 1):
                            key = (band_mismatch(a, b, y, dx, dy), abs(dx) + abs(dy))
                            if bd is None or key < bd:
                                bd, best = key, [dx, dy]
                    motion[a][b][y] = best
        return motion

    def _load_reference(self, path):
        """Donor sheet as per-frame RGBA rows (its own palette, index 0 -> transparent),
        so the editor can show 'what is what' behind the recoloured work."""
        if not path:
            return None
        rim = Image.open(path).convert('P') if Image.open(path).mode != 'P' \
            else Image.open(path)
        need = self.n * self.fh
        if rim.size[0] != self.fw or rim.size[1] < need:
            print('  (reference %s is %s, sheet frame is %dx%d x %d -- skipping overlay)'
                  % (path, rim.size, self.fw, self.fh, self.n))
            return None
        if rim.size[1] > need:  # donor sheet has trailing padding (e.g. MU 488 vs 480)
            rim = rim.crop((0, 0, self.fw, need))
        rpal = rim.getpalette() or []
        rgba = []
        for px in rim.getdata():
            if px == 0:
                rgba.append([0, 0, 0, 0])
            else:
                rgba.append([rpal[px * 3], rpal[px * 3 + 1], rpal[px * 3 + 2], 255])
        per = self.fw * self.fh
        return [rgba[f * per:(f + 1) * per] for f in range(self.n)]

    def as_json(self):
        return json.dumps({
            'fw': self.fw, 'fh': self.fh, 'n': self.n, 'palette': self.palette,
            'frames': self.frames, 'path': os.path.basename(self.sheet_path),
            'id': self.id, 'idleSeq': IDLE_SEQ, 'tickMs': TICK_MS,
            'hasReference': self.reference is not None,
            'canReset': bool(self.base_path and os.path.isfile(self.base_path)),
            'done': self.is_done(),
            'motion': self.get_motion(),
        })

    def reference_json(self):
        return json.dumps({'frames': self.reference or []})

    def save(self, frames):
        if len(frames) != self.n or any(len(fr) != self.fw * self.fh for fr in frames):
            raise ValueError('frame data does not match %dx%d x %d'
                             % (self.fw, self.fh, self.n))
        self.frames = [[int(v) & 0x0F for v in fr] for fr in frames]
        flat = [v for fr in self.frames for v in fr]
        out = Image.new('P', (self.fw, self.n * self.fh))
        pal = []
        for rgb in self.palette:
            pal += list(rgb)
        out.putpalette(pal)
        out.putdata(flat)
        out.save(self.sheet_path)
        map_sprite_tool.sheet_info(self.sheet_path, (self.fw, self.fh))  # loud on drift

    def reset(self):
        """Revert the sheet to its pristine clean-recolour snapshot (discards all edits,
        saved or not)."""
        if not (self.base_path and os.path.isfile(self.base_path)):
            raise ValueError('no base snapshot for %s' % self.id)
        data = list(Image.open(self.base_path).getdata())
        per = self.fw * self.fh
        self.save([data[f * per:(f + 1) * per] for f in range(self.n)])
        self.set_done(False)

    def is_done(self):
        return bool(self.done_path and os.path.exists(self.done_path))

    def set_done(self, value):
        if not self.done_path:
            return
        if value:
            open(self.done_path, 'w').close()
        elif os.path.exists(self.done_path):
            os.remove(self.done_path)


# uid -> Doc for every editable cast member (campaign mode); single entry in file mode.
DOCS = {}
ORDER = []


def _doc(char):
    d = DOCS.get(char) or (DOCS.get(ORDER[0]) if ORDER else None)
    if d is None:
        raise KeyError('no such character %r' % char)
    return d


HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>map sprite editor</title>
<style>
  :root{--bg:#1e1f22;--panel:#2b2c30;--panel2:#33343a;--line:#15161a;--accent:#5a8dee;
        --txt:#d6d6d6;--muted:#8a8b90}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font:12px/1.4 -apple-system,system-ui,sans-serif;user-select:none;overflow:hidden}
  #app{display:grid;grid-template-columns:46px 1fr 188px;grid-template-rows:1fr 96px 24px;
    grid-template-areas:"tools canvas right" "tools timeline right" "status status status";
    height:100vh}
  /* left tool column (Aseprite-style) */
  #tools{grid-area:tools;background:var(--panel);border-right:1px solid var(--line);
    display:flex;flex-direction:column;align-items:center;padding-top:6px;gap:3px}
  .tool{width:34px;height:34px;border:1px solid transparent;border-radius:5px;
    background:var(--panel2);color:var(--txt);font-size:16px;cursor:pointer;
    display:flex;align-items:center;justify-content:center}
  .tool:hover{border-color:#555}
  .tool.on{background:var(--accent);border-color:var(--accent);color:#fff}
  .fg{width:30px;height:30px;border-radius:5px;border:2px solid #777;margin-top:8px}
  /* canvas */
  #canvasWrap{grid-area:canvas;position:relative;overflow:hidden;background:#141519}
  #stage{position:absolute;left:0;top:0;image-rendering:pixelated;cursor:crosshair}
  #canvasBar{position:absolute;top:6px;left:6px;display:flex;gap:4px;z-index:2}
  #canvasBar button,.tgl{background:rgba(40,41,46,.85);border:1px solid #444;color:var(--txt);
    border-radius:4px;padding:3px 7px;cursor:pointer;font-size:11px}
  .tgl.on{background:var(--accent);border-color:var(--accent);color:#fff}
  /* right column: preview + reference + palette */
  #right{grid-area:right;background:var(--panel);border-left:1px solid var(--line);
    display:flex;flex-direction:column;overflow:auto}
  #right select{width:100%;background:var(--panel2);color:var(--txt);border:1px solid #555;
    border-radius:4px;padding:4px}
  .sect{padding:8px;border-bottom:1px solid var(--line)}
  .sect h4{margin:0 0 6px;font-size:10px;letter-spacing:.08em;text-transform:uppercase;
    color:var(--muted);font-weight:600;display:flex;justify-content:space-between}
  #prevCv,#refCv{image-rendering:pixelated;background:
    repeating-conic-gradient(#aab0b8 0 25%,#c6ccd4 0 50%) 0/16px 16px;border:1px solid #444;
    display:block;margin:auto}
  #pal{display:grid;grid-template-columns:repeat(4,1fr);gap:3px}
  .sw{aspect-ratio:1;border:2px solid #3a3b40;border-radius:3px;cursor:pointer;
    display:flex;align-items:center;justify-content:center;font-size:9px;color:#fff;
    text-shadow:0 0 2px #000,0 0 2px #000}
  .sw.sel{border-color:#fff;box-shadow:0 0 0 2px var(--accent)}
  /* timeline */
  #timeline{grid-area:timeline;background:var(--panel);border-top:1px solid var(--line);
    display:flex;align-items:center;gap:8px;padding:0 8px;overflow-x:auto}
  .pbtn{background:var(--panel2);border:1px solid #555;color:var(--txt);border-radius:5px;
    width:30px;height:30px;cursor:pointer;font-size:14px}
  .pbtn.on{background:var(--accent);border-color:var(--accent);color:#fff}
  .frames{display:flex;gap:6px}
  .fcell{display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer}
  .fcell canvas{image-rendering:pixelated;background:
    repeating-conic-gradient(#aab0b8 0 25%,#c6ccd4 0 50%) 0/10px 10px;border:2px solid #3a3b40;
    border-radius:3px}
  .fcell.sel canvas{border-color:var(--accent)}
  .fcell .lbl{font-size:9px;color:var(--muted)}
  .fcell.idle .lbl{color:#7ac77a}
  /* status */
  #status{grid-area:status;background:var(--line);display:flex;align-items:center;gap:16px;
    padding:0 12px;font-size:11px;color:var(--muted)}
  #status b{color:var(--txt)} #saveStat{margin-left:auto}
  button.save{background:#3a6db5;border:1px solid #3a6db5;color:#fff;border-radius:5px;
    padding:4px 10px;cursor:pointer;font-weight:600;margin-right:4px}
  button.finish{background:#2a9d54;border:1px solid #2a9d54;color:#fff;border-radius:5px;
    padding:4px 10px;cursor:pointer;font-weight:600}
  button.finish.done{background:#1d6b3a;border-color:#7ac77a}
  button.ub{background:var(--panel2);border:1px solid #555;color:var(--txt);border-radius:5px;
    padding:4px 8px;cursor:pointer;margin-right:4px}
  button.ub:hover:not(:disabled){background:#41424c}
  button.ub:disabled{opacity:.4;cursor:default}
</style></head><body>
<div id="app">
  <div id="tools">
    <div class="tool on" data-tool="pencil" title="Pencil (B) — paint pixels with the selected palette colour. Drag to draw a line.">✏️</div>
    <div class="tool" data-tool="eraser" title="Eraser (E) — paint index 0 (transparent), clearing pixels back to see-through.">🧽</div>
    <div class="tool" data-tool="bucket" title="Fill (G) — flood-fill the connected same-colour area under the cursor with the selected colour.">🪣</div>
    <div class="tool" data-tool="pick" title="Eyedropper (I, or Alt-click any tool) — pick up the colour under the cursor as the active colour.">💧</div>
    <div class="tool" data-tool="pan" title="Pan (H, or drag with middle mouse) — slide the canvas around without painting.">✋</div>
    <div class="fg" id="fgsw" title="Active colour — the palette index the pencil/fill paints with. Click a palette swatch to change it."></div>
  </div>

  <div id="canvasWrap">
    <canvas id="stage"></canvas>
    <div id="canvasBar">
      <button id="zoomOut" title="Zoom out (or Ctrl/⌘ + scroll down)">−</button>
      <button id="zoomIn" title="Zoom in (or Ctrl/⌘ + scroll up)">+</button>
      <button id="zoomFit" title="Fit the sprite to the window">fit</button>
      <span class="tgl on" id="gridTgl" title="Pixel grid + row-letter / column-number labels on the canvas. Display only.">grid</span>
      <span class="tgl" id="onionTgl" title="Onion skin — show the neighbouring frames faintly behind this one (previous = red, next = blue) so edits line up across the animation. Display only; never saved.">onion</span>
      <span class="tgl" id="refTgl" title="Reference underlay — show the original vanilla donor sprite faintly behind your work, like tracing paper, so you can tell what each area used to be. Display only; never saved.">ref</span>
      <span class="tgl" id="donorTgl" title="Donor (original colours) — show the unedited vanilla Fire Emblem donor sprite at full strength over the canvas, in its real colours, for an A/B compare. Toggle off to keep painting. Display only; never saved.">donor</span>
      <span class="tgl" id="motionTgl" title="Motion map — outline the pixels that differ between frames (the parts that move in the bob). No outline = identical in every frame, so 'all frames' edits it safely; outlined = it moves, so it may need per-frame care. Display only.">motion</span>
      <span class="tgl" id="allTgl" title="All frames — apply every edit (pencil / eraser / fill) to the same pixel in ALL frames at once. Best for static (un-outlined) pixels; moving pixels will drift. Mutually exclusive with follow.">all frames</span>
      <span class="tgl" id="followTgl" title="Follow motion — apply edits to ALL frames, but offset so they track each pixel's movement (measured per-row from this character's own donor animation). Edit once, it rides the bob. Verify via the thumbnails / onion; undo if a complex motion places it wrong. Mutually exclusive with all-frames.">follow</span>
    </div>
  </div>

  <div id="right">
    <div class="sect"><h4>Character</h4>
      <select id="charSel" title="Pick which cast member to edit — each loads its own sheet, donor reference, and motion."></select>
      <div class="seg" id="modeSeg" style="display:flex;gap:4px;margin-top:6px">
        <button data-mode="idle" class="on" style="flex:1" title="Edit the idle (standing) sheet.">Idle</button>
        <button data-mode="walk" style="flex:1" title="Edit the walk / hover (MU) sheet — 32×32, 15 frames.">Walk</button>
      </div>
      <button id="resetBtn" class="ub" style="width:100%;margin-top:6px"
        title="Revert THIS sheet (idle or walk) to its clean recolour, discarding all edits.">↺ Reset to clean recolor</button></div>
    <div class="sect"><h4>Preview <span id="bgCycle" style="cursor:pointer"
        title="Click to cycle the preview background (grass / snow / grey / black) to check contrast on different map terrain.">grass ▸</span></h4>
      <canvas id="prevCv" title="Live idle animation at the real FE8 cadence (frames 0,1,2 held 533/67/533/67 ms)."></canvas></div>
    <div class="sect" id="refSect" style="display:none"><h4>Reference (donor)</h4>
      <canvas id="refCv" title="The original vanilla donor sprite for this frame, full colour — a reference for what each area was before recolouring."></canvas></div>
    <div class="sect"><h4>Palette</h4><div id="pal"
        title="The 16 locked cast-palette colours. Click one to make it the active painting colour. ∅ (index 0) is transparent."></div></div>
  </div>

  <div id="timeline">
    <button class="pbtn on" id="play" title="Play / pause the idle preview (top-right). Editing always works regardless.">⏸</button>
    <div class="frames" id="frames"
      title="Animation frames. Click a thumbnail to edit that frame. Frames tagged ·idle are the ones the engine animates for the standing pose."></div>
  </div>

  <div id="status">
    <span id="stCur">—</span><span id="stZoom"></span><span id="stFrame"></span>
    <span id="stSize"></span>
    <span id="saveStat">
      <button class="ub" id="undoBtn" disabled title="Undo (Ctrl/⌘+Z)">↶ undo</button>
      <button class="ub" id="redoBtn" disabled title="Redo (Ctrl/⌘+Shift+Z or Ctrl/⌘+Y)">↷ redo</button>
      <button class="save" id="save"
      title="Save a local work-in-progress checkpoint to <id>.png (Ctrl/⌘+S). NOT committed.">💾 Save</button>
      <button class="finish" id="finishBtn"
      title="Mark this character DONE — saves and flags it approved-to-commit (Claude commits finished characters after a build check). Click again to un-finish.">✓ Finish</button></span>
  </div>
</div>
<script>
let S=null, REF=null, frame=0, tool='pencil', active=6, zoom=12;
let origin={x:40,y:30}, showGrid=true, onion=false, showRef=false, showDonor=false, showMotion=false;
let painting=false, panning=false, panStart=null, playing=true, allFrames=false, followMotion=false;
let MOTION=null, CUR=null, MODE='idle', dirty=false;
const docId=()=> MODE==='walk' ? CUR+':mu' : CUR;
// switch sheets WITHOUT losing unsaved work: auto-save the current sheet first
async function switchTo(uid, mode){
  if(dirty){await save();}
  await loadChar(uid, mode);
}
let undo=[], redo=[], playT=0, playStart=0;
const BGS=[['grass',[104,152,56]],['snow',[224,232,240]],['grey',[96,96,96]],['black',[20,20,20]]];
let bgIdx=0;
const $=id=>document.getElementById(id);
const css=i=>{const c=S.palette[i];return `rgb(${c[0]},${c[1]},${c[2]})`;};
const lum=i=>{const c=S.palette[i];return c[0]+c[1]+c[2];};
const rowLabel=i=> i<26?String.fromCharCode(65+i):String.fromCharCode(97+i-26);

let CHARS=[];
async function buildCharOptions(){
  CHARS=(await (await fetch('chars')).json()).chars;
  const sel=$('charSel'); const keep=sel.value; sel.innerHTML='';
  CHARS.forEach(c=>{const o=document.createElement('option');
    const mk=(c.idleDone?'✓':'')+(c.walkDone?'✓':''); o.value=c.id;
    o.textContent=(mk?mk+' ':'')+c.id+(c.donor?(' ('+c.donor+')'):''); sel.appendChild(o);});
  if(keep)sel.value=keep;
  return CHARS;
}
function curChar(){return CHARS.find(c=>c.id===CUR)||{};}
function syncModeSeg(){const c=curChar();
  [...$('modeSeg').children].forEach(btn=>{const m=btn.dataset.mode;
    const done = m==='idle'?c.idleDone:c.walkDone;
    btn.classList.toggle('on', m===MODE);
    btn.disabled = (m==='walk' && !c.hasWalk);
    btn.textContent = (m==='idle'?'Idle':'Walk')+(done?' ✓':'');});}
async function init(){
  const chars=await buildCharOptions();
  $('charSel').onchange=()=>switchTo($('charSel').value, MODE);
  $('modeSeg').addEventListener('click',ev=>{const b=ev.target.closest('button');
    if(!b||b.disabled||b.dataset.mode===MODE)return; switchTo(CUR, b.dataset.mode);});
  await loadChar(chars[0].id, 'idle');
  requestAnimationFrame(loop);
}
function updateDoneUI(){const b=$('finishBtn');
  b.textContent = S.done ? '✓ Finished' : '✓ Finish';
  b.classList.toggle('done', !!S.done);}
async function loadChar(uid, mode){
  CUR=uid; MODE=mode||'idle'; $('charSel').value=uid;
  const id=docId();
  S=await (await fetch('data?char='+encodeURIComponent(id))).json();
  MOTION=S.motion||null;
  REF = S.hasReference ? (await (await fetch('reference?char='+encodeURIComponent(id))).json()).frames : null;
  undo=[]; redo=[]; syncUndoBtns();
  $('stSize').textContent=`${S.fw}×${S.fh}`;
  $('refSect').style.display = REF ? '' : 'none';
  $('resetBtn').disabled = !S.canReset;
  if(!MOTION&&followMotion){followMotion=false;} syncModeBtns();
  updateDoneUI(); syncModeSeg();
  buildPalette(); buildFrames(); fit(); selectFrame(0); setFg(active||6);
  dirty=false; $('save').textContent='💾 Save';   // fresh load is clean
}

/* ---- palette ---- */
function buildPalette(){
  const p=$('pal'); p.innerHTML='';
  for(let i=0;i<16;i++){
    const d=document.createElement('div'); d.className='sw'+(i===active?' sel':''); d.dataset.i=i;
    if(i===0){d.style.background='repeating-conic-gradient(#555 0 25%,#333 0 50%) 0/10px 10px';
      d.textContent='∅'; d.title='index 0 — transparent';}
    else{d.style.background=css(i); d.style.color=lum(i)>360?'#000':'#fff'; d.textContent=i;
      d.title='index '+i;}
    d.onclick=()=>setFg(i);
    p.appendChild(d);
  }
}
function setFg(i){active=i; [...$('pal').children].forEach(s=>s.classList.toggle('sel',+s.dataset.i===i));
  const f=$('fgsw'); if(i===0){f.style.background='repeating-conic-gradient(#555 0 25%,#333 0 50%) 0/8px 8px';}
  else f.style.background=css(i);}

/* ---- timeline ---- */
function buildFrames(){
  const f=$('frames'); f.innerHTML='';
  const idleFrames=new Set(S.idleSeq.map(s=>s[0]));
  for(let i=0;i<S.n;i++){
    const cell=document.createElement('div');
    cell.className='fcell'+(i===frame?' sel':'')+(idleFrames.has(i)?' idle':''); cell.dataset.f=i;
    const c=document.createElement('canvas'); c.width=S.fw*3; c.height=S.fh*3;
    drawFrameInto(c.getContext('2d'),i,3,null);
    const lbl=document.createElement('div'); lbl.className='lbl';
    lbl.textContent=i+(idleFrames.has(i)?'·idle':'');
    cell.appendChild(c); cell.appendChild(lbl);
    cell.title='Frame '+i+(idleFrames.has(i)?' — animated in the idle bob':' — not used by the idle')+'. Click to edit it.';
    cell.onclick=()=>selectFrame(i);
    f.appendChild(cell);
  }
}
function selectFrame(i){frame=i; [...$('frames').children].forEach(c=>c.classList.toggle('sel',+c.dataset.f===i));
  $('stFrame').textContent='frame '+i+'/'+(S.n-1); drawStage(); drawRef();}

/* ---- core draws ---- */
function drawFrameInto(ctx,f,cell,bg){      // flat sprite into a small ctx (thumbnails)
  ctx.clearRect(0,0,S.fw*cell,S.fh*cell);
  if(bg){ctx.fillStyle=`rgb(${bg[0]},${bg[1]},${bg[2]})`; ctx.fillRect(0,0,S.fw*cell,S.fh*cell);}
  const fr=S.frames[f];
  for(let y=0;y<S.fh;y++)for(let x=0;x<S.fw;x++){const i=fr[y*S.fw+x]; if(!i)continue;
    ctx.fillStyle=css(i); ctx.fillRect(x*cell,y*cell,cell,cell);}
}
function drawStage(){
  const cv=$('stage'), W=$('canvasWrap').clientWidth, H=$('canvasWrap').clientHeight;
  cv.width=W; cv.height=H; const ctx=cv.getContext('2d'); ctx.imageSmoothingEnabled=false;
  ctx.clearRect(0,0,W,H);
  const ox=origin.x, oy=origin.y, z=zoom;
  // checkerboard inside the sprite bounds (light, so dark outline pixels stay visible —
  // not the old near-black checker that hid them)
  for(let y=0;y<S.fh;y++)for(let x=0;x<S.fw;x++){
    ctx.fillStyle=((x+y)&1)?'#aab0b8':'#c6ccd4';
    ctx.fillRect(ox+x*z,oy+y*z,z,z);}
  // onion: prev (red) + next (blue) idle-neighbours, faint
  if(onion){
    drawGhost((frame-1+S.n)%S.n,[255,80,80]); drawGhost((frame+1)%S.n,[80,140,255]);
  }
  function drawGhost(gf,tint){const fr=S.frames[gf];ctx.globalAlpha=.25;
    for(let y=0;y<S.fh;y++)for(let x=0;x<S.fw;x++){if(!fr[y*S.fw+x])continue;
      ctx.fillStyle=`rgb(${tint[0]},${tint[1]},${tint[2]})`;ctx.fillRect(ox+x*z,oy+y*z,z,z);}
    ctx.globalAlpha=1;}
  // reference overlay (donor, faint) under the painting
  if(showRef && REF){const ref=REF[frame];ctx.globalAlpha=.35;
    for(let y=0;y<S.fh;y++)for(let x=0;x<S.fw;x++){const p=ref[y*S.fw+x];if(!p[3])continue;
      ctx.fillStyle=`rgb(${p[0]},${p[1]},${p[2]})`;ctx.fillRect(ox+x*z,oy+y*z,z,z);}
    ctx.globalAlpha=1;}
  // sprite
  const fr=S.frames[frame];
  for(let y=0;y<S.fh;y++)for(let x=0;x<S.fw;x++){const i=fr[y*S.fw+x];if(!i)continue;
    ctx.fillStyle=css(i);ctx.fillRect(ox+x*z,oy+y*z,z,z);}
  // donor (original colours) on top, full strength: an A/B "show the original" compare
  if(showDonor && REF){const ref=REF[frame];
    for(let y=0;y<S.fh;y++)for(let x=0;x<S.fw;x++){const p=ref[y*S.fw+x];if(!p[3])continue;
      ctx.fillStyle=`rgb(${p[0]},${p[1]},${p[2]})`;ctx.fillRect(ox+x*z,oy+y*z,z,z);}}
  // motion map: outline pixels that aren't identical across every frame (they move)
  if(showMotion){ctx.strokeStyle='#ffd400';ctx.lineWidth=Math.max(1,z/8);
    for(let y=0;y<S.fh;y++)for(let x=0;x<S.fw;x++){const idx=y*S.fw+x;
      const v=S.frames[0][idx];let moves=false;
      for(let f=1;f<S.n;f++)if(S.frames[f][idx]!==v){moves=true;break;}
      if(moves)ctx.strokeRect(ox+x*z+1,oy+y*z+1,z-2,z-2);}}
  // pixel grid + axis labels
  if(showGrid && z>=6){
    ctx.strokeStyle='rgba(0,0,0,.35)';ctx.lineWidth=1;ctx.beginPath();
    for(let x=0;x<=S.fw;x++){ctx.moveTo(ox+x*z+.5,oy);ctx.lineTo(ox+x*z+.5,oy+S.fh*z);}
    for(let y=0;y<=S.fh;y++){ctx.moveTo(ox,oy+y*z+.5);ctx.lineTo(ox+S.fw*z,oy+y*z+.5);}
    ctx.stroke();
    ctx.fillStyle='#888';ctx.font='9px monospace';
    if(z>=11){for(let x=0;x<S.fw;x++)ctx.fillText(x,ox+x*z+z/2-3,oy-3);
      for(let y=0;y<S.fh;y++)ctx.fillText(rowLabel(y),ox-12,oy+y*z+z/2+3);}
  }
  $('stZoom').textContent='zoom '+(z*100/8|0)+'%';
}
function drawRef(){if(!REF){return;} const c=$('refCv');const cell=Math.max(2,(168/S.fw)|0);
  c.width=S.fw*cell;c.height=S.fh*cell;const ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);
  const ref=REF[frame];for(let y=0;y<S.fh;y++)for(let x=0;x<S.fw;x++){const p=ref[y*S.fw+x];if(!p[3])continue;
    ctx.fillStyle=`rgb(${p[0]},${p[1]},${p[2]})`;ctx.fillRect(x*cell,y*cell,cell,cell);}}

/* ---- live preview (decomp idle timing) ---- */
function loop(ts){
  if(playing){const cycle=S.idleSeq.reduce((a,s)=>a+s[1],0)*S.tickMs;
    const t=((ts-playStart)%cycle)/S.tickMs; let acc=0,pf=S.idleSeq[0][0];
    for(const [fi,dur] of S.idleSeq){if(t<acc+dur){pf=fi;break;}acc+=dur;}
    drawPreview(pf);}
  requestAnimationFrame(loop);
}
function drawPreview(pf){const c=$('prevCv');const cell=6;c.width=S.fw*cell;c.height=S.fh*cell;
  const ctx=c.getContext('2d');const bg=BGS[bgIdx][1];
  ctx.fillStyle=`rgb(${bg[0]},${bg[1]},${bg[2]})`;ctx.fillRect(0,0,c.width,c.height);
  const fr=S.frames[Math.min(pf,S.n-1)];for(let y=0;y<S.fh;y++)for(let x=0;x<S.fw;x++){
    const i=fr[y*S.fw+x];if(!i)continue;ctx.fillStyle=css(i);ctx.fillRect(x*cell,y*cell,cell,cell);}}

/* ---- view ---- */
function fit(){const W=$('canvasWrap').clientWidth-60,H=$('canvasWrap').clientHeight-50;
  zoom=Math.max(4,Math.min((W/S.fw)|0,(H/S.fh)|0));
  origin.x=((W+60)-S.fw*zoom)/2;origin.y=((H+50)-S.fh*zoom)/2;drawStage();}

/* ---- mouse ---- */
function cellAt(ev){const r=$('stage').getBoundingClientRect();
  const x=Math.floor((ev.clientX-r.left-origin.x)/zoom),y=Math.floor((ev.clientY-r.top-origin.y)/zoom);
  return [x,y];}
function inb(x,y){return x>=0&&x<S.fw&&y>=0&&y<S.fh;}
function snap(){return S.frames.map(fr=>fr.slice());}        // full-sheet snapshots
function pushUndo(){undo.push(snap());if(undo.length>120)undo.shift();redo=[];syncUndoBtns();}
// which (frame,x,y) cells a click at (x,y) on the active frame touches
function paintCells(x,y){
  const out=[[frame,x,y]];
  if(allFrames){for(let f=0;f<S.n;f++)if(f!==frame)out.push([f,x,y]);}
  else if(followMotion&&MOTION){for(let f=0;f<S.n;f++){if(f===frame)continue;
    const o=MOTION[frame][f][y]||[0,0];out.push([f,x+o[0],y+o[1]]);}}
  return out.filter(([f,cx,cy])=>cx>=0&&cx<S.fw&&cy>=0&&cy<S.fh);
}
function applyPaint(x,y,first){
  if(!inb(x,y))return;
  if(tool==='pick'){setFg(S.frames[frame][y*S.fw+x]);return;}
  const cells=paintCells(x,y);
  if(tool==='bucket'){if(first){pushUndo();
    for(const [f,cx,cy] of cells)flood(f,cx,cy,active);drawStage();rebuildThumbs();markDirty();}return;}
  const v=tool==='eraser'?0:active;
  if(first)pushUndo();
  let changed=false;
  for(const [f,cx,cy] of cells){const i=cy*S.fw+cx;if(S.frames[f][i]!==v){S.frames[f][i]=v;changed=true;}}
  if(changed){drawStage();rebuildThumbs();markDirty();}
}
function flood(f,x,y,to){const fr=S.frames[f];const from=fr[y*S.fw+x];if(from===to)return;
  const st=[[x,y]];while(st.length){const [cx,cy]=st.pop();if(!inb(cx,cy))continue;
    if(fr[cy*S.fw+cx]!==from)continue;fr[cy*S.fw+cx]=to;
    st.push([cx+1,cy],[cx-1,cy],[cx,cy+1],[cx,cy-1]);}}

window.addEventListener('load',()=>{
  init();
  const st=$('stage');
  st.addEventListener('mousedown',ev=>{
    if(tool==='pan'||ev.button===1||ev.spaceKey){panning=true;panStart={x:ev.clientX-origin.x,y:ev.clientY-origin.y};return;}
    if(ev.altKey){const [x,y]=cellAt(ev);if(inb(x,y))setFg(S.frames[frame][y*S.fw+x]);return;}
    painting=true;const [x,y]=cellAt(ev);applyPaint(x,y,true);});
  st.addEventListener('mousemove',ev=>{
    const [x,y]=cellAt(ev);
    $('stCur').textContent=inb(x,y)?('cur '+rowLabel(y)+x+'  ·  idx '+S.frames[frame][y*S.fw+x]):'—';
    if(panning){origin.x=ev.clientX-panStart.x;origin.y=ev.clientY-panStart.y;drawStage();return;}
    if(painting)applyPaint(x,y,false);});
  window.addEventListener('mouseup',()=>{painting=false;panning=false;});
  st.addEventListener('wheel',ev=>{if(!ev.ctrlKey&&!ev.metaKey)return;ev.preventDefault();
    const f=ev.deltaY<0?1.25:0.8;const nz=Math.max(2,Math.min(48,zoom*f));
    const r=st.getBoundingClientRect();const mx=ev.clientX-r.left,my=ev.clientY-r.top;
    origin.x=mx-(mx-origin.x)*nz/zoom;origin.y=my-(my-origin.y)*nz/zoom;zoom=nz;drawStage();},{passive:false});

  $('tools').addEventListener('click',ev=>{const t=ev.target.closest('.tool');if(!t||!t.dataset.tool)return;
    tool=t.dataset.tool;[...document.querySelectorAll('.tool')].forEach(x=>x.classList.toggle('on',x===t));});
  $('zoomIn').onclick=()=>{zoom=Math.min(48,zoom*1.25);drawStage();};
  $('zoomOut').onclick=()=>{zoom=Math.max(2,zoom*0.8);drawStage();};
  $('zoomFit').onclick=fit;
  $('gridTgl').onclick=e=>{showGrid=!showGrid;e.target.classList.toggle('on',showGrid);drawStage();};
  $('onionTgl').onclick=e=>{onion=!onion;e.target.classList.toggle('on',onion);drawStage();};
  $('refTgl').onclick=e=>{if(!REF)return;showRef=!showRef;e.target.classList.toggle('on',showRef);drawStage();};
  $('donorTgl').onclick=e=>{if(!REF)return;showDonor=!showDonor;e.target.classList.toggle('on',showDonor);drawStage();};
  $('motionTgl').onclick=e=>{showMotion=!showMotion;e.target.classList.toggle('on',showMotion);drawStage();};
  $('allTgl').onclick=e=>{allFrames=!allFrames;if(allFrames)followMotion=false;syncModeBtns();};
  $('followTgl').onclick=e=>{if(!MOTION)return;followMotion=!followMotion;if(followMotion)allFrames=false;syncModeBtns();};
  $('undoBtn').onclick=doUndo; $('redoBtn').onclick=doRedo;
  $('play').onclick=e=>{playing=!playing;e.target.textContent=playing?'⏸':'▶';if(playing)playStart=performance.now();};
  $('bgCycle').onclick=e=>{bgIdx=(bgIdx+1)%BGS.length;e.target.textContent=BGS[bgIdx][0]+' ▸';};
  $('save').onclick=save;
  $('finishBtn').onclick=async()=>{
    const url = S.done ? 'unfinish' : 'finish';
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({char:docId(),frames:S.frames})});
    if(r.ok){S=await r.json(); updateDoneUI(); await buildCharOptions(); syncModeSeg();}};
  $('resetBtn').onclick=async()=>{
    if($('resetBtn').disabled)return;
    if(!confirm('Reset '+CUR+' ('+MODE+') to the clean recolour? All edits to this sheet (including saved) will be lost.'))return;
    const r=await fetch('reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({char:docId()})});
    if(r.ok){await buildCharOptions(); await loadChar(CUR, MODE);}};
  window.addEventListener('keydown',ev=>{
    if(ev.metaKey||ev.ctrlKey){if(ev.key==='z'&&!ev.shiftKey){doUndo();ev.preventDefault();}
      else if((ev.key==='z'&&ev.shiftKey)||ev.key==='y'){doRedo();ev.preventDefault();}
      else if(ev.key==='s'){save();ev.preventDefault();}return;}
    const k=ev.key.toLowerCase();const map={b:'pencil',e:'eraser',g:'bucket',i:'pick',h:'pan'};
    if(map[k]){tool=map[k];[...document.querySelectorAll('.tool')].forEach(x=>x.classList.toggle('on',x.dataset.tool===tool));}});
  window.addEventListener('resize',()=>drawStage());
  window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
  playStart=performance.now();
});
function rebuildThumbs(){const cells=$('frames').children;
  for(let f=0;f<S.n;f++)if(cells[f])drawFrameInto(cells[f].querySelector('canvas').getContext('2d'),f,3,null);}
function syncModeBtns(){$('allTgl').classList.toggle('on',allFrames);
  $('followTgl').classList.toggle('on',followMotion);}
function syncUndoBtns(){const u=$('undoBtn'),r=$('redoBtn');
  if(u)u.disabled=!undo.length; if(r)r.disabled=!redo.length;}
function markDirty(){dirty=true; const b=$('save'); if(b&&!b.textContent.startsWith('● '))b.textContent='● '+b.textContent.replace(/^● /,'');}
function doUndo(){if(!undo.length)return;redo.push(snap());S.frames=undo.pop();drawStage();rebuildThumbs();syncUndoBtns();markDirty();}
function doRedo(){if(!redo.length)return;undo.push(snap());S.frames=redo.pop();drawStage();rebuildThumbs();syncUndoBtns();markDirty();}
async function save(){$('saveStat').querySelector('button')&&($('save').textContent='saving…');
  const r=await fetch('save',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({char:docId(),frames:S.frames})});
  if(r.ok)dirty=false;
  $('save').textContent = r.ok?('💾 Saved '+new Date().toLocaleTimeString()):'❌ FAILED';
  setTimeout(()=>{if(!dirty)$('save').textContent='💾 Save';},2500);}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='text/html; charset=utf-8'):
        body = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _char(self):
        q = parse_qs(urlparse(self.path).query)
        return q.get('char', [None])[0]

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html'):
            self._send(200, HTML)
        elif path == '/chars':
            chars = [{'id': u, 'donor': DOCS[u].donor_name,
                      'idleDone': DOCS[u].is_done(),
                      'hasWalk': (u + ':mu') in DOCS,
                      'walkDone': (u + ':mu') in DOCS and DOCS[u + ':mu'].is_done()}
                     for u in ORDER]
            self._send(200, json.dumps({'chars': chars}), 'application/json')
        elif path == '/data':
            self._send(200, _doc(self._char()).as_json(), 'application/json')
        elif path == '/reference':
            self._send(200, _doc(self._char()).reference_json(), 'application/json')
        else:
            self._send(404, 'not found')

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        payload = json.loads(self.rfile.read(length) or b'{}')
        try:
            if path == '/save':
                d = _doc(payload.get('char'))
                d.save(payload['frames'])
                print('  saved %s' % d.sheet_path)
                self._send(200, json.dumps({'ok': True}), 'application/json')
            elif path == '/reset':
                d = _doc(payload.get('char'))
                d.reset()
                print('  reset %s to clean recolour' % d.sheet_path)
                self._send(200, d.as_json(), 'application/json')
            elif path == '/finish':
                d = _doc(payload.get('char'))
                if 'frames' in payload:
                    d.save(payload['frames'])
                d.set_done(True)
                print('  FINISHED %s (approved-to-commit)' % d.id)
                self._send(200, d.as_json(), 'application/json')
            elif path == '/unfinish':
                d = _doc(payload.get('char'))
                d.set_done(False)
                print('  un-finished %s' % d.id)
                self._send(200, d.as_json(), 'application/json')
            else:
                self._send(404, 'not found')
        except Exception as exc:  # noqa: BLE001
            self._send(500, json.dumps({'ok': False, 'error': str(exc)}), 'application/json')


def _build_campaign_docs(campaign):
    """Per classed cast member, build an IDLE doc (<id>.png, key uid) and -- if a walk
    sheet exists -- a WALK/MU doc (<id>_mu.png, key uid+':mu', 32x32 frames). Geometry/
    reference/motion come from each one's donor (YAML art.map_sprite.base); reset snapshots
    live in map_sprites/.base/. ORDER lists the characters (for the picker)."""
    import build_campaign as bc
    adir = os.path.join(bc.REPO, 'campaigns', campaign, 'map_sprites')
    palette = os.path.join(adir, 'cast_palette.png')
    if not os.path.isfile(palette):
        sys.exit('ERROR: no %s' % palette)
    basedir = os.path.join(adir, '.base')
    gfx = os.path.join(bc.REPO, 'fireemblem8u', 'graphics', 'unit_icon')
    docs, order = {}, []
    for uid, slot, cls, sms in bc.classed_cast(campaign):
        sheet = os.path.join(adir, uid + '.png')
        if not os.path.isfile(sheet):
            continue
        base = bc.load_unit(campaign, uid).get('art', {}).get('map_sprite', {}).get('base')
        wait_donor = os.path.join(gfx, 'wait', 'unit_icon_wait_%s_sheet.png' % base) if base else None
        docs[uid] = Doc(sheet, palette,
                        wait_donor if wait_donor and os.path.isfile(wait_donor) else None,
                        base, uid, os.path.join(basedir, uid + '.png'))
        order.append(uid)
        mu_sheet = os.path.join(adir, uid + '_mu.png')
        if os.path.isfile(mu_sheet):
            move_donor = os.path.join(gfx, 'move', 'unit_icon_move_%s_sheet.png' % base) if base else None
            docs[uid + ':mu'] = Doc(
                mu_sheet, palette,
                move_donor if move_donor and os.path.isfile(move_donor) else None,
                base, uid + ':mu', os.path.join(basedir, uid + '_mu.png'), geom=(32, 32))
    if not docs:
        sys.exit('ERROR: no map_sprites/<id>.png sheets found for %s' % campaign)
    return docs, order


def _add_extra(docs, order, campaign, uid, base, geom=None):
    """Add an experimental/scratch character (not a real campaign unit) to the editor:
    map_sprites/<uid>.png on donor `base`, plus its walk if <uid>_mu.png exists. Lets you
    play with an alternate donor (e.g. a second marty on Civilian_M1, or a flapping pinky
    whose idle is the 32x32 flight) without touching the real cast. `geom` forces the idle
    frame size (e.g. (32,32) for a flight-as-idle); then the donor MOVE sheet is the
    reference. Not injected by the build (it only iterates classed_cast)."""
    import build_campaign as bc
    adir = os.path.join(bc.REPO, 'campaigns', campaign, 'map_sprites')
    palette = os.path.join(adir, 'cast_palette.png')
    basedir = os.path.join(adir, '.base')
    gfx = os.path.join(bc.REPO, 'fireemblem8u', 'graphics', 'unit_icon')
    sheet = os.path.join(adir, uid + '.png')
    if not os.path.isfile(sheet):
        sys.exit('ERROR: --extra %s: no %s' % (uid, sheet))
    # geom => idle is a 32x32 (flight-style) sheet; reference is the move donor. If a
    # matching reference override exists (.base/<uid>.ref.png -- original-colour frames
    # that line up with this sandbox's frames, e.g. action frames 12-14), use it so the
    # `donor`/`ref` underlay matches frame-for-frame.
    sub = 'move' if geom else 'wait'
    ref_override = os.path.join(basedir, uid + '.ref.png')
    if os.path.isfile(ref_override):
        ref = ref_override
    else:
        ref = os.path.join(gfx, sub, 'unit_icon_%s_%s_sheet.png' % (sub, base))
        ref = ref if os.path.isfile(ref) else None
    docs[uid] = Doc(sheet, palette, ref, base, uid,
                    os.path.join(basedir, uid + '.png'), geom=geom)
    if uid not in order:
        order.append(uid)
    mu_sheet = os.path.join(adir, uid + '_mu.png')
    if os.path.isfile(mu_sheet):
        move_donor = os.path.join(gfx, 'move', 'unit_icon_move_%s_sheet.png' % base)
        docs[uid + ':mu'] = Doc(mu_sheet, palette,
                                move_donor if os.path.isfile(move_donor) else None,
                                base, uid + ':mu', os.path.join(basedir, uid + '_mu.png'),
                                geom=(32, 32))


def main():
    global DOCS, ORDER
    ap = argparse.ArgumentParser(description='local browser pixel editor for cast sheets')
    ap.add_argument('sheet', nargs='?')
    ap.add_argument('palette', nargs='?')
    ap.add_argument('--campaign', default=None,
                    help='edit every cast sheet in this campaign (multi-character)')
    ap.add_argument('--extra', action='append', default=[], metavar='uid=Donor',
                    help='add an experimental scratch character (campaign mode), e.g. '
                         '--extra marty-boy=Civilian_M1')
    ap.add_argument('--donor', default=None,
                    help='donor class name (YAML art.map_sprite.base) -- frame size is '
                         'read from the decomp for it')
    ap.add_argument('--reference', default=None, help='donor sheet to show behind the work')
    ap.add_argument('--mu', action='store_true',
                    help='edit a MU/walk sheet (32x32 frames); reference defaults to the '
                         'donor MOVE sheet')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true')
    args = ap.parse_args()
    if args.campaign:
        DOCS, ORDER = _build_campaign_docs(args.campaign)
        for spec in args.extra:
            uid, _, base = spec.partition('=')
            if not base:
                sys.exit('ERROR: --extra expects uid=Donor[@WxH], got %r' % spec)
            geom = None
            if '@' in base:
                base, _, gs = base.partition('@')
                gw, _, gh = gs.partition('x')
                geom = (int(gw), int(gh))
            _add_extra(DOCS, ORDER, args.campaign, uid, base, geom)
    else:
        if not (args.sheet and args.palette):
            sys.exit('usage: map_sprite_editor.py <sheet.png> <cast_palette.png> --donor X\n'
                     '       map_sprite_editor.py <walk.png> <pal> --mu --donor X\n'
                     '       map_sprite_editor.py --campaign <name>')
        ref, geom = args.reference, None
        if args.mu:
            geom = (32, 32)  # MU/walk frame is the fixed 32x32 move-sprite OBJ size
            if not ref and args.donor:
                cand = os.path.join(map_sprite_tool.REPO, 'fireemblem8u', 'graphics',
                                    'unit_icon', 'move',
                                    'unit_icon_move_%s_sheet.png' % args.donor)
                ref = cand if os.path.isfile(cand) else None
        d = Doc(args.sheet, args.palette, ref, args.donor, geom=geom)
        DOCS, ORDER = {d.id: d}, [d.id]
    url = 'http://127.0.0.1:%d/' % args.port
    httpd = HTTPServer(('127.0.0.1', args.port), Handler)
    print('map sprite editor: %d character(s) [%s]' % (len(ORDER), ', '.join(ORDER)))
    print('open %s  (local only; Ctrl-C to stop)' % url)
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nstopped.')


if __name__ == '__main__':
    main()
