"""On-map recruitment: talk recruits, parley recruiters, and custom-art pid wiring.
"""
import sys

from inject.cast import (
    char_symbol, class_enum_for, deploy_class_for, load_unit, PORTRAIT_MAP,
    SCRIPTED_NEUTRAL_SPRITES)
from inject.hosting import recruit_chapter_number
from inject.scenes import branch_on_check_alive


def assert_custom_art_pid_wired(pid, uid, where):
    """A chapter staging a unit that OWNS custom map art must stage it under a pid that wears it.

    `assert_declared_map_sprites_injected` cannot see this, and did not: it asks whether an ASSET
    reached some sprite table, and the white moose's did -- under ch04's pid. ch05 staged the same
    creature under a pid of its own (pids are per-chapter), that pid was in no override row, and
    `GetUnitSMSId` fell through to CLASS_GWYLLGI's stock hound. The asset was wired; this unit was
    not. Nothing between those two statements was being checked.

    So this is the per-PID half, called from the chapter injector that knows which pid it is
    using. Cheap, and it fails the BUILD rather than shipping a red dog (Nicolas, 2026-08-14).
    """
    for asset, char_ids, _donor in SCRIPTED_NEUTRAL_SPRITES:
        if asset != uid:
            continue
        if pid not in char_ids:
            sys.exit('ERROR: %s stages %r as pid %s, which wears no custom map sprite -- it '
                     'would render its stock CLASS sprite on the faction palette while the '
                     'committed art sits unused.\n'
                     '       Add %s to SCRIPTED_NEUTRAL_SPRITES\'s %r row (it already lists %s).'
                     % (where, uid, pid, pid, uid, ', '.join(char_ids)))
        return
    sys.exit('ERROR: %s asks whether pid %s wears %r, which is in no SCRIPTED_NEUTRAL_SPRITES '
             'row at all -- either the asset id is misspelled or the creature is cast (which '
             'goes through PORTRAIT_MAP instead)' % (where, pid, uid))


# A recruit placed GREEN on the map in its OWN recruit chapter (a Colm-style talk recruit,
# e.g. Trex: recruit.via == 'story') self-joins the blue party via CUSA when talked to, so it
# persists to the next chapter with no extra wiring. Every OTHER recruit joins OFF the map --
# a cutscene/market recruit, e.g. Baxby (recruit.via == 'market'), won over in a scene with no
# on-map unit -- so NOTHING puts it in the saved party. cast_available_at() only SIZES the
# deploy cap template (never LOADed), so an off-map recruit would silently be absent from the
# field until it gets an explicit between-chapter join-LOAD (#23). This is that discriminator.
ON_MAP_RECRUIT_VIA = ('story', 'talk')   # placed green + CUSA -> self-joins, persists naturally


def on_map_talk_recruits(campaign, chapter_number):
    """Cast members recruited MID-MAP via Talk IN `chapter_number` (the mirror of
    offmap_join_recruits): recruits whose recruit chapter IS this chapter and whose join
    method is an on-map talk (recruit.via in ON_MAP_RECRUIT_VIA). Returns
    [(unit_id, slot, class_enum, deploy_class_enum, level)] in PORTRAIT_MAP order. Each is
    placed GREEN and joined by a CHAR talk -> CUSA (the vanilla Colm/Neimi pattern, #23 item 2)."""
    out = []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        if recruit_chapter_number(campaign, unit) != chapter_number:
            continue   # not recruited in THIS chapter
        if (unit.get('recruit') or {}).get('via') not in ON_MAP_RECRUIT_VIA:
            continue   # off-map recruit -- joins via offmap_join_recruits, not an on-map talk
        out.append((unit_id, slot, class_enum, deploy_class_for(unit),
                    int(unit.get('fe_stats', {}).get('level', 1))))
    return out


def talk_recruit_char_entries(recruiters, target, flag, script):
    """One CHAR(flag, script, recruiter, target) per recruiter -- FE8's multi-recruiter talk
    idiom (cf. vanilla ch14a Rennac: two CHAR entries sharing a flag). All share flag + script
    + target, so ANY recruiter's talk recruits `target` and completing it sets the shared flag,
    disabling every entry (no re-trigger)."""
    return ''.join('    CHAR(%s, %s, %s, %s)\n' % (flag, script, r, target)
                   for r in recruiters)


