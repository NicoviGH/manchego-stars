---
id: 165
title: "World-map tour rides vanilla's drawn-map slot with two Icewind Dale backdrops, selected by a free mask bit."
date: "2026-06-10"
section: "Story & Dialogue"
issues: [29, 43]
---

# World-map tour rides vanilla's drawn-map slot with two Icewind Dale backdrops, selected by a free mask bit.

The drawn map (`WM_SHOWDRAWNMAP` → `StartGmapRm`, `worldmap_rm.c`) is one 240×160 prerendered screen: a 30×20 TSA
over ≤640 unique 4bpp tiles at BG VRAM 0, palette rows 5-8 (raw TSA entries get +0x5000). `tools/gen_drawnmap.py`
converts source art into that format (crop 3:2 → 240×160 → erase source lettering with rect median filters — it
never survives the downscale — → re-letter in a 3×5 micro-caps font + Georgia titles → per-tile 4-row palette
quantization; `--emit` writes the ROM trio into `campaigns/.../events/`). **Format gotchas (cost a debug session
each):** tile 0 must be fully transparent — during the blocking display `GmapRm_80C2320` parks BG1 behind a
cleared-to-tile-0 BG2, so a non-blank tile 0 paints the whole screen through the wrong palette; and TSA rows are
stored bottom-up (`TmApplyTsa` walks the dest upward). **Backdrop pair (Nicolas, 2026-06-10):** map A = the Gemini
Magvel-style repaint of the whole dale (establishing shot, card 1), map B = the purchased hand-drawn ten-towns map,
icy duotone, all ten towns + three lakes re-lettered (cards 2-6). Vanilla's `Img/Pal/Tsa_EventGmap` are shared with
ch2/ch5 WM events, so the consumer is patched to montage-local `*_MontageDrawnMap{A,B}` symbols (mural rule);
`GMAPRM_FLAG_4` (0x10, never read by engine code) on the `WM_SHOWDRAWNMAP` mask picks map B. **Event**
(`inject_world_tour`, MONTAGE=1): `EventScrWM_Prologue_Beginning` rewritten on vanilla's own rhythm — spawn lord,
SILENT → THE BEGINNING, map revealed by `WM_FADEOUT`; the A→B swap hides under a `FADI`/`FADU` pair (masks leave
the GmapRm blend flags clear, vanilla's prologue shape). The WM text window covers the bottom ~50 rows, so map B
shows at scroll y=24 and rides vanilla's pan trick (`WM_MOVECAM2` scrolls BG1 here, not the camera) down to y=48
for the Redwaters card and back for the closer; both maps are lettered for those scrolls. The 6 locked `town_tour`
cards become msg 0x8DB (vanilla's WM narration, referenced only here) as `[BreakTalk]` segments ↔ `TEXTCONT`
boundaries, 42-char lines, 2-line pages. **Save-slot banners:** `sub_80895B4`'s `config&1` palette table continues
past the 9-color `gPal_08A07AD8` label — the save-slot select reads pair 0's tail + the +0x10 dim row through
`gUnknown_08A07AEA`/`gUnknown_08A07B0A`, so `inject_title_theme` recolors those too (16 + first 7 colors) or the
unselected slots stay vanilla green; the per-difficulty pairs stay vanilla (semantic colors).
_Decided: 2026-06-10; full New-Game-to-map GIF reviewed and approved by Nicolas ("perfect"), save-slot fix verified
in-emulator. Closes the tour half of #43 and bootstraps #29._

**Multi-speaker cutscene faces: the budget is PODIUMS (positions), not speakers (the 4-face fix).**
Only `FACE_SLOT_COUNT = 4` faces load at once (the `gFaces` pool; `include/face.h`), but a big set
piece (the ch01 Beat-1 Northlook scene) has ~10 speakers. `_script_to_message` tracks the 8 talk
POSITIONS as a live map (≤4 loaded) + an LRU: reusing a podium for a new speaker emits
`[OpenX][ClearFace]` (scene.c fades out `faces[activePosition]` and frees its slot; the command's
temporary lock means the fade-out completes BEFORE the next `[LoadFace]`, so the pool never
overflows), and a full pool evicts the LRU. A `preload` list seeds silent **listeners** before the
dialogue (so no one talks to an empty room); a `(podium, None)` staging value is a faceless box.
≤4-podium scripts (the prologue) render byte-identically to the old lazy-load path.

**Staging = clean two-shots.** Face podiums (gTalkFaceHPosLut, px = x·8; faces are 96px wide):
FarLeft 24 / MidLeft 48 / Left 72 / Right 168 / MidRight 192 / FarRight 216. Only podiums ≥96px
apart avoid overlap, so the one clean pair is **MidLeft ↔ MidRight** (144px). Speakers therefore
rotate through the mid-left spotlight with the anchor (Hlin) at mid-right; listeners fill outer
podiums where slight overlap reads as "standing together." (Decided after Nicolas flagged 3-stacked
listeners and Hlin/Scramsax overlap as too crowded.)

**Scene wiring.** The locked chapter `script:` splits on `beat_break` sentinels into one `Text()`
per beat — each `Text` ends in `REMA`, which clears all faces (`sub_800E640`) → a fresh 4-face
budget per beat while the `BACG` background persists across `REMA` (cf. ch16a). At the head of
`EventScr_Ch2_BeginningScene`: `REMOVEPORTRAITS`→`BACG(BG_FIREPLACE)`→`FADU`→`BROWNBOXTEXT`
(auto-dismissing "The Northlook" card)→beats A–E (Hlin's "who leads?" lands in beat E, still at the
Northlook)→`FADI`. Then the **lord-select runs over its own scenic BG, not the battle map**
(`CH01_LORDSEL_BG = BG_DARKLING_WOODS`): `BACG` draws on BG3, the menu's `ClearBg0Bg1` only touches
BG0/1, and `CallLordSelectMenu` sets `SetDispEnable(1,1,0,1,1)` (BG2/map OFF). After the pick:
`FADI`→`LOMA(host)` (`RestartBattleMap` rebuilds the map BG VRAM that `BACG` clobbered — cf. ch13a;
plain `RemoveBGIfNeeded` is for chapter *transitions*)→DISA/LOAD→`FADU`→PREP.

**ON-MAP (no-BG) event-script cutscenes anchor the talk bubble to a FACE, not a unit** (the ch03
mid-map RBG-execution beat — a mid-battle Misc `AFEV`, no `BACG`). Over a `BACG` the text is a
full-screen window; on the bare map it's a `PutTalkBubble` speech bubble, and the bubble anchors to
the on-screen face podium (`[OpenX][LoadFace]`). So a **faced** beat renders fine wherever the camera
is, but a **faceless** line (no `[OpenX]`) has no anchor — in a Misc `AFEV`/`TURN` script there is no
talking unit either — so the bubble lands off the tilemap and only a sliver shows. Two rules fall out
(`_beat_is_faceless` routes them): (1) a faceless on-map line must ride the opaque **auto-centered**
box (`SVAL(EVT_SLOT_B, 0xFF00FF)`→`SOLOTEXTBOXSTART`), which needs no anchor; (2) **never mix a faced
and a faceless speaker in one on-map beat** — the faceless half drags the shared bubble off-screen and
mis-wraps the faced half (Marty + the mugless Brute did exactly this). Split them into separate beats
(each `Text()`'s trailing `REMA` clears faces, so none bleed across — a bare `TEXTSHOW` chain without
it left Pinky's face up under Wolfram). Cleanest fix when a speaker recurs: **give it a mug** — the
Brute got one on the collision-free Caellach guest slot (`GUEST_PORTRAIT_MAP`), turning its beat into
a normal faced bubble. Verified in-engine (`recordch03midmap`, 2026-07-11).

**Transitions: keep the FADE (vanilla-flavored).** Vanilla never reuses one podium for different
*people* — each speaker gets their own slot (≤4), faces fade in once, `REMA` clears between messages
(`[ClearFace]` is in 0/119 vanilla scripts); the in-place swap (`sub_80066E0`) is vanilla but only
for one character's *expression* change. So for our one-podium roll-call the `[ClearFace]` fade
("one leaves, next arrives") fits vanilla's grammar; a swap would morph one face into another.
_Decided 2026-06-16 with Nicolas across four motion reviews (`run.sh recordch01`): Sclorbo shows
his Ross face; Marty's spore-cough is a parenthetical (FE8 has
no cutscene particle FX); Pinky (Neimi) appears beside RBG at his intro; lord-select confirm reads
"lead the party." `make` green, `verify_text` 3404/0, playtests PASS (ch00 win/gameover, ch01 entry,
ch01win). #21._

**Ch1 trail beats: vanilla-reskin hints, an Izobai boss voice, and 'Ol Bitey over the hearth.**
The two house hints reskin **vanilla Ch1's own house quotes** (`0x93B`/`0x93C`, the ids we reuse):
the gate→"the mounds provide defense and heal wounds to boot," and the armor-knight→Izobai's
scrap-plate "turns aside almost any blade… I know my armor, though… a good blast of magic could get
right through it" (the weapon-triangle tip was cut — vanilla's house never carries it). The road
sign + the dismembered sled-driver fold into one trailhead trigger. Izobai (`lore/izobai.md`,
cunning/mocking mercenary) gets a turn-1 taunt (spare `EventScr_Ch2_Turn2Player` slot) and a death
quote. **'Ol Bitey** — the stuffed fish Scramsax name-drops — is mounted over the Northlook hearth
by `inject_northlook_bitey`: a build step that git-restores the vanilla `bg_Fireplace.png` (idempotent),
paints a small fish using ONLY existing palette colours (so each 8x8 tile stays in its 4bpp 16-colour
bank), and clears the converted intermediates so `make` re-derives them. Hand-written narration must
pass `_term_pad` (the `[.]` Huffman terminator-parity pad) or it bleeds into the next message.
_Decided 2026-06-17 with Nicolas (interactive dialogue pass, one beat at a time; Bitey art reviewed
in-game). `make` green, `verify_text` 3404/0, ch01win PASS. #21._

---

**Ch1 ending "The Rolling Cheddar" wired the same way as Beat 1.**
The locked `chapter_end` script is consumed by `inject_ch01` into `EventScr_Ch2_EndingScene` exactly
like the opening: a scenic `BACG` + a "Bryn Shander" brown-box card + one `Text()` per beat (A–F),
each `Text()`'s trailing `REMA` clearing faces so the 4-face budget resets per beat. Speakers are
staged as clean two-shots — **Duvessa (the host) anchors mid-right** and the party speaks mid-left,
with the other beat speaker placed opposite her; in beat E **Baxby evicts Duvessa's mid-right podium**
(`[OpenMidRight][ClearFace]`) as she gestures to the market and the bird steps forward. Bodies/card
ride the same dead vanilla Ch1-tutorial slot-2 ids as Beat 1 (`0x946`–`0x94C`). **Baxby's cutscene
face rides the vanilla Forde slot** (`GUEST_PORTRAIT_MAP`): Forde is a Cavalier — matching Baxby's
donor class — absent from our MVP chapters (ch00–08), so dressing `FID_Forde` with `baxby.png` is
collision-free; his recruit UNIT + map sprite will ride that same Forde character slot when wired.
The scene plays over the vanilla **`BG_NORMAL_VILLAGE`** BG (we tried winterizing it — a palette swap
just washes the village out, and no clean FE8 GBA snow-village BG existed in the FE-Repo — so we use it
as-is; Nicolas 2026-06-17) and `MNC2(0x3)` still drops to vanilla Ch3 until ch02 is hosted.
_Wired 2026-06-17. `make` green, `verify_text` 3404/0, ch01win PASS (ending runs through all 6 beats
→ advances). Feel/motion review is Nicolas's in-game pass. #21._

---
