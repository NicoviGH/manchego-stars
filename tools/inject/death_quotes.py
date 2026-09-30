"""Player-character death quotes (#6).
"""
import sys

import fe8_talk_font
from inject.cast import classed_cast, load_unit
from inject.paths import TEXTS_TXT
from inject.scenes import _prepend_defeat_quote
from inject.text import _fid_tag, _script_to_message, set_message_body


# Per-PC death quotes (#6, dialogue pass 2026-06-17): one universal dying line per
# deployable cast member, shown with their bust when they fall in ANY chapter. Each
# rides a dead slot-2 message id: 0x94D-0x953 are Ch1-tutorial ids (stripped by the
# prologue host); pinky's 0x958 is a vanilla Ch2 scene id, dead because inject_ch01
# replaces the slot-2 events; trex's 0x965 is the Ephraim/Eirika training-flashback
# tutorial scene, and baxby's 0x93E is the "visit a home / place the cursor" Ch1 cursor
# tutorial -- both dead the same way the prologue host strips the FE8 tutorial path.
# All vetted unreferenced elsewhere -> safe campaign-wide.
# Keyed by cast unit_id; the PC rides its PORTRAIT_MAP slot, so pid/FID = CHARACTER_<slot>.
PC_DEATH_QUOTE_MSGS = {
    'braulo':     0x94D,
    'marty':      0x94E,
    'wolfram':    0x94F,
    'meesmickle': 0x950,
    'prof-rbg':   0x951,
    'rootis':     0x952,
    'sclorbo':    0x953,
    'pinky':      0x958,
    'trex':       0x965,
    'baxby':      0x93E,
    'lupin':      0x974,   # dead vanilla slot (no TEXTSHOW/.msg ref). TODO(#24): auto-allocate
                           # death-quote ids from a free pool so new recruits need only YAML.
    # ch05's pair (#25), picked the same way and from the same neighbourhood as Lupin's: dead
    # vanilla TUTORIAL bodies (0x97A "Now select Staff and press...", 0x97B "Ross has been
    # rescued...") that no TEXTSHOW, .msg or .msgId reaches. The audit that found them excludes
    # include/constants/msg.h, which #defines EVERY id and so marks every slot "referenced",
    # and ignores bare-hex matches, which collide with unrelated addresses -- Lupin's own 0x974
    # fails both of those looser tests while being genuinely free, which is the control.
    'basil':      0x97A,
    'sahnar':     0x97B,
}


def pc_death_quote_rows(campaign):
    """Every gDefeatTalkList row the death-quote pass writes, IN SCAN ORDER.

    ONE row per cast member, and that is a decision rather than a limitation: FE8 lets a pid
    hold a chapter-keyed row ahead of its chapter=0xFF one, and ch05 briefly gave Basil a
    second box on vanilla's escort pattern before it was cut for saying the same thing twice
    (decisions.md -> "One death quote per character"). A pid with two rows would be decided
    here and nowhere else -- GetDefeatTalkEntry returns the first match -- so if that call is
    ever revisited, the ordering belongs in this function and not in a chapter injector, which
    runs BEFORE this pass and would prepend its row behind these.
    """
    rows = []
    for unit_id, slot, _, _ in classed_cast(campaign):
        if unit_id not in PC_DEATH_QUOTE_MSGS:
            sys.exit('ERROR: no death-quote msg id allocated for cast member %r' % unit_id)
        rows.append(
            '    {\n'
            '        .pid     = CHARACTER_%s, /* %s death quote (#6, any chapter) */\n'
            '        .route   = CHAPTER_MODE_ANY,\n'
            '        .chapter = 0xFF, /* fires in every chapter */\n'
            '        .msg     = 0x%04X,\n'
            '    },' % (slot.upper(), unit_id, PC_DEATH_QUOTE_MSGS[unit_id]))
    return rows


def inject_pc_death_quotes(campaign, verbose=True):
    """Universal per-PC death quotes (#6): when a deployable cast member falls, FE8's
    gDefeatTalkList machinery (DisplayDefeatTalkForPid, eventinfo.c) shows their dying
    line with their bust -- exactly the vanilla player-death-quote path (cf. Natasha
    MSG_9C6, Forde MSG_9DC). Entries go at the HEAD of the list (GetDefeatTalkEntry
    returns the first pid match) with route=ANY, chapter=0xFF and no flag, so they fire
    in EVERY chapter. Each PC rides its PORTRAIT_MAP slot, so pid + face = CHARACTER_<slot>
    / [FID_<slot>]. Quote text lives in the unit YAML (`death_quote`); bodies render via
    _script_to_message with the bust on the left podium, like the boss death quotes."""
    # 1. Text bodies (each quote in a map talk box with the faller's bust, left podium).
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for unit_id, slot, _, _ in classed_cast(campaign):
        unit = load_unit(campaign, unit_id)
        quote = unit.get('death_quote')
        if not quote:
            sys.exit('ERROR: %s YAML has no death_quote (#6 requires one per cast member)'
                     % unit_id)
        set_message_body(lines, PC_DEATH_QUOTE_MSGS[unit_id], _script_to_message(
            [{unit_id: quote}], {unit_id: ('[OpenMidLeft]', _fid_tag(slot))}, width=fe8_talk_font.BATTLE_QUOTE_BUDGET_PX))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    # 2. Prepend the entries at the head of gDefeatTalkList (same idiom as the boss
    #    quotes; distinct pids, so ordering vs. those is immaterial).
    rows = pc_death_quote_rows(campaign)
    _prepend_defeat_quote('\n'.join(rows))
    if verbose:
        print('  death quotes: %d cast members (chapter=any)' % len(rows))
