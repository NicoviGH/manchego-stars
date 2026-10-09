"""Campaign sound effects: vendored one-shot samples appended to gSongTable as NEW song ids.

FE8 and the GBA Pokemon games share the m4a (MP2K) sound engine, so a cry from pokeemerald is
already in the format FE8 plays: 8-bit signed PCM with a 16-byte header. A sound effect is four
appended pieces, and none of them edits a vanilla row:

  1. the SAMPLE    -- the committed .aif is copied into sound/direct_sound_samples/ and the
                      decomp's own rule (`sound/%.bin: sound/%.aif`, aif2pcm) builds its .bin;
  2. its DATA      -- a DirectSoundData_<stem> incbin, appended to direct_sound_data.s;
  3. the SONG      -- a one-voice voicegroup and a one-note track, appended to the same file:
                      base key 60 played at Cn3, so the sample sounds at the rate it was
                      recorded at;
  4. the TABLE ROW -- appended to gSongTable, so its id is the table's length at inject time,
                      and named in songs.h for event scripts (`SOUN(SONG_MS_*)`).

Everything rides files the linker script already lists (song_table.o, direct_sound_data.o), so
no new object needs placing. Long form: decisions.md -> "Custom sound effects append to
gSongTable".
"""
import os
import re
import shutil
import sys

from inject.decomp import REPO
from inject.paths import DIRECT_SOUND_DATA_S, SONG_TABLE_S, SONGS_H, SOUND_SAMPLE_DIR


# (enum name, sample stem, credit). The stem names campaigns/<c>/sounds/<stem>.aif.
CAMPAIGN_SOUNDS = [
    # ch06: Messie surfaces (#26). Kyogre's cry from Pokemon Ruby/Sapphire/Emerald, staged the
    # way Sapphire's Cave of Origin stages Kyogre's awakening (Nicolas, 2026-10-09).
    ('SONG_MS_KYOGRE_CRY', 'ms_kyogre_cry', '{Game Freak; pret/pokeemerald cries/kyogre.wav}'),
]

# The music player a sound plays on. 6 is where vanilla's monster cries and battle effects sit
# (song814_mon_gar_critical1, the ch05 moose's mon_mdg_critical1), so a cry neither stops the
# chapter's music nor is cut off by a menu blip.
SFX_PLAYER = 6

_TABLE_ROW = re.compile(r'^\tsong \w+, \d+, \d+$', re.M)


def song_table_length(song_table_s):
    """Rows in gSongTable. The table index IS the song id, so this is the next free id."""
    return len(_TABLE_ROW.findall(song_table_s))


def sound_asm(stem):
    """The sample's data label, its voicegroup and its one-note song, as appended assembly."""
    return ('\n\t.align 2\n\t.global DirectSoundData_%(s)s\nDirectSoundData_%(s)s:\n'
            '\t.incbin "sound/direct_sound_samples/%(s)s.bin"\n'
            '\n\t.align 2\n\t.global voicegroup_%(s)s\nvoicegroup_%(s)s:\n'
            '\tvoice_directsound 60, 0, DirectSoundData_%(s)s, 255, 0, 255, 0\n'
            '\n\t.align 2\n\t.global song_%(s)s_1\nsong_%(s)s_1:\n'
            '\t.byte\tKEYSH\t, 0\n'
            '\t.byte\tTEMPO\t, 60\n'
            '\t.byte\tVOICE\t, 0\n'
            '\t.byte\tVOL\t, v127\n'
            '\t.byte\t\tN96\t, Cn3, v127\n'
            '\t.byte\tW96\n'
            '\t.byte\tFINE\n'
            '\n\t.align 2\n\t.global song_%(s)s\nsong_%(s)s:\n'
            '\t.byte\t1\t@ trackCount\n'
            '\t.byte\t0\t@ blockCount\n'
            '\t.byte\t20\t@ priority\n'
            '\t.byte\t0\t@ reverb\n'
            '\t.word\tvoicegroup_%(s)s\n'
            '\t.word\tsong_%(s)s_1\n' % {'s': stem})


def inject_sounds(campaign, verbose=True):
    """Append the campaign's sound effects (module docstring). Idempotent: the three patched
    files are in PATCHED_DECOMP_FILES and restored from HEAD every build."""
    src_dir = os.path.join(REPO, 'campaigns', campaign, 'sounds')
    with open(SONG_TABLE_S, encoding='utf-8') as f:
        table = f.read()
    first = song_table_length(table)
    rows, asm, enums = [], [], []
    for i, (enum_name, stem, _credit) in enumerate(CAMPAIGN_SOUNDS):
        src = os.path.join(src_dir, stem + '.aif')
        if not os.path.isfile(src):
            sys.exit('ERROR: campaign sound source missing: %s' % src)
        dst = os.path.join(SOUND_SAMPLE_DIR, stem + '.aif')
        shutil.copyfile(src, dst)
        if os.path.exists(dst[:-4] + '.bin'):
            os.remove(dst[:-4] + '.bin')
        rows.append('\tsong song_%s, %d, %d' % (stem, SFX_PLAYER, SFX_PLAYER))
        asm.append(sound_asm(stem))
        enums.append('    %s = 0x%X,' % (enum_name, first + i))
    with open(SONG_TABLE_S, 'w', encoding='utf-8') as f:
        f.write(table.rstrip('\n') + '\n' + '\n'.join(rows) + '\n')
    with open(DIRECT_SOUND_DATA_S, encoding='utf-8') as f:
        data = f.read()
    with open(DIRECT_SOUND_DATA_S, 'w', encoding='utf-8') as f:
        # The track macros (MPlayDef.s) and voice macros are included ONCE: a second include
        # would redefine every equate.
        f.write(data + '\n\t.include "MPlayDef.s"\n\t.include "asm/macros/music_voice.inc"\n'
                + ''.join(asm))
    with open(SONGS_H, encoding='utf-8') as f:
        h = f.read()
    anchor = next((ln for ln in h.splitlines() if ln.strip().startswith('SONG_SILENT')), None)
    if anchor is None or h.count(anchor) != 1:
        sys.exit('ERROR: SONG_SILENT enum anchor not unique in %s' % SONGS_H)
    with open(SONGS_H, 'w', encoding='utf-8') as f:
        f.write(h.replace(anchor, '\n'.join(enums) + '\n' + anchor, 1))
    if verbose:
        print('  %d campaign sound(s) -> gSongTable[0x%X..] (additive)'
              % (len(CAMPAIGN_SOUNDS), first))
