"""Cutscene beats: splitting a chapter's scripts into beats and emitting their events.

Also the scene-level branches (`variant_beat`, `branch_on_check_alive`), battle and defeat
quotes, and the chapter title card.
"""
import os
import subprocess
import sys

import fe8_talk_font
import gen_chapter_title
from inject.cast import PORTRAIT_MAP
from inject.decomp import BATTLEQUOTES_C, DECOMP
from inject.text import (
    _fe_dialogue_text, _fid_tag, _script_to_message, SCRIPT_DIRECTIVES, set_message_body)


def _beat_is_narration(beat):
    """True if every entry in a scenic beat is faceless `narration` stage-business."""
    real = [e for e in beat if next(iter(e)) not in SCRIPT_DIRECTIVES]
    return bool(real) and all('narration' in e for e in real)


def _scenic_beat_calls(msgs, beats, labels):
    """One event-script text call per scenic beat. A beat that is ALL faceless
    `narration` rides an opaque, auto-centered SOLOTEXTBOXSTART box (gProcScr_BoxDialogue,
    helpbox.c) so the aside is never boxless over the scene art (#58); EVT_SLOT_B =
    0x00FF00FF feeds x=y=0xFF -> auto-center (dialogue-box config flag 0x100, sub_800E31C).
    A beat with any faced speaker rides the normal talk window via Text() (TEXTSTART)."""
    out = []
    for msg, beat, lbl in zip(msgs, beats, labels):
        if _beat_is_narration(beat):
            out.append('    SVAL(EVT_SLOT_B, 0xFF00FF) /* auto-center the opaque solo box (#58) */\n'
                       '    SOLOTEXTBOXSTART\n'
                       '    TEXTSHOW(0x%X) /* %s */\n    TEXTEND\n    REMA\n' % (msg, lbl))
        else:
            out.append('    Text(0x%X) /* %s */\n' % (msg, lbl))
    return ''.join(out)


# so ch03+ reuse them instead of growing new copy-paste siblings. Pure string/file
# mechanics only -- everything chapter-specific rides in as an argument.

def _split_script_beats(script, card_required=True):
    """Split a locked chapter-YAML cutscene `script:` into (location_card, beats):
    entries accumulate into the current beat, `beat_break` sentinels start a new one,
    and the `location_card` rides out separately (card_required=False tolerates a
    script without one and returns card=None)."""
    if card_required:
        card = next(v for e in script for k, v in e.items() if k == 'location_card')
    else:
        card = next((v for e in script for k, v in e.items()
                     if k == 'location_card'), None)
    beats = [[]]
    for entry in script:
        (k, v), = entry.items()
        if k == 'location_card':
            continue
        if k == 'beat_break':
            beats.append([])
            continue
        beats[-1].append(entry)
    return card, beats


def _split_event_beats(chap, trigger, err_label, msg_ids=None, card_required=True):
    """Locate the chapter event with `trigger` and split its locked `script:` into
    (location_card, beats) (cf. _split_script_beats). Passing the scene's reserved
    `msg_ids` block guards the split against it -- a count mismatch means a
    beat_break drifted in the YAML and a zip would silently drop the extra."""
    ev = next((e for e in chap['events'] if e.get('trigger') == trigger), None)
    if ev is None:
        sys.exit('ERROR: %s: no %r event in the chapter YAML' % (err_label, trigger))
    card, beats = _split_script_beats(ev['script'], card_required=card_required)
    if msg_ids is not None and len(beats) != len(msg_ids):
        sys.exit('ERROR: %s split into %d beats; expected %d (check beat_break '
                 'markers in the YAML)' % (err_label, len(beats), len(msg_ids)))
    return card, beats


def split_on_stage_cut(script, where):
    """Split a cutscene script at its `stage_cut:` into (before, direction, after).

    One directive, two messages, and the second id is what a SCENE CHANGE costs. See
    SCRIPT_DIRECTIVES for why a `stage_break` cannot do this job.
    """
    cuts = [i for i, e in enumerate(script) if 'stage_cut' in e]
    if len(cuts) != 1:
        sys.exit('ERROR: %s needs exactly ONE `stage_cut:`; found %d' % (where, len(cuts)))
    i = cuts[0]
    before, after = script[:i], script[i + 1:]
    if not before or not after:
        sys.exit('ERROR: %s has a `stage_cut:` with nothing on one side of it -- a cut between '
                 'a beat and nothing is just the end of the beat' % where)
    return before, script[i]['stage_cut'], after


