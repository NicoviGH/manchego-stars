"""The opening montage (#43) and the world-map tour.
"""
import os
import re
import shutil
import sys

from yaml_loader import yaml_load
import gen_subtitle_cards
from inject.decomp import _replace_brace_block, REPO
from inject.paths import (
    DATA_OPSUBTITLE_S, OP_SUBTITLE_GFX_DIR, OPSUBTITLE_C, PROLOGUE_WM_H, TEXTS_TXT,
    WORLD_MAP_GFX_DIR, WORLDMAP_RM_C)
from inject.text import _fe_dialogue_text, _wrap_fe_lines, set_message_body


TOUR_TEXT_ID = 0x8DB   # vanilla's WM narration message, referenced only here


def inject_opening_montage(campaign, verbose=True):
    """#43 lore crawl: re-render vanilla's seven opening-monologue slides from the
    campaign's locked card text and retime the display LUT to our word counts.
    The proc machinery (opsubtitle.c transitions, flare on slide 2, START-to-skip)
    is reused untouched -- the crawl was budgeted to seven cards for exactly that.
    Slide PNGs are decomp build inputs (make re-converts them via FETSATOOL + lz);
    stale intermediates are removed like the chap_title ones in inject_prologue."""
    montage_yaml = os.path.join(REPO, 'campaigns', campaign, 'events',
                                'opening-montage.yaml')
    cards = gen_subtitle_cards.crawl_cards(montage_yaml)
    with open(OPSUBTITLE_C, encoding='utf-8') as f:
        src = f.read()
    for i, text in enumerate(cards):
        png = os.path.join(OP_SUBTITLE_GFX_DIR, 'OpSubtitle_%02d.png' % i)
        gen_subtitle_cards.compose_card(text).save(png)
        for stale in ('.feimg2.bin', '.feimg2.bin.lz',
                      '.fetsa2.bin', '.fetsa2.bin.lz'):
            if os.path.exists(png[:-4] + stale):
                os.remove(png[:-4] + stale)
        src, n = re.subn(
            r'(gTsa_OpSubtitle_%02d,\n)(\s*)\d+(,)' % i,
            r'\g<1>\g<2>%d\g<3>' % gen_subtitle_cards.card_timer(text),
            src, count=1)
        if n == 0:
            sys.exit('ERROR: gOpSubtitleGfxLut timer for slide %d not found in %s'
                     % (i, OPSUBTITLE_C))
    # Backdrop mural: vanilla composites the slides over Img_CommGameBgScreen (the
    # brown rune wall) -- a SHARED asset (shops, chapter intro fx, ending details,
    # mural_background all decompress it), so never overwrite it. Instead point
    # opsubtitle.c's three uses at montage-local symbols and incbin our aurora-
    # township mural (book ch1 opener art, campaigns/.../events/opening-mural.png)
    # behind them. Same shape as vanilla: 640 sequential 4bpp tiles + 16-color pal.
    mural_src = os.path.join(REPO, 'campaigns', campaign, 'events',
                             'opening-mural.png')
    mural = gen_subtitle_cards.compose_mural(mural_src)
    mural_png = os.path.join(OP_SUBTITLE_GFX_DIR, 'MontageMural.png')
    mural.save(mural_png)
    with open(os.path.join(OP_SUBTITLE_GFX_DIR, 'MontageMural.gbapal'), 'wb') as f:
        f.write(gen_subtitle_cards.mural_gbapal(mural))
    for stale in ('.4bpp', '.4bpp.lz'):
        if os.path.exists(mural_png[:-4] + stale):
            os.remove(mural_png[:-4] + stale)
    src, n_img = re.subn(r'\bImg_CommGameBgScreen\b', 'Img_MontageMural', src)
    src, n_pal = re.subn(r'\bPal_08B1756C\b', 'Pal_MontageMural', src)
    if n_img != 1 or n_pal != 2:
        sys.exit('ERROR: mural symbol sites moved in %s (img %d != 1, pal %d != 2)'
                 % (OPSUBTITLE_C, n_img, n_pal))
    src = src.replace(
        '#include "constants/songs.h"',
        '#include "constants/songs.h"\n\n'
        '/* manchego #43: montage-local backdrop (vanilla rune wall is shared) */\n'
        'extern u8 CONST_DATA Img_MontageMural[];\n'
        'extern u16 CONST_DATA Pal_MontageMural[];', 1)
    with open(OPSUBTITLE_C, 'w', encoding='utf-8') as f:
        f.write(src)
    with open(DATA_OPSUBTITLE_S, encoding='utf-8') as f:
        dat = f.read()
    dat += ('\n\t.global Img_MontageMural\n'
            'Img_MontageMural:\n'
            '\t.incbin "graphics/op_subtitle/MontageMural.4bpp.lz"\n\n'
            '\t.global Pal_MontageMural\n'
            'Pal_MontageMural:\n'
            '\t.incbin "graphics/op_subtitle/MontageMural.gbapal"\n')
    with open(DATA_OPSUBTITLE_S, 'w', encoding='utf-8') as f:
        f.write(dat)
    if verbose:
        print('  lore crawl: %d slides re-rendered from %s; LUT retimed; '
              'aurora mural wired' % (len(cards), os.path.relpath(montage_yaml, REPO)))


