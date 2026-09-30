"""The Arena (#265): the campaign's presentation palette, backdrop, and attendant faces.
"""
import glob
import os
import re
import struct
import sys

from PIL import Image

from yaml_loader import yaml_load
import portrait_tool
from inject.cast import _vendor_mug_to_bust, GUEST_PORTRAIT_MAP, PORTRAIT_MAP
from inject.chapter_ids import CH02_CHWINGA_PORTRAIT_SLOT, CH05_VISIT_FACES
from inject.decomp import DECOMP, REPO, vanilla_decomp_text
from inject.hosts import hosted_chapters
from inject.paths import PORTRAIT_DIR, UIARENA_C


def inject_arena_attendant_portraits(campaign, verbose=True):
    """Dress each chapter-declared Arena attendant onto its configured vanilla face slot."""
    overrides = arena_presentation_config(campaign)['chapters']
    # Validate every slot BEFORE writing any of them, so a bad pairing is reported instead of
    # discovered halfway through with some slots already dressed. Two chapters may share a
    # slot only if they share the attendant: silently keeping the first chapter's art while
    # GetArenaPresentationFace still emits a case for both hosts would put the wrong
    # attendant on screen with a green build.
    claimed = {}
    for _host, override in sorted(overrides.items()):
        slot, portrait = override['face_slot'], override['portrait_path']
        if claimed.setdefault(slot, portrait) != portrait:
            sys.exit('ERROR: %s: Arena attendant face_slot %r is already dressed with a '
                     'different portrait (%s) -- give this chapter its own slot'
                     % (override['chapter_path'], slot, claimed[slot]))

    written = set()
    for host, override in sorted(overrides.items()):
        slot = override['face_slot']
        if slot in written:
            continue
        bust = _vendor_mug_to_arena_bust(override['portrait_path'])
        tileset, mouth, chibi, pal_bytes = portrait_tool.generate(
            bust, static_portrait=True)
        base = os.path.join(PORTRAIT_DIR, 'portrait_' + slot)
        tileset.save(base + '_tileset.png')
        mouth.save(base + '_mouth.png')
        chibi.save(base + '_chibi.png')
        with open(base + '_palette.agbpal', 'wb') as f:
            f.write(pal_bytes)
        written.add(slot)
        if verbose:
            print('  Arena attendant host %d -> portrait_%s' % (host, slot))


def _bgr555(hexstr):
    """'#rrggbb' -> a 15-bit BGR555 halfword (FE8 .agbpal / GBA palette format)."""
    h = hexstr.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


# The Arena combat backdrop's three palette phases, straight out of the base ROM. Offsets are
# the `.incbin` arguments in data/banim-efxlvupfx.s -- the decomp's own numbers. The four banks
# land at gPaletteBuffer + 0x60, i.e. hardware BG banks 6..9, which is what campaign.yaml and
# the ch05arena proof both speak in.
ARENA_BATTLE_BG_PALETTES = {'A': 0x5BEF94, 'B': 0x5BF014, 'C': 0x5BF094}
ARENA_BATTLE_BG_BASE_BANK = 6
# gPal_ArenaBuildingFront (data/data_9A31F8.s) -- the welcome screen's coliseum exterior.
# uiarena.c applies it at ApplyPalettes(..., 0xC, 4), i.e. hardware banks 12..15.
ARENA_FRONT_PALETTE = 0x9AC024
ARENA_FRONT_BASE_BANK = 12


def _vanilla_palette_words(offset):
    with open(os.path.join(DECOMP, 'baserom.gba'), 'rb') as f:
        rom = f.read()
    return list(struct.unpack_from('<64H', rom, offset))


def vanilla_arena_battle_palettes():
    """{phase: [64 BGR555 words]} read from the untouched base ROM."""
    return {phase: _vanilla_palette_words(offset)
            for phase, offset in sorted(ARENA_BATTLE_BG_PALETTES.items())}


def vanilla_arena_front_palette():
    """The welcome screen's 64 vanilla BGR555 words, read from the untouched base ROM."""
    return _vanilla_palette_words(ARENA_FRONT_PALETTE)