def _cutscene_fid(spk, special, err_label, fallback=None):
    """Speaker id -> face tag for a chapter cutscene: the chapter's `special` speakers
    first (guest slots, faceless `narration` -> None), then the PC PORTRAIT_MAP, then
    an optional `fallback` portrait map (e.g. GUEST_PORTRAIT_MAP) checked LAST."""
    if spk in special:
        return special[spk]
    if spk in PORTRAIT_MAP:
        return _fid_tag(PORTRAIT_MAP[spk].upper())
    if fallback and spk in fallback:
        return _fid_tag(fallback[spk].upper())
    sys.exit('ERROR: %s %r' % (err_label, spk))


def _make_fid(special, err_label, fallback=None):
    """A chapter's speaker->face function (a closure over _cutscene_fid), the shape
    _stage_beat/_emit_scene_beats consume."""
    def fid(spk):
        return _cutscene_fid(spk, special, err_label, fallback=fallback)
    return fid


def _stage_beat(beat, fid, home, overrides=None):
    """Podium staging for one scenic beat: speaker -> (podium, face tag). Speakers
    default to the mid-left podium; `home` anchors recurring speakers (quest-givers),
    `overrides` moves a speaker for this beat only; faces resolve through the
    chapter's fid function (cf. _cutscene_fid)."""
    ov = overrides or {}
    # Directives are stage business, not speakers: `fid('exits')` would die in _cutscene_fid as
    # an "unknown cutscene speaker" the first time a non-ch05 scene used one (review, 2026-08-14).
    # But the character a `present:`/`exits:` NAMES is staged like a speaker, and
    # _script_to_message refuses one with no podium -- so they are seated too.
    staged = [k for e in beat for k in e if k not in SCRIPT_DIRECTIVES]
    staged += [v for e in beat for k, v in e.items() if k in ('present', 'exits')]
    return {k: (ov.get(k, home.get(k, '[OpenMidLeft]')), fid(k)) for k in staged}


def _emit_scene_beats(lines, msg_ids, beats, fid, home, overrides=None,
                      preloads=None, width=None, trailings=None):
    """Write one message per scenic beat into texts.txt `lines` (see scene_beat_bodies)."""
    for msg_id, body in scene_beat_bodies(msg_ids, beats, fid, home, overrides=overrides,
                                          preloads=preloads, width=width, trailings=trailings):
        set_message_body(lines, msg_id, body)


def scene_beat_bodies(msg_ids, beats, fid, home, overrides=None,
                      preloads=None, width=None, trailings=None):
    """[(msg_id, body)], one message per scenic beat (staging via _stage_beat, body via
    _script_to_message) -- PURE, so `tools/scene_preview.py` reads the very bodies the
    injector writes. width=None picks per beat: faceless-narration beats ride
    the opaque, auto-centered SOLOTEXTBOXSTART box (#58) at SOLO_BOX_BUDGET_PX (helpbox.c
    clamps that box to 0xC0 while its text draws unclamped); faced beats take the talk
    bubble's TALK_BUDGET_PX. A fixed width overrides for scenes with no narration beats.
    `trailings` (parallel to beats) appends a raw text-code to a beat's body -- see
    _script_to_message's `trailing` (the single-face-exit fade)."""
    overrides = overrides or [None] * len(beats)
    preloads = preloads or [None] * len(beats)
    trailings = trailings or [None] * len(beats)
    if not (len(overrides) == len(preloads) == len(trailings) == len(beats)):
        sys.exit('ERROR: scene staging lists out of step with its %d beats '
                 '(%d overrides, %d preloads, %d trailings) for msgs %s' %
                 (len(beats), len(overrides), len(preloads), len(trailings), msg_ids))
    out = []
    for msg_id, beat, override, preload, trailing in zip(
            msg_ids, beats, overrides, preloads, trailings):
        # Faced scene beats render via _scenic_beat_calls -> Text() -> a TALK BUBBLE (PutTalkBubble),
        # NOT a full-screen box -- and a bubble line over 29 tiles hits the unclamped x = 29 - width
        # < 0 branch and overflows off the right edge (the ch03 crier "...pays fifty gold to whoever
        # cle|" bug). So faced beats take the talk bubble's pixel budget; narration keeps the
        # narrower one that fits the auto-centered SOLOTEXTBOXSTART.
        # width=None still picks PER BEAT, and the pair is not cosmetic: a faceless narration
        # beat rides the opaque auto-centered SOLOTEXTBOXSTART box, which helpbox.c clamps to
        # 0xC0 while its text draws unclamped. Only a FACED beat gets the talk bubble's budget.
        w = width if width is not None else (
            fe8_talk_font.SOLO_BOX_BUDGET_PX if _beat_is_narration(beat)
            else fe8_talk_font.TALK_BUDGET_PX)
        out.append((msg_id, _script_to_message(
            beat, _stage_beat(beat, fid, home, override), width=w, preload=preload,
            trailing=trailing)))
    return out