def talk_recruit_script(msg_id, target, pre_script='', variant=None, label_base=0):
    """The shared talk-recruit script (cf. vanilla EventScr_Ch3_Talk_NeimiColm): show the
    migrated talk line, then CUSA `target` to BLUE (EvtChangeFaction), set the map-event
    visibility evbit, end. MUSS/STAL are trimmed -- the line rides the map talk window, not a
    fanfare. Faction-agnostic: a GREEN bystander (Trex/Basil) and a RED parley (Lupin/Sahnar)
    both end at BLUE via this one CUSA. `pre_script` is spliced in AFTER the talk line and
    BEFORE the CUSA -- a group parley passes its own conversion sweep there (ch04: the wolf
    pack, convert_survivors_green), so the whole outcome still rides the single recruit path.

    `variant` is (character, msg_id): the scene addresses a unit the player may never have
    recruited, so ask the roster and show the other copy when it is not there. The SHAPE is
    vanilla's own and is not invented here -- `ch14a-eventscript.h` branches on
    CHECK_ALIVE(CHARACTER_JOSHUA), Sahnar's donor and vanilla Ch5's optional Talk recruit,
    and picks a WHOLE MESSAGE per arm before converging:

        CHECK_ALIVE(CHARACTER_JOSHUA)
        BEQ(0xa, EVT_SLOT_C, EVT_SLOT_0)
        TEXTSHOW(0xa93) / TEXTEND / GOTO(0xb)
    LABEL(0xa)
        TEXTSHOW(0xa95) / TEXTEND
    LABEL(0xb)

    Only TEXTSHOW+TEXTEND go inside the arms. `TEXTSTART`, the `REMA` and above all the CUSA
    stay SHARED, exactly as ch14a shares everything past its LABEL -- a recruit duplicated into
    both arms is one recruit to fix twice.

    `label_base` offsets the branch's label PAIR. It exists because `pre_script` can carry
    labels of its own -- ch04's parley passes a `convert_survivors_green` sweep, one skip label
    per wolf -- and BEQ/GOTO scan the whole list for a matching LABEL, so a collision jumps into
    the wrong arm. ch04 sits at 0x40 and does not currently pass a `variant`, which is the only
    reason 0 is safe as a default; a caller doing both must move one of them."""
    beat = ('    TEXTSHOW(0x%X)\n'
            '    TEXTEND\n')
    return ('{\n'
            '    TEXTSTART\n'
            + (beat % msg_id if variant is None
               else branch_on_check_alive(variant[0], beat % msg_id, beat % variant[1],
                                          label_base=label_base))
            + '    REMA\n'
            + pre_script
            + '    CUSA(%s) /* -> blue: the talk recruits the target */\n'
              '    EVBIT_T(7)\n'
              '    ENDA\n}' % target)


def talk_recruit_wiring(recruiters, target, flag, script_symbol, msg_id, pre_script='',
                        variant=None, label_base=0):
    """Assemble the reusable on-map talk-recruit event wiring (ch03 Trex / ch04 Lupin / ch05
    Basil+Sahnar). Returns (char_events, talk_script):
      char_events -- the EventListScr_..._Character body: one CHAR(flag, script, recruiter,
        target) per `recruiters` entry (talk_recruit_char_entries). ch03 passes the whole
        field roster (talk_recruiters -- "any party member"); ch04 passes a single recruiter
        (the YAML parley.by, e.g. Marty) -- same machinery, caller picks the recruiter set.
      talk_script -- the shared talk script (talk_recruit_script) whose CUSA flips `target`
        BLUE, with `pre_script` spliced in before the CUSA (the red parley's pack conversion).
    Both flavours share ONE flow instead of a per-chapter green/red copy."""
    char_events = ('{\n' + talk_recruit_char_entries(recruiters, target, flag, script_symbol)
                   + '    END_MAIN\n}')
    return char_events, talk_recruit_script(msg_id, target, pre_script=pre_script,
                                           variant=variant, label_base=label_base)


def parley_recruiters(unit):
    """The recruiter set for a GATED talk recruit = ONLY the speaker the unit's own `parley.by`
    names, as a one-entry CHARACTER_ list for talk_recruit_wiring.

    The counterpart to talk_recruiters ("any core party member", ch03's Trex). A chapter picks
    between them; the wiring downstream is identical either way. Gated recruits are the ones
    whose fiction is carried by ONE character, so the recruiter is authored data rather than a
    roster query: ch04's Marty->Lupin (Nicolas 2026-07-21 -- the reveal centres Marty's creature
    diplomacy) and ch05's Basil->Sahnar (Sahnar does not weigh the argument, she RECOGNISES
    Basil -- lore/sahnar.md; anyone else gets the killing edge).

    `unit` is whatever dict carries the parley block -- ch04 hands it the convertible WAVE,
    ch05 the convertible ENEMY entry. Both are just "the thing being parleyed with", which is
    why this needs neither the campaign nor the chapter."""
    by = (unit.get('parley') or {})['by']
    if by not in PORTRAIT_MAP:
        sys.exit('ERROR: parley.by %r is not a cast member with a PORTRAIT_MAP slot -- a Talk '
                 'can only be initiated by a unit the engine can address' % by)
    return [char_symbol(PORTRAIT_MAP[by])]