def arena_palette_delta(background, field, config_path, base_bank):
    """Validate one Arena palette DELTA -> {palette word index: BGR555 word}.

    A delta, not a palette, and deliberately so. Both arena views were first authored as
    complete 64-word replacements, and both were rejected on sight for the same reason: the
    combat backdrop lost the coliseum's stone, wood, gold and crowd, and the welcome screen's
    masonry stopped reading as a material (its saturation had been crushed from 0.29-0.74 to
    0.10-0.20 while its luminance was faithfully preserved -- which is why every numeric check
    passed). Naming only the words that change makes that failure unrepresentable.
    """
    if not isinstance(background, list) or not background:
        got = type(background).__name__ if background is not None else 'nothing'
        sys.exit('ERROR: %s: %s must be a non-empty list of {bank, index, color} entries '
                 '(got %s)' % (config_path, field, got))
    banks = range(base_bank, base_bank + 4)
    delta = {}
    for i, entry in enumerate(background):
        where = '%s[%d]' % (field, i)
        if not isinstance(entry, dict) or set(entry) != {'bank', 'index', 'color'}:
            sys.exit('ERROR: %s: %s must be a mapping with exactly bank, index and color '
                     '(got %r)' % (config_path, where, entry))
        bank, index, color = entry['bank'], entry['index'], entry['color']
        if bank not in banks:
            sys.exit('ERROR: %s: %s bank must be one of %s (the four banks the Arena backdrop '
                     'occupies), got %r' % (config_path, where, list(banks), bank))
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index <= 15:
            sys.exit('ERROR: %s: %s index must be 0..15, got %r' % (config_path, where, index))
        if index == 0:
            sys.exit('ERROR: %s: %s names index 0, the transparent key -- it must stay '
                     'byte-identical in every bank' % (config_path, where))
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', color):
            sys.exit('ERROR: %s: %s color must be #RRGGBB, got %r'
                     % (config_path, where, color))
        word_index = (bank - base_bank) * 16 + index
        if word_index in delta:
            sys.exit('ERROR: %s: %s names bank %d index %d twice'
                     % (config_path, where, bank, index))
        delta[word_index] = _bgr555(color)
    return delta


def _compose(vanilla_words, delta):
    words = list(vanilla_words)
    for word_index, word in delta.items():
        words[word_index] = word
    return words


def _arena_section_background(section, name, config_path):
    if not isinstance(section, dict):
        sys.exit('ERROR: %s: arena_presentation.%s must be a mapping' % (config_path, name))
    return section.get('background'), 'arena_presentation.%s.background' % name


def arena_welcome_palette_delta(welcome, config_path):
    """Validate the welcome-screen delta. Pure config -- reads no ROM (see below)."""
    background, field = _arena_section_background(welcome, 'welcome', config_path)
    return arena_palette_delta(background, field, config_path, ARENA_FRONT_BASE_BANK)


def arena_combat_palette_delta(combat, config_path):
    """Validate the combat-backdrop delta. Pure config -- reads no ROM (see below)."""
    background, field = _arena_section_background(combat, 'combat', config_path)
    return arena_palette_delta(background, field, config_path, ARENA_BATTLE_BG_BASE_BANK)


# Composing a delta needs vanilla's words, and vanilla's words live in baserom.gba -- which
# CI does not have when it runs `make test` (the workflow mocks the ROM only later, for the
# link check). So COMPOSITION IS DEFERRED to build time and never happens during config load:
# arena_presentation_config() is consumed by dressed_portrait_slots() and friends, and making
# it touch the ROM took eleven unrelated portrait tests down with it.
def arena_welcome_palette_words(delta, vanilla=None):
    """Compose the welcome delta over the vanilla coliseum exterior -> 64 words."""
    return _compose(vanilla if vanilla is not None else vanilla_arena_front_palette(), delta)


def arena_combat_palette_words(delta, vanilla=None):
    """Compose the combat delta over vanilla's own three phases -> three 64-word phases."""
    vanilla = vanilla if vanilla is not None else vanilla_arena_battle_palettes()
    return {'background': [_compose(vanilla[phase], delta) for phase in 'ABC']}


def _portrait_face_id(slot):
    """Resolve a portrait asset stem to FE8's one-based FID from committed portrait_data.c."""
    source = vanilla_decomp_text('src/portrait_data.c')
    match = re.search(r'\{portrait_%s_tileset,.*?\},\s*//\s*(\d+)\s*$'
                      % re.escape(slot), source, re.M)
    if not match:
        sys.exit('ERROR: Arena attendant face_slot %r has no portrait_data.c entry' % slot)
    return int(match.group(1)) + 1