def midmap_minibosses(chap):
    """Enemy units in a loaded chapter flagged `is_miniboss` -- a mid-map miniboss whose
    DEFEAT fires a flagged death cutscene (the mirror of the boss's DefeatBoss win, but keyed
    to a tmp flag + a Misc AFEV rather than EVFLAG_DEFEAT_BOSS). Returns the enemy dicts in
    YAML order. ch03's Icewind Brute triggers the RBG-execution beat (#23 item 1)."""
    return [e for e in chap.get('enemy_units', []) if e.get('is_miniboss')]


def defeat_quote_row(pid, chapter_const, comment, msg=0, flag=None):
    """One gDefeatTalkList entry: `pid` falling in `chapter_const` shows `msg` and raises `flag`.

    SetPidDefeatedFlag raises the flag on ANY matching pid's death (no CA_BOSS gate,
    eventinfo.c) and DisplayDefeatTalkForPid shows `msg` only when nonzero, so the three shapes
    every chapter uses are one row: a silent flag (msg 0) lets a faceless unit drive an AFEV, a
    flagged quote is a boss line that also wins the chapter, and a flag-less quote is a line
    with no consequence -- the retreat of a unit who lives (vanilla's Seth precedent).
    `.chapter` is the HOST index, and the row must reach the HEAD of the list
    (`_prepend_defeat_quote`): the scan returns the first match."""
    msg_value = '0' if msg == 0 else '0x%X' % msg
    flag_line = '' if flag is None else '        .flag    = %s,\n' % flag
    return ('    {\n'
            '        .pid     = %s, /* %s */\n'
            '        .route   = CHAPTER_MODE_ANY,\n'
            '        .chapter = %s,\n'
            '%s'
            '        .msg     = %s,\n'
            '    },' % (pid, comment, chapter_const, flag_line, msg_value))


def battle_quote_body(speaker, lines, seating):
    """A one-speaker quote held to FE8's battle bubble (143px): every boss taunt and defeat
    line, and the death quotes that ride the same bubble. `lines` is one string per box and
    `seating` is the speaker's (seat, face tag) pair."""
    return _script_to_message([{speaker: line} for line in lines], {speaker: seating},
                              fe8_talk_font.BATTLE_QUOTE_BUDGET_PX)


def boss_quote_message(chap, trigger, speaker, face, msg_id, boxes, seat='[OpenMidLeft]'):
    """One locked boss quote -- the first-engagement taunt (`boss_battle`) or the defeat line
    (`boss_death`) -- rendered from the chapter's event at the battle bubble's 143px budget.

    `boxes` is the locked box count and a different count is a hard error: these ids are
    written straight into the boss's own rows (battle_quote_pair, defeat_quote_row), so an
    extra box would silently lengthen a line Nicolas signed off on. `seat` is the twin's own
    (vanilla's bosses mostly hold [OpenMidLeft] for both quotes)."""
    _card, beats = _split_event_beats(chap, trigger, '%s %s' % (chap['id'], trigger), (msg_id,),
                                      card_required=False)
    beat = beats[0]
    if len(beat) != boxes or any(next(iter(entry)) != speaker for entry in beat):
        sys.exit('ERROR: %s %s must remain %d locked %s box(es)'
                 % (chap['id'], trigger, boxes, speaker))
    return battle_quote_body(speaker, [entry[speaker] for entry in beat], (seat, _fid_tag(face)))


