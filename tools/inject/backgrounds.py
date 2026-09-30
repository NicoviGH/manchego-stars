"""Event backgrounds (#22): vendored winter BGs appended to gConvoBackgroundData.
"""
import os
import shutil
import sys

from inject.decomp import REPO
from inject.paths import BACKGROUNDS_H, BG_GFX_DIR, BG_H, DATA_BG_S, EVENTSCR2_C


# Campaign event BGs, in slot order. Each rides a NEW gConvoBackgroundData index; the 240x160
# source PNG (tools/bg_to_fe8.py output, <=8 banks) lives in campaigns/<c>/backgrounds/<stem>.png
# and make's generic bg rules build its bins. The vanilla enum ENDS at BG_RANDOM (0x37, a
# sentinel with no real BG). Rather than shove BG_RANDOM aside for each new BG (a per-BG hack
# that caps at one), we APPEND campaign BGs PAST it starting at 0x38 -- the same "append into
# free enum space, never disturb a vanilla slot" model as the appended enemy/class slots (0x80+)
# -- so the range grows without limit. The two pre-0x38 gaps (0x36 free + 0x37 BG_RANDOM) get
# harmless placeholder table rows so the table stays index==enum contiguous. (enum_name, stem, credit).
CAMPAIGN_BG_SLOT0 = 0x38   # first campaign BG index -- PAST the vanilla BG_RANDOM sentinel (0x37)
CAMPAIGN_BGS = [
    ('BG_MS_TARGOS_WINTER',   'bg_TargosWinter',   '{Zeldacrafter}'),  # ch02 ending: Targos at night
    ('BG_MS_TERMALAINE_MINE', 'bg_TermalaineMine', '{FE7 rip}'),        # ch03 opening: the mine mouth
    # ch04 opening beat B: the fogged forest edge. NOT a vendored import and not new tile art --
    # vanilla's own bg_Plain_1 TILES under a winter palette. The BG "fog" variants (_Fog, _Sunset,
    # _Night) are palette swaps of one image, which is why BG_PLAIN_1_FOG is a green summer meadow
    # under white haze and read wrong in a snowbound chapter. Additive slot, so vanilla's BG is
    # untouched and still available. Approved by Nicolas 2026-07-31 over BG_TREES.
    ('BG_MS_LONELYWOOD_FOG',  'bg_LonelywoodFog',  '{vanilla FE8 bg_Plain_1, winter palette}'),
    # The two Ten-Towns settlements that had been borrowing another town's backdrop. Both are
    # Fenriel winter CGs, already 240x160, and both need the 8-bank refit in bg_to_fe8.py (a
    # dithered CG has tiles of 16-18 colours, so the greedy single-set pack cannot hold them).
    # Distinct backdrops per town is the point: BG_MS_TARGOS_WINTER already backs ch02's and
    # ch03's endings, and a third reuse reads as one town (Nicolas, 2026-08-09).
    ('BG_MS_BRYN_SHANDER_WINTER', 'bg_BrynShanderWinter', '{Fenriel}'),  # ch01 ending: walled town at dusk
    ('BG_MS_BREMEN_WINTER',       'bg_BremenWinter',      '{Fenriel}'),  # ch07 (#27): the lakeside town
    # ch05's opening backdrop (#25): the elven tomb's snowed-in stonework, behind the three
    # scenes that play before the party arrives. Nicolas's pick 2026-08-13, and the FIRST
    # vendored BG that needed NO refit -- the FE-Repo's FE9-10 rips ship already indexed at 16
    # colours, so bg_to_fe8.py's greedy pack reproduces the source EXACTLY (0 of 38400 pixels
    # differ from the 5-bit source picture). It lands on 2 banks rather than 1 only because FE8
    # reserves local index 0 of every bank as transparent -- 15 usable, and the source has 16.
    # Well inside the SIX the fade/transition procs apply, unlike Bremen's 8.
    # This rip family is LETTERBOXED -- a 240-wide picture in a 256-wide canvas -- and both ch05
    # BGs first shipped with half the mat still on, because a CENTRE crop keeps half of it and
    # discards real picture opposite. `trim_uniform_border` strips it, so these land 1:1 with no
    # scaling. Long form: decisions.md -> "A letterbox mat is not picture".
    ('BG_MS_ELVEN_TOMB',          'bg_ElvenTomb',         '{FE9-10 CG rip}'),
    # ch05 scene 4 (#25): the ridge the party crests, and the first backdrop in the chapter the
    # PARTY is standing in rather than looking at from the tomb's side. It is a SECOND BG in one
    # scene run on purpose -- vanilla Ch5 spends BG_SERAFEW_VILLAGE on four consecutive scenes and
    # switches to BG_TOWN at exactly this beat, when the travellers physically arrive. Same FE9-10
    # rip family as the tomb, so it needs no refit either -- and the same letterbox mat, stripped
    # the same way: mode-P at 16 colours in, 0 of 38400 pixels different from the 5-bit source
    # PICTURE out. It packs onto 3 banks rather than the tomb's
    # 2 (16 source colours against 15 usable per bank, and this picture's tiles straddle the split
    # differently), still inside the SIX the fade/transition procs apply.
    ('BG_MS_FOREST_OUTSKIRTS_WINTER', 'bg_ForestOutskirtsWinter', '{FE9-10 CG rip}'),
    # ch05 scene 7 (#25): the moose BELLOWS, full screen, between Pinky's question and the
    # charge. Nicolas's art and Nicolas's idea (2026-08-15), and the reason it is a BG rather
    # than a portrait is the whole point: a 96x80 bust is drawn in the talk window's envelope
    # and those antlers do not fit it, while a BACG owns all 240x160 and has no envelope at all.
    # The beat is WORDLESS, so unlike every other entry here it carries no message and costs no
    # message id -- the flash is BACG/FADU/STAL/FADI plus vanilla's own EventScr_RemoveBGIfNeeded,
    # which is `village_script`'s mid-map idiom with the text half removed.
    # SIX banks, which is the ceiling that matters rather than the eight a BACG can hold: the
    # fade/transition procs apply only six, and this image FADES in and out (Bremen's 8-bank CG
    # is why that rule is written down). Converted at --banks 6 from a 1260x1047 RGBA master,
    # cropped to FILL rather than fitted with bars -- the beat is a bellow in the player's face
    # and the crop is what sells the scale.
    # The PLATE behind it is the elven tomb's own backdrop, and that is the second answer to
    # "make it look like it is over the map" rather than the first. The first was to bake a
    # CAPTURED MAP FRAME in behind the animal, which composites perfectly and dies on contact
    # with motion: the risen standing in that frame do not move for the 90 frames it is up, and
    # a map whose units are frozen reads as a photograph of a map (Nicolas, 2026-08-15 --
    # "what gives it away is the rest of the characters don't move"). A SCENIC plate promises no
    # motion, so there is nothing to give away. General rule: a still image may stand in for a
    # still thing; it may never stand in for something the player has just watched move.
    ('BG_MS_WHITE_MOOSE',         'bg_WhiteMoose',        '{Nicolas}'),
]