def arena_presentation_config(campaign):
    """Load optional campaign palette and chapter attendant overrides with vanilla fallbacks.

    Chapter YAML owns the source portrait and collision-free target slot. The returned chapter
    mapping is keyed by the hosted ROM slot consumed by gPlaySt.chapterIndex.
    """
    campaign_dir = os.path.join(REPO, 'campaigns', campaign)
    campaign_path = os.path.join(campaign_dir, 'campaign.yaml')
    with open(campaign_path, encoding='utf-8') as f:
        root = yaml_load(f) or {}
    campaign_cfg = root.get('arena_presentation') or {}
    if not isinstance(campaign_cfg, dict):
        sys.exit('ERROR: %s: arena_presentation must be a mapping' % campaign_path)

    host_by_number = {chapter.number: chapter.host_index for chapter in hosted_chapters()}
    chapters = {}
    chapter_dir = os.path.join(campaign_dir, 'chapters')
    for chapter_path in sorted(glob.glob(os.path.join(chapter_dir, 'ch*.yaml'))):
        with open(chapter_path, encoding='utf-8') as f:
            chapter = yaml_load(f) or {}
        section = chapter.get('arena_presentation') or {}
        if not section:
            continue
        if not isinstance(section, dict) or not isinstance(section.get('attendant'), dict):
            sys.exit('ERROR: %s: arena_presentation.attendant must be a mapping'
                     % chapter_path)
        attendant = section['attendant']
        portrait_rel = attendant.get('portrait')
        face_slot = attendant.get('face_slot')
        if not isinstance(portrait_rel, str) or not portrait_rel:
            sys.exit('ERROR: %s: arena_presentation.attendant.portrait must name a campaign '
                     'asset path' % chapter_path)
        if not isinstance(face_slot, str) or not face_slot:
            sys.exit('ERROR: %s: arena_presentation.attendant.face_slot must name a vanilla '
                     'portrait slot' % chapter_path)
        portrait_path = os.path.normpath(os.path.join(campaign_dir, portrait_rel))
        if os.path.commonpath((campaign_dir, portrait_path)) != campaign_dir:
            sys.exit('ERROR: %s: arena_presentation.attendant.portrait escapes the campaign: %s'
                     % (chapter_path, portrait_rel))
        if not os.path.isfile(portrait_path):
            sys.exit('ERROR: %s: arena_presentation.attendant.portrait not found: %s'
                     % (chapter_path, portrait_path))
        # inject_arena_attendant_portraits runs AFTER inject_portraits, so a slot the cast
        # already owns would be silently overwritten -- a green build with a stranger's face
        # on a player character. Ch05's Glen is free today; the next attendant needs proving.
        claimed = (set(PORTRAIT_MAP.values()) | set(GUEST_PORTRAIT_MAP.values())
                   | set(CH02_CHWINGA_PORTRAIT_SLOT.values())
                   | {slot for _mug, slot, _rc in CH05_VISIT_FACES.values()})
        if face_slot in claimed:
            sys.exit('ERROR: %s: Arena attendant face_slot %r is already dressed by the '
                     'campaign cast -- pick a slot no other portrait claims'
                     % (chapter_path, face_slot))
        number = chapter.get('chapter_number')
        if number not in host_by_number:
            sys.exit('ERROR: %s: chapter_number %r has no hosted ROM slot for its Arena '
                     'attendant override' % (chapter_path, number))
        host = host_by_number[number]
        chapters[host] = {
            'portrait_path': portrait_path,
            'face_slot': face_slot,
            'face_id': _portrait_face_id(face_slot),
            'chapter_path': chapter_path,
        }
    welcome = campaign_cfg.get('welcome')
    combat = campaign_cfg.get('combat')
    return {'campaign': campaign_cfg, 'campaign_path': campaign_path, 'chapters': chapters,
            'welcome_delta': (None if welcome is None
                              else arena_welcome_palette_delta(welcome, campaign_path)),
            'combat_delta': (None if combat is None
                             else arena_combat_palette_delta(combat, campaign_path))}


def arena_presentation_source(palette_words, chapter_faces):
    """Generated data/selectors consumed by the campaign-agnostic ArenaUi_Init hook."""
    lines = ['', '/* Build-generated optional Arena presentation bindings (#265). */']
    if palette_words is not None:
        if len(palette_words) != 64:
            sys.exit('ERROR: Arena presentation source needs exactly 64 palette words')
        lines += ['static CONST_DATA u16 gMSArenaBuildingFrontPalette[64] = {']
        for i in range(0, 64, 8):
            lines.append('    %s,' % ', '.join('0x%04X' % word
                                               for word in palette_words[i:i + 8]))
        lines.append('};')
    lines += ['', 'const u16 * GetArenaPresentationPalette(void)', '{']
    lines.append('    return %s;' % ('gMSArenaBuildingFrontPalette'
                                    if palette_words is not None
                                    else 'gPal_ArenaBuildingFront'))
    lines += ['}', '', 'int GetArenaPresentationFace(void)', '{']
    if chapter_faces:
        lines.append('    switch (gPlaySt.chapterIndex) {')
        for host, override in sorted(chapter_faces.items()):
            lines += ['    case %d:' % host, '        return 0x%02X;' % override['face_id']]
        lines += ['    }', '']
    lines += ['    return 0x67;', '}', '']
    return '\n'.join(lines)