def battle_quote_pair(pid, chapter_const, msg, comment, flag='EVFLAG_BATTLE_QUOTES'):
    """The two gBattleTalkList rows that give `pid` a first-engagement line in `chapter_const`.

    FE8's mid-fight boss line is a PAIR, and shipping one row is the easy half-wiring.
    `CallBattleQuoteEventsIfAny` (eventinfo.c) is handed (attacker, defender) and asks
    `GetBattleQuoteEntry` for (A,B), then (A,0), then (0,B) -- so a row keyed on the boss as
    pidA fires when the boss swings, and a row keyed on it as pidB (behind the
    CHAR_EVT_PLAYER_LEADER sentinel, which is literally 0) fires when the player does. Vanilla
    writes both for every boss it gives a taunt: O'Neill, Breguet, Bone, Bazba, Saar.

    Both rows carry the SAME flag deliberately. The scan skips any entry whose flag is already
    set, so whichever side fires first retires the other; two flags would let the line play
    twice. `.chapter` must be the HOST index (it is compared against gPlaySt.chapterIndex), and
    the entries belong at the head of the list for the same first-match reason the defeat
    quotes do."""
    return ('    {\n'
            '        .pidA     = CHAR_EVT_PLAYER_LEADER,\n'
            '        .pidB     = %s, /* %s */\n'
            '        .chapter = %s,\n'
            '        .flag    = %s,\n'
            '        .msg     = 0x%X,\n'
            '    },\n'
            '    {\n'
            '        .pidA     = %s, /* the same line when they swing first */\n'
            '        .chapter = %s,\n'
            '        .flag    = %s,\n'
            '        .msg     = 0x%X,\n'
            '    },' % (pid, comment, chapter_const, flag, msg,
                        pid, chapter_const, flag, msg))


def _prepend_defeat_quote(quote):
    """Prepend an entry at the HEAD of gDefeatTalkList (battlequotes.c): the head entry
    wins GetDefeatTalkEntry's first-match scan, shadowing any vanilla entry for the
    same pid further down (the shadowing rule debriefed in inject_prologue step 5)."""
    with open(BATTLEQUOTES_C, encoding='utf-8') as f:
        bq = f.read()
    head = 'CONST_DATA struct DefeatTalkEnt gDefeatTalkList[] = {\n'
    if bq.count(head) != 1:
        sys.exit('ERROR: gDefeatTalkList head not in expected form in %s'
                 % BATTLEQUOTES_C)
    bq = bq.replace(head, head + quote + '\n')
    with open(BATTLEQUOTES_C, 'w', encoding='utf-8') as f:
        f.write(bq)


def _prepend_battle_quote(entries):
    """Prepend `entries` at the HEAD of gBattleTalkList (battlequotes.c) -- the mid-fight
    line list, whose rows come from battle_quote_pair(). GetBattleQuoteEntry scans first-match
    exactly like the defeat list, so the head wins over any vanilla row for the same pid in
    the same chapter."""
    with open(BATTLEQUOTES_C, encoding='utf-8') as f:
        bq = f.read()
    head = 'CONST_DATA struct BattleTalkExtEnt gBattleTalkList[] = {\n'
    if bq.count(head) != 1:
        sys.exit('ERROR: gBattleTalkList head not in expected form in %s'
                 % BATTLEQUOTES_C)
    bq = bq.replace(head, head + entries + '\n')
    with open(BATTLEQUOTES_C, 'w', encoding='utf-8') as f:
        f.write(bq)