def _tour_message_body(cards):
    """Render the town_tour cards as the WM narration message (vanilla 0x8DB
    shape): pages of up to two drawn lines ([LF] within a page, [A][LF]
    between pages), cards separated by [BreakTalk] -- each one is a TEXTCONT
    boundary in the event script -- and [X] terminated."""
    segs = []
    for card in cards:
        lines = _wrap_fe_lines(_fe_dialogue_text(card))
        pages = ['[LF]\n'.join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
        segs.append('[A][LF]\n'.join(pages) + '[A][CR][LF]')
    return ''.join(s + '\n[BreakTalk]\n' for s in segs) + '[X]'


def _tour_event_script(card_count):
    """The prologue WM event: vanilla's opening rhythm (spawn lord, silent ->
    THE BEGINNING, drawn map revealed by WM_FADEOUT) with our two backdrops.
    Card 1 plays over map A; the swap to map B hides under a FADI/FADU pair
    (both masks leave GMAPRM_FLAG_0/1 clear = no GmapRm blends, vanilla's own
    prologue shape); 0x10 = GMAPRM_FLAG_4 selects map B in the patched
    consumer.

    The WM text window covers the bottom ~50 rows, so map B rides vanilla's
    pan trick (WM_MOVECAM2 scrolls BG1 during the drawn-map display): shown
    at y=24 for the upper-lakes cards, panned to y=48 for the Redwaters card
    (bringing Good Mead / Dougan's Hole / Easthaven above the window) and
    back for the closer. gen_drawnmap letters both maps for these scrolls.
    Ends with vanilla's FADI + SKIPWN handoff into the chapter."""
    if card_count != 6:
        sys.exit('ERROR: tour script choreography expects 6 cards, got %d'
                 % card_count)
    lines = [
        'EVBIT_MODIFY(0x1)',
        'WmEvtNoFade',
        'WM_SPAWNLORD(WM_MU_0, CHARACTER_EIRIKA, WM_NODE_BorderMulan)',
        'WM_CENTERCAMONLORD(WM_MU_0)',
        'MUSCFAST(SONG_SILENT)',
        'STAL(32)',
        'MUSC(SONG_THE_BEGINNING)',
        'WM_SHOWDRAWNMAP(0, 0, 0x0)',
        'STAL(2)',
        'WM_FADEOUT(0)',
        'WM_TEXTDECORATE',
        'EVBIT_MODIFY(0x0)',
        'STAL(40)',
        'WM_SHOWTEXTWINDOW(40, 0x0001)',
        'WM_WAITFORTEXT',
        'WM_TEXTSTART',
        'WM_TEXT(0x%04X, 0)' % TOUR_TEXT_ID,   # card 1: the dale (map A)
        'TEXTEND',
        'STAL(20)',
        'FADI(16)',
        'WM_WAITFORFXCLEAR1',   # hide the drawn map (EventB5_WmHideBigMap)
        'WM_WAITFORFXCLEAR2',   # wait for its proc to end (EventB7_WmBigMapWait)
        'WM_SHOWDRAWNMAP(0, 24, 0x10)',
        'STAL(2)',
        'FADU(16)',
        'TEXTCONT',             # card 2: Bryn Shander
        'TEXTEND',
        'STAL(20)',
        'TEXTCONT',             # card 3: Maer Dualdon towns
        'TEXTEND',
        'STAL(20)',
        'TEXTCONT',             # card 4: Lac Dinneshere towns
        'TEXTEND',
        'STAL(10)',
        'WM_MOVECAM2(0, 24, 0, 48, 50, 0)',   # pan down to the Redwaters
        'STAL(55)',
        'TEXTCONT',             # card 5: Redwaters towns
        'TEXTEND',
        'STAL(10)',
        'WM_MOVECAM2(0, 48, 0, 24, 50, 0)',   # pan back for the closer
        'STAL(55)',
        'TEXTCONT',             # card 6: closer
        'TEXTEND',
        'WM_REMOVETEXT',
        'STAL(2)',
        'FADI(16)',
        'SKIPWN',
        'ENDA',
    ]
    return '{\n' + ''.join('    %s\n' % line for line in lines) + '}'


def inject_world_tour(campaign, verbose=True):
    """#43 world-map tour: the Icewind Dale drawn maps + the prologue WM event.

    Backdrops: the two gen_drawnmap --emit assets (a-dale = whole-dale
    establishing shot, b-towns = ten-towns close-up; GIF-review pair locked
    2026-06-10) ride the WM_SHOWDRAWNMAP slot. The vanilla assets
    (Img/Pal/Tsa_EventGmap) are SHARED with vanilla ch2/ch5 WM events, so the
    consumer (GmapRm_StartUpdateDirect) is patched to montage-local symbols
    instead of overwriting them (decisions.md mural rule); the never-read
    GMAPRM_FLAG_4 mask bit selects map B (proc->flag = mask minus UNBLOCK).

    Text: the 6 locked town_tour cards become msg 0x8DB -- vanilla's WM
    narration message, referenced only by this event."""
    montage_yaml = os.path.join(REPO, 'campaigns', campaign, 'events',
                                'opening-montage.yaml')
    with open(montage_yaml, encoding='utf-8') as f:
        cards = yaml_load(f)['town_tour']['cards']

    # 1. Backdrop binaries -> decomp graphics (make LZ-compresses 4bpp + tsa).
    os.makedirs(WORLD_MAP_GFX_DIR, exist_ok=True)
    for src_base, sym in (('tour-map-a-dale', 'MontageDrawnMapA'),
                          ('tour-map-b-towns', 'MontageDrawnMapB')):
        for ext in ('.4bpp', '.tsa', '.gbapal'):
            src = os.path.join(REPO, 'campaigns', campaign, 'events',
                               src_base + ext)
            if not os.path.exists(src):
                sys.exit('ERROR: %s missing -- run tools/gen_drawnmap.py --emit'
                         % src)
            dst = os.path.join(WORLD_MAP_GFX_DIR, sym + ext)
            shutil.copyfile(src, dst)
            if os.path.exists(dst + '.lz'):
                os.remove(dst + '.lz')

    with open(DATA_OPSUBTITLE_S, encoding='utf-8') as f:
        dat = f.read()
    for sym in ('MontageDrawnMapA', 'MontageDrawnMapB'):
        dat += ('\n\t.align 2, 0\n'
                '\t.global Img_%(s)s\nImg_%(s)s:\n'
                '\t.incbin "graphics/world_map/%(s)s.4bpp.lz"\n'
                '\t.align 2, 0\n'
                '\t.global Tsa_%(s)s\nTsa_%(s)s:\n'
                '\t.incbin "graphics/world_map/%(s)s.tsa.lz"\n'
                '\t.align 2, 0\n'
                '\t.global Pal_%(s)s\nPal_%(s)s:\n'
                '\t.incbin "graphics/world_map/%(s)s.gbapal"\n' % {'s': sym})
    with open(DATA_OPSUBTITLE_S, 'w', encoding='utf-8') as f:
        f.write(dat)

    # 2. Patch the consumer to the montage-local pair, selected by the mask.
    with open(WORLDMAP_RM_C, encoding='utf-8') as f:
        rm = f.read()
    rm = rm.replace(
        '#include "constants/worldmap.h"',
        '#include "constants/worldmap.h"\n\n'
        '/* manchego #43: montage-local drawn maps (vanilla EventGmap trio is\n'
        '   shared with ch2/ch5 WM events -- patch the consumer, not the data) */\n'
        'extern u8 CONST_DATA Img_MontageDrawnMapA[];\n'
        'extern u8 CONST_DATA Tsa_MontageDrawnMapA[];\n'
        'extern u16 CONST_DATA Pal_MontageDrawnMapA[];\n'
        'extern u8 CONST_DATA Img_MontageDrawnMapB[];\n'
        'extern u8 CONST_DATA Tsa_MontageDrawnMapB[];\n'
        'extern u16 CONST_DATA Pal_MontageDrawnMapB[];', 1)
    old = ('    Decompress(Img_EventGmap, (void *)BG_VRAM);\n'
           '    ApplyPalettes(Pal_EventGmap, 5, 4);\n'
           '    Decompress(Tsa_EventGmap, gGenericBuffer);\n')
    new = ('    if (proc->flag & GMAPRM_FLAG_4)\n'
           '    {\n'
           '        Decompress(Img_MontageDrawnMapB, (void *)BG_VRAM);\n'
           '        ApplyPalettes(Pal_MontageDrawnMapB, 5, 4);\n'
           '        Decompress(Tsa_MontageDrawnMapB, gGenericBuffer);\n'
           '    }\n'
           '    else\n'
           '    {\n'
           '        Decompress(Img_MontageDrawnMapA, (void *)BG_VRAM);\n'
           '        ApplyPalettes(Pal_MontageDrawnMapA, 5, 4);\n'
           '        Decompress(Tsa_MontageDrawnMapA, gGenericBuffer);\n'
           '    }\n')
    if rm.count(old) != 1:
        sys.exit('ERROR: GmapRm_StartUpdateDirect asset lines not in expected '
                 'vanilla form in %s' % WORLDMAP_RM_C)
    rm = rm.replace(old, new, 1)
    with open(WORLDMAP_RM_C, 'w', encoding='utf-8') as f:
        f.write(rm)

    # 3. The tour event + its message body.
    with open(PROLOGUE_WM_H, encoding='utf-8') as f:
        wm = f.read()
    wm = _replace_brace_block(wm, 'EventScrWM_Prologue_Beginning[] =',
                              _tour_event_script(len(cards)), PROLOGUE_WM_H)
    with open(PROLOGUE_WM_H, 'w', encoding='utf-8') as f:
        f.write(wm)

    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, TOUR_TEXT_ID, _tour_message_body(cards))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    if verbose:
        print('  world tour: %d cards -> MSG_%03X; drawn maps A (dale) + B '
              '(ten-towns) wired via GMAPRM_FLAG_4' % (len(cards), TOUR_TEXT_ID))