def arena_battle_background_source(text, background_words):
    """Insert optional campaign palette phases into the Arena combat backdrop cycle."""
    if background_words is None:
        return text
    if len(background_words) != 3 or any(len(phase) != 64 for phase in background_words):
        sys.exit('ERROR: Arena battle background needs three 64-word palette phases')
    anchor = 'u16 * CONST_DATA PalArray_ArenaBattleBg[] =\n{\n'
    if text.count(anchor) != 1:
        sys.exit('ERROR: Arena battle palette array not in expected form')
    lines = ['/* Build-generated winter Arena battle backdrop palettes (#265). */']
    for suffix, phase in zip('ABC', background_words):
        lines.append('static CONST_DATA u16 gMSArenaBattleBgPalette%s[64] = {' % suffix)
        for i in range(0, 64, 8):
            lines.append('    %s,' % ', '.join('0x%04X' % word for word in phase[i:i + 8]))
        lines += ['};', '']
    text = text.replace(anchor, '\n'.join(lines) + '\n' + anchor, 1)
    vanilla = (anchor + '    Pal_ArenaBattleBg_A,\n'
               '    Pal_ArenaBattleBg_B,\n'
               '    Pal_ArenaBattleBg_C,\n')
    winter = (anchor + '    gMSArenaBattleBgPaletteA,\n'
              '    gMSArenaBattleBgPaletteB,\n'
              '    gMSArenaBattleBgPaletteC,\n')
    if text.count(vanilla) != 1:
        sys.exit('ERROR: Arena battle palette entries not in expected vanilla form')
    return text.replace(vanilla, winter, 1)


def inject_arena_presentation(campaign, verbose=True):
    """Append campaign/chapter Arena bindings after the generic engine hook is installed."""
    cfg = arena_presentation_config(campaign)
    words = (None if cfg['welcome_delta'] is None
             else arena_welcome_palette_words(cfg['welcome_delta']))
    with open(UIARENA_C, 'a', encoding='utf-8') as f:
        f.write(arena_presentation_source(words, cfg['chapters']))
    with open(os.path.join(DECOMP, 'src', 'banim-ekrarena.c'), encoding='utf-8') as f:
        battle_bg = f.read()
    phases = (None if cfg['combat_delta'] is None
              else arena_combat_palette_words(cfg['combat_delta'])['background'])
    with open(os.path.join(DECOMP, 'src', 'banim-ekrarena.c'), 'w', encoding='utf-8') as f:
        f.write(arena_battle_background_source(battle_bg, phases))
    if verbose:
        def changed(composed, vanilla):
            return sum(1 for a, b in zip(composed, vanilla) if a != b)
        print('  welcome=%s; combat backdrop=%s; attendant overrides=%s'
              % ('vanilla' if words is None
                 else '%d of 64 words over vanilla'
                      % changed(words, vanilla_arena_front_palette()),
                 'vanilla' if phases is None
                 else '%d of 64 words over vanilla, x3 phases'
                      % changed(phases[0], vanilla_arena_battle_palettes()['A']),
                 sorted(cfg['chapters'])))


def _vendor_mug_to_arena_bust(path):
    """Scale a standard FE-Repo mug's chibi to the counter-portrait envelope.

    Armoury, Vendor, Arena, and Secret Shop all paint only bust coordinates
    (24, 0)..(72, 48).  ArenaUi_Init positions that envelope inside its 64x64
    frame; feeding it a normal 96x80 bust draws through the frame even though
    the face engine itself clips nothing.  The FE-Repo 128x112 mug format carries
    its artist-authored 32x32 chibi at (96, 16).  Scale that mini-bust to the
    full 48x48 painted area used by every vanilla counter portrait instead of
    leaving a blank 8-pixel gutter or resampling the 96x80 talking frame.
    """
    source = _vendor_mug_to_bust(path)
    palette = source.getpalette()
    palette_index = {tuple(palette[i:i + 3]): i // 3 for i in range(0, 48, 3)}
    sheet = Image.open(path).convert('RGB')
    key = sheet.getpixel((0, 0))
    chibi_rgb = sheet.crop((96, 16, 128, 48)).resize(
        (48, 48), Image.Resampling.NEAREST)
    chibi = Image.new('P', (48, 48), 0)
    chibi.putpalette(palette)
    try:
        chibi.putdata([0 if pixel == key else palette_index[pixel]
                       for pixel in chibi_rgb.getdata()])
    except KeyError as exc:
        sys.exit('ERROR: %s chibi uses colour %r outside its 16-colour main-frame palette'
                 % (os.path.basename(path), exc.args[0]))
    bust = Image.new('P', (portrait_tool.BUST_W, portrait_tool.BUST_H), 0)
    bust.putpalette(palette)
    bust.paste(chibi, (24, 0))
    return bust