def _write_chapter_title_card(host, title):
    """Compose the chapter's title-card banner (the intro/status banner is a 4bpp image, not
    text) and CONVERT it ourselves, rather than deleting the intermediates and trusting make.

    This used to delete `chap_title_N.4bpp{,.lz}` "so make re-converts". make does not: the
    incbin dependency reaches `data/data_chap_title.o` through `$$(data_dep)` -- a
    `$(shell scaninc ...)` target-specific variable resolved by `.SECONDEXPANSION` -- and GNU
    Make **3.81**, which is what Apple ships and what this repo builds with, drops it. Verified
    directly: with the .lz deleted, `make -n fireemblem8.gba` plans no rule that rebuilds it.

    That has two consequences and neither announces itself (this is #245's actual root cause,
    which was filed as a "TESTCH build race" -- it is not a race, and it is not TESTCH's):
      1. When `data_chap_title.o` DOES need reassembling, the build dies on
         `Error: file not found: graphics/chap_title/chap_title_N.4bpp.lz`.
      2. When it does NOT -- the common case, since its .s never changes -- the build succeeds
         and the ROM silently keeps the PREVIOUS card. A retitled chapter just never lands.

    So: run the same two gbagfx conversions the Makefile would have, then drop the .o so the
    new bytes are actually assembled in. Deterministic, and independent of the make version.
    """
    title_png = os.path.join(DECOMP, 'graphics', 'chap_title',
                             'chap_title_%d.png' % host['chapTitleId'])
    gen_chapter_title.compose_title(title).save(title_png)
    gbagfx = os.path.join(DECOMP, 'tools', 'gbagfx', 'gbagfx')
    if not os.path.exists(gbagfx):
        # A fresh checkout has no helper tools -- tools/setup-toolchain.sh omits upstream's
        # build_tools.sh (HANDOFF). Say so, rather than raising FileNotFoundError on a path.
        sys.exit('ERROR: %s is missing -- a fresh checkout needs the decomp helper tools:\n'
                 '  (cd fireemblem8u && ./build_tools.sh)' % gbagfx)
    four_bpp, lz = title_png[:-4] + '.4bpp', title_png[:-4] + '.4bpp.lz'
    for src, dst in ((title_png, four_bpp), (four_bpp, lz)):
        subprocess.run([gbagfx, src, dst], cwd=DECOMP, check=True)
    # The incbin dependency is dropped, so a fresh .lz alone would sit there unread.
    chap_title_o = os.path.join(DECOMP, 'data', 'data_chap_title.o')
    if os.path.exists(chap_title_o):
        os.remove(chap_title_o)


def variant_beat(beat, fallback, err_label):
    """Splice a scene's `no_lupin_fallback`-style variant over its locked beat.

    A chapter YAML declares the fallback as `boxes:` (1-based indices), `replaces:` (the
    OPENING TEXT of each box it stands in for) and a `script:` of the substitute lines --
    one per box, in the same order. The `replaces:` anchors exist so an index cannot
    silently drift: we assert each named box still starts with its anchor before swapping,
    and hard-fail if the locked script has been re-ordered underneath the fallback.

    A `script:` entry may be a LIST of boxes rather than one, and then the named box is
    replaced by all of them. A substitute chosen as prose can simply be too long for the
    channel it lands in -- ch05's on-map fallbacks were, at the old 29 -- and the
    author has to place the extra A-press, because a wrapper left to choose it puts the page
    break mid-clause. `boxes:`/`replaces:`/`script:` still agree one-for-one; only the
    substitute is plural, which is what keeps this one mechanism rather than two.

    OMIT `script:` ENTIRELY and every named box is DROPPED. Some variants are a cut rather
    than a substitution -- ch05's ending loses its whole berry exchange when Sahnar was never
    recruited -- and a cut authored as six empty substitutes would say the same thing far
    worse. The `replaces:` anchors still apply and still assert, which is the point: a drop is
    the one edit where getting the index wrong is invisible in the output, because the result
    is simply a shorter scene that still reads.

    Returns a new beat with the named boxes replaced and every other box (e.g. ch04's Marty
    box 2, unchanged in both branches) carried through. It is the SAME LENGTH as `beat` only
    when every substitute is singular -- two arms of a branch are not required to cost the
    same number of A-presses, only to each stand up.

    Reused by ch05's conditional scenes (#25) -- one mechanism, not two.
    """
    boxes, anchors = fallback['boxes'], fallback['replaces']
    subs = fallback.get('script')
    if subs is None:                       # a CUT: every named box goes, nothing takes its place
        subs = [[] for _ in boxes]
        if len(boxes) != len(anchors):
            sys.exit('ERROR: %s: cut declares %d boxes and %d replaces -- the anchors are what '
                     'keeps a drop honest, so there must be one per box'
                     % (err_label, len(boxes), len(anchors)))
    elif not (len(boxes) == len(anchors) == len(subs)):
        sys.exit('ERROR: %s: fallback declares %d boxes, %d replaces, %d script lines '
                 '-- all three must agree' % (err_label, len(boxes), len(anchors), len(subs)))
    # `boxes:` are A-PRESS numbers, not list positions, and a script may carry stage directions
    # (`exits:` and friends) that are not boxes. Map one to the other rather than indexing the
    # raw list: without this, a directive added ABOVE a fallback silently shifts every index
    # past it -- caught by the anchor assertion below, but as a confusing "the locked script
    # moved" rather than the truth.
    positions = [i for i, e in enumerate(beat) if next(iter(e)) not in SCRIPT_DIRECTIVES]
    # Resolve every substitution against the ORIGINAL beat first and splice afterwards. Editing
    # in place would move every box after a plural substitute, so a later `boxes:` index would
    # land one short and the anchor assertion would blame the locked script for moving.
    replacement = {}
    for idx, anchor, sub in zip(boxes, anchors, subs):
        if not 1 <= idx <= len(positions):
            sys.exit('ERROR: %s: fallback box %d is outside the %d-box scene'
                     % (err_label, idx, len(positions)))
        at = positions[idx - 1]
        (_, text), = beat[at].items()
        if not _fe_dialogue_text(text).startswith(_fe_dialogue_text(anchor)[:40]):
            sys.exit('ERROR: %s: fallback box %d anchored to %r but that box now reads %r '
                     '-- the locked script moved; re-anchor the fallback'
                     % (err_label, idx, anchor[:40], text[:40]))
        replacement[at] = sub if isinstance(sub, list) else [sub]
    out = []
    for i, entry in enumerate(beat):
        out.extend(replacement.get(i, [entry]))
    return out