def inject_backgrounds(campaign, verbose=True):
    """Append the campaign's vendored event BGs as NEW gConvoBackgroundData slots (#22).

    Additive: each BG gets a fresh enum id (backgrounds.h), a table row (eventscr2.c) and
    incbin symbols (data_bg.s) -- never an edit to a vanilla entry. PNGs come from
    campaigns/<c>/backgrounds/ (tools/bg_to_fe8.py output); the decomp's generic
    gbagfx/FETSATOOL rules build .feimg2.bin.lz / .fetsa2.bin / .gbapal at make time. The
    four patched decomp files are in PATCHED_DECOMP_FILES (restored from HEAD each build),
    so insert-before-anchor stays idempotent; the copied PNG + its stale bins are refreshed."""
    src_dir = os.path.join(REPO, 'campaigns', campaign, 'backgrounds')
    # slot(i) = CAMPAIGN_BG_SLOT0 + i, all PAST the BG_RANDOM sentinel (0x37). Assets (PNG copy,
    # incbin syms, externs) are per-BG; the enum + table build handles the sentinel gap below.
    by_slot, data_syms, externs = {}, [], []
    for i, (enum_name, stem, _credit) in enumerate(CAMPAIGN_BGS):
        slot = CAMPAIGN_BG_SLOT0 + i
        src_png = os.path.join(src_dir, stem + '.png')
        if not os.path.isfile(src_png):
            sys.exit('ERROR: campaign BG source missing: %s' % src_png)
        dst_png = os.path.join(BG_GFX_DIR, stem + '.png')
        shutil.copyfile(src_png, dst_png)
        for stale in ('.feimg2.bin', '.feimg2.bin.lz', '.fetsa2.bin',
                      '.fetsa2.bin.lz', '.gbapal'):
            if os.path.exists(dst_png[:-4] + stale):
                os.remove(dst_png[:-4] + stale)
        by_slot[slot] = (enum_name, stem)
        externs.append('extern unsigned char %s_tiles[];\n'
                       'extern unsigned char %s_map[];\n'
                       'extern unsigned char %s_palette[];' % (stem, stem, stem))
        data_syms.append(
            '\n\t.align 2, 0\n\t.global %(s)s_tiles\n%(s)s_tiles:\n'
            '\t.incbin "graphics/bg/%(s)s.feimg2.bin.lz"\n'
            '\n\t.align 2, 0\n\t.global %(s)s_map\n%(s)s_map:\n'
            '\t.incbin "graphics/bg/%(s)s.fetsa2.bin"\n'
            '\n\t.align 2, 0\n\t.global %(s)s_palette\n%(s)s_palette:\n'
            '\t.incbin "graphics/bg/%(s)s.gbapal"\n' % {'s': stem})
    # 1. enum ids: campaign BGs live PAST BG_RANDOM (0x37) -> insert AFTER its line (keeps the
    #    table index == enum value, and never renumbers the vanilla sentinel).
    enum_lines = ['    %s = 0x%X,' % (by_slot[s][0], s) for s in sorted(by_slot)]
    with open(BACKGROUNDS_H, encoding='utf-8') as f:
        h = f.read()
    anchor = next((ln for ln in h.splitlines() if ln.strip().startswith('BG_RANDOM')), None)
    if anchor is None or h.count(anchor) != 1:
        sys.exit('ERROR: BG_RANDOM enum anchor not unique in %s' % BACKGROUNDS_H)
    h = h.replace(anchor, anchor + '\n' + '\n'.join(enum_lines), 1)
    with open(BACKGROUNDS_H, 'w', encoding='utf-8') as f:
        f.write(h)
    # 2. table rows: append after bg_Blank (0x35) up to the highest campaign slot. Indices with
    #    no campaign BG (the 0x36 gap + 0x37 BG_RANDOM) get a harmless bg_Blank placeholder row
    #    so the table stays index==enum contiguous; BG_RANDOM never hits it (eventscr.c short-
    #    circuits on `bgIndex == BG_RANDOM` before any table lookup).
    placeholder = '\t{bg_Blank_tiles, bg_Blank_map, bg_Blank_palette},'
    table_rows = []
    for idx in range(0x36, max(by_slot) + 1):
        if idx in by_slot:
            s = by_slot[idx][1]
            table_rows.append('\t{%s_tiles, %s_map, %s_palette},' % (s, s, s))
        else:
            table_rows.append('%s /* 0x%X: BG_RANDOM / gap placeholder (never drawn) */' % (placeholder, idx))
    tail = placeholder + '\n};'
    with open(EVENTSCR2_C, encoding='utf-8') as f:
        c = f.read()
    if c.count(tail) != 1:
        sys.exit('ERROR: gConvoBackgroundData tail not in expected form in %s' % EVENTSCR2_C)
    c = c.replace(tail, placeholder + '\n' + '\n'.join(table_rows) + '\n};', 1)
    with open(EVENTSCR2_C, 'w', encoding='utf-8') as f:
        f.write(c)
    # 3. externs: the table rows reference the data_bg symbols -- declare them in bg.h.
    decl_anchor = 'extern unsigned char bg_Blank_palette[];'
    with open(BG_H, encoding='utf-8') as f:
        bh = f.read()
    if bh.count(decl_anchor) != 1:
        sys.exit('ERROR: bg.h extern anchor not unique in %s' % BG_H)
    bh = bh.replace(decl_anchor, decl_anchor + '\n' + '\n'.join(externs), 1)
    with open(BG_H, 'w', encoding='utf-8') as f:
        f.write(bh)
    # 4. incbin symbols: append to data_bg.s (the bins are make-built from the PNG).
    with open(DATA_BG_S, encoding='utf-8') as f:
        d = f.read()
    with open(DATA_BG_S, 'w', encoding='utf-8') as f:
        f.write(d + ''.join(data_syms))
    if verbose:
        print('  %d campaign BG(s) -> gConvoBackgroundData[0x%X..] (additive)'
              % (len(CAMPAIGN_BGS), CAMPAIGN_BG_SLOT0))