def _branch_on_slot_c(test, if_true, if_false, label_base, why):
    """The event-branch SKELETON both campaign branches share, parameterised by its test.

    Every FE8 conditional of this shape works the same way: some CHECK_* leaves a 0/1 in slot C,
    BEQ jumps to the fallback arm when it equals slot 0, the true arm GOTOs past that arm, and
    both converge on a shared LABEL. Only the CHECK_ line differs between "is this flag set" and
    "is this unit on the roster", so only that line is a parameter -- two skeletons would be two
    mechanisms to keep in step. `label_base` offsets the pair so several branches can coexist in
    one script without colliding.
    """
    a, b = label_base, label_base + 1
    return ('    %s\n'
            '    BEQ(0x%X, EVT_SLOT_C, EVT_SLOT_0) /* %s -> the fallback arm */\n'
            % (test, a, why)
            + if_true
            + '    GOTO(0x%X)\n'
              'LABEL(0x%X)\n' % (b, a)
            + if_false
            + 'LABEL(0x%X)\n' % b)


def branch_on_check_alive(character, if_alive, if_absent, label_base=0):
    """The same branch, asking the ROSTER instead of a flag: is this unit ours and alive?

    ch05's conditional scenes address units the player may never have recruited, and this is
    vanilla's own answer for that question rather than a flag we would have to carry across a
    chapter boundary: `ch14a-eventscript.h` branches its ending on CHECK_ALIVE(CHARACTER_JOSHUA)
    three times, Joshua being vanilla Ch5's optional Talk recruit and Sahnar's exact donor.

    Two properties make it the right test and not merely a convenient one:
      * `eventscr.c` (:3212) writes slot C = 0 when the unit is NOT FOUND AT ALL as well as when
        it is `US_DEAD`, so never-recruited and recruited-then-killed collapse into one arm --
        which is what the prose wants, a dead Lupin being no more "out there now, with travelers"
        than one who was never won;
      * it reads the roster, NOT the field. ch05 deploys 9 of a 10-unit pool, so a recruited
        Lupin can be alive and benched; `EVSUBCMD_CHECK_DEPLOYED` exists separately for exactly
        this distinction and vanilla uses ALIVE for dialogue.
    """
    return _branch_on_slot_c('CHECK_ALIVE(%s)' % character, if_alive, if_absent,
                             label_base, 'not on the roster, or dead')
