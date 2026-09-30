"""Message-id ownership: who spends which vanilla message id, and the guards on it.

The registries here are DISCOVERED from the injector's own `*_MSG`/`*_PIDS` constants,
across every module (`inject.namespace`), so registering an id is naming it.
"""
import collections
import os
import re
import sys

from inject.namespace import injector_constants
from inject.cast import RAW_PID_PORTRAITS
from inject.chapter_ids import (
    CH01_GOAL_STATUS_MSG, CH01_GOAL_WINDOW_MSG, CH01_LITERAL_MSGS, CH02_GOAL_STATUS_MSG,
    CH02_GOAL_WINDOW_MSG, CH02_TURN1_MSGS, CH02_VILLAGE_SLOTS, CH03_BOSS_DEATH_MSG,
    CH03_ENDING_CARD_MSG, CH03_ENDING_MSGS, CH03_GOAL_STATUS_MSG, CH03_GOAL_WINDOW_MSG,
    CH03_MIDMAP_MSGS, CH03_OPENING_CARD_MSG, CH03_OPENING_MSGS, CH03_TREX_ENTRANCE_MSG,
    CH03_TREX_TALK_MSG, CH04_COTTAGE_MSG, CH04_ENDING_MSG, CH04_ENDING_NO_LUPIN_MSG,
    CH04_GOAL_STATUS_MSG, CH04_GOAL_WINDOW_MSG, CH04_LUPIN_TALK_MSG, CH04_MOOSE_MSG,
    CH04_OPENING_CARD_MSG, CH04_OPENING_MSGS, CH04_REVEAL_MSGS, CH04_VILLAGE_MSG,
    CH05_ARENA_FOUND_MSG, CH05_ARENA_RULES_MSG, CH05_ARRIVAL_NO_LUPIN_MSG, CH05_ARRIVAL_SLOT,
    CH05_BASIL_JOIN_NO_LUPIN_MSG, CH05_BASIL_JOIN_SLOT, CH05_ENDING_LOST_MSG, CH05_ENDING_MSGS,
    CH05_ERUPTION_MSG, CH05_GOAL_STATUS_MSG, CH05_GOAL_WINDOW_MSG, CH05_MOOSE_CHARGE_SLOT,
    CH05_MOOSE_NAME_MSG, CH05_MOOSE_QUIP_MSG, CH05_OPENING_SLOTS, CH05_RAVISIN_DEATH_MSG,
    CH05_RAVISIN_TAUNT_MSG, CH05_SAHNAR_ALONE_SLOT, CH05_SAHNAR_TALK_MSG,
    CH05_SAHNAR_TALK_NO_LUPIN_MSG, CH05_VILLAGE_SLOTS, CH06_BOAT_NAME_MSGS, CH06_GOAL_STATUS_MSG,
    CH06_GOAL_WINDOW_MSG, PROLOGUE_LITERAL_MSGS)
from inject.decomp import REPO
from inject.hosts import literal_message_ids


HOSTED_CHAPTER_MESSAGE_IDS = {
    'ch00': PROLOGUE_LITERAL_MSGS,
    'ch03': (CH03_BOSS_DEATH_MSG,        # reserved: the grell's quote was CUT (msg=0) but the
                                         # slot stays ch03's, so nothing else may take it
             CH03_TREX_TALK_MSG, CH03_OPENING_CARD_MSG, *CH03_OPENING_MSGS,
             CH03_ENDING_CARD_MSG, *CH03_ENDING_MSGS, CH03_TREX_ENTRANCE_MSG,
             *CH03_MIDMAP_MSGS, CH03_GOAL_WINDOW_MSG, CH03_GOAL_STATUS_MSG),
    'ch04': (CH04_LUPIN_TALK_MSG, *CH04_REVEAL_MSGS, CH04_OPENING_CARD_MSG,
             *CH04_OPENING_MSGS, CH04_MOOSE_MSG, CH04_ENDING_MSG,
             CH04_ENDING_NO_LUPIN_MSG, CH04_VILLAGE_MSG, CH04_COTTAGE_MSG,
             CH04_GOAL_WINDOW_MSG, CH04_GOAL_STATUS_MSG),
    # ch05 hosts on slot 6, so it takes vanilla CH6's dead block (0x9E4..0x9F5) -- NOT vanilla
    # Ch5's, even though ch05 is vanilla Ch5's 1:1 twin in every other respect. ch04 sits on
    # slot 5 and already owns that block. This is the sharpest case of the two offsets: the
    # chapter we MINE and the block we WRITE INTO are different vanilla chapters, and the
    # YAML's `slot: "vanilla 0x9BB"` labels are anatomy references to the mined chapter, not
    # claims on ids. The eruption warning is the first dialogue claim from that block; later
    # cutscene ids land with the remaining dialogue pass (#25), and this guard will refuse them
    # if any collide.
    # The four reliquary visit lines joined the block 2026-08-08 (dialogue-pass). They sit
    # OUTSIDE ch05's host block on purpose -- see CH05_VILLAGE_SLOTS for why that is safe here
    # and why spending ch05's own ids on them was the worse trade.
    'ch05': (CH05_ERUPTION_MSG, CH05_RAVISIN_DEATH_MSG, CH05_RAVISIN_TAUNT_MSG,
             CH05_ARENA_FOUND_MSG, CH05_ARENA_RULES_MSG,
             CH05_SAHNAR_TALK_MSG, CH05_SAHNAR_TALK_NO_LUPIN_MSG,
             *(msg for _slot, msg, _boxes, _what in CH05_OPENING_SLOTS),
             CH05_ARRIVAL_SLOT[1], CH05_ARRIVAL_NO_LUPIN_MSG,
             CH05_BASIL_JOIN_SLOT[1], CH05_BASIL_JOIN_NO_LUPIN_MSG,
             CH05_SAHNAR_ALONE_SLOT[1], CH05_MOOSE_CHARGE_SLOT[1],
             CH05_MOOSE_QUIP_MSG,
             # The two endings (#25). Scene 16 takes the four ids vanilla spends on its OWN
             # ending block, which is the scene we mine -- swept free because everything that
             # reaches them lives in ch5-eventscript.h, which inject_ch04 rewrites. Scene 17
             # takes the host block's last free id plus one appended past MSG_D4B.
             *CH05_ENDING_MSGS.values(), CH05_ENDING_LOST_MSG,
             # The moose's NAME -- appended past vanilla's last id rather than taken from a
             # donor, so it is claimed here like any other id ch05 writes.
             CH05_MOOSE_NAME_MSG,
             CH05_GOAL_WINDOW_MSG, CH05_GOAL_STATUS_MSG,
             *(slot[1] for slot in CH05_VILLAGE_SLOTS.values())),
    # ch06 hosts on slot 7 and takes vanilla CH7's dead block -- not vanilla Ch6's, which ch05
    # already owns from slot 6. The chapter it MINES (FE8 Ch6, its parity bar) and the chapter
    # whose ids it WRITES INTO are two chapters apart here, which is the offset stated once in
    # the CH06_* constant block. Only the goal pair is spent today: ch06's scenes are declared
    # with empty text on purpose and the dialogue pass claims the rest of the run.
    'ch06': (CH06_GOAL_WINDOW_MSG, CH06_GOAL_STATUS_MSG,
             # the two boats' name plates -- appended past vanilla's last id rather than taken
             # from a donor, so they are claimed here like any other id ch06 writes
             *CH06_BOAT_NAME_MSGS.values()),
    # Goal ids only -- ch01/ch02 predate the per-chapter block registry, but their goal strings
    # still have to be unique against every other hosted chapter (#207).
    'ch01': (*CH01_LITERAL_MSGS, CH01_GOAL_WINDOW_MSG, CH01_GOAL_STATUS_MSG),
    # The goal window/status predate the block registry and sit outside it; the two Targos
    # hut visits are ch02's first claims from the block it gained when the pool widened.
    'ch02': (CH02_GOAL_WINDOW_MSG, CH02_GOAL_STATUS_MSG,
             *CH02_TURN1_MSGS,
             *(msg for _sym, msg, _fid, _bg in CH02_VILLAGE_SLOTS.values())),
}

# The DEAD VANILLA BLOCK each hosted chapter draws its ids from, inclusive. A hosted chapter
# takes its HOST SLOT's block, which is not the block of the chapter it mines -- ch05 is
# vanilla Ch5's 1:1 twin and owns vanilla CH6's ids, because it hosts on slot 6 and ch04 has
# slot 5's already.
#
# Declared rather than inferred from what is claimed, and that is the whole point: a range
# computed from its own contents can only ever report itself as full, so it could never
# answer the question this exists for -- how much room is LEFT. These ranges were prose in
# the comments beside each chapter's constants (#312 promoted them to data); a chapter with
# no entry predates the registry, and "unknown" is reported rather than guessed at.
#
# A block's free ids are the ones NOBODY claims, not the ones its owner has not taken: ch05's
# ending borrowed 0x9C9/0x9CA out of ch04's block, with the reason recorded at CH05_ENDING_MSGS.
# Message id ranges a hosted chapter may spend, as a TUPLE OF RANGES per chapter.
#
# The first rule was "take the dead block of the slot you displace" -- safe with no analysis,
# since blanking slot N's events kills slot N's text references. It also caps a chapter at
# whatever that one vanilla chapter happened to spend, and ch05 hit 0 free at 18 ids while
# 528 ids belonging to chapters we never ship sat unclaimed in contiguous runs up to 48 wide.
# Extra ranges come from that pool; `live_ids_in_declared_blocks` is what makes taking them
# safe, by CHECKING deadness rather than assuming it. Existing ranges are never renumbered --
# a shipped message id moving is a text regression nobody would see until the ROM ran.
HOSTED_CHAPTER_MESSAGE_BLOCKS = {
    'ch02': ((0xAC0, 0xAEF),),                    # from the never-shipped pool (48 ids)
    'ch03': ((0x9A3, 0x9B9),),                    # the dead vanilla Ch4 block (slot 4)
    # 0x9C9-0x9CC withheld: ch05 spends 0x9C9/0x9CA (below), and a block may not cover
    # an id another chapter already writes. ch04 spends through 0x9C6.
    'ch04': ((0x9BA, 0x9C8),),                    # the dead vanilla Ch5 block (slot 5)
    # (0x9C9,0x9D2) is not new territory -- ch05 was ALREADY writing these ids while no
    # block declared them, so its headroom read wrong and ch04's block sat over two of
    # them. Declaring them changes no text; it makes the declaration true.
    'ch05': ((0x9C9, 0x9D2), (0x9E4, 0x9F5), (0xBC5, 0xBF2)),
    # The dead vanilla Ch7 block (slot 7), contiguous after ch05's 0x9E4-0x9F5. Every id in it
    # is referenced ONLY by `ch7-eventscript.h`, which inject_ch06 rewrites wholesale -- so the
    # deadness is created by the same injector that spends the range, not assumed of it.
    # Vanilla Ch7 also spends 0xA00-0xA07; those are left unclaimed rather than swept in, so
    # the block stays the ten ids the hosting derivation named.
    'ch06': ((0x9F6, 0x9FF),),
}

# The size of vanilla's message table (gMsgTable). Ids at or above this are not messages.
VANILLA_MESSAGE_COUNT = 0xD4C

def message_block_ranges(chapter, blocks=None):
    """The (lo, hi) ranges a hosted chapter may spend. Empty when it declares none.

    Ranges validate themselves: an inverted pair yields NEGATIVE capacity and a negative
    `free` in `make chapter`, and a typo'd bound (0xBF20 for 0xBF2) reports enormous headroom
    -- neither of which any other guard would call wrong.
    """
    ranges = tuple((blocks if blocks is not None
                    else HOSTED_CHAPTER_MESSAGE_BLOCKS).get(chapter, ()))
    for lo, hi in ranges:
        if not 0 < lo <= hi < VANILLA_MESSAGE_COUNT:
            raise ValueError('%s declares message range (0x%X, 0x%X), which is not an '
                             'ascending pair inside the 0x%X-id table'
                             % (chapter, lo, hi, VANILLA_MESSAGE_COUNT))
    return ranges


def message_block_capacity(chapter, blocks=None):
    """How many ids a chapter's declared ranges hold in total."""
    return sum(hi - lo + 1 for lo, hi in message_block_ranges(chapter, blocks))


def injector_message_ids():
    """{vanilla message id: constant name} for the ids the injector NAMES as `*_MSG`/`*_MSGS`.

    The hazard a widened block actually faces. Vanilla's own references to a slot we host
    die when our injector blanks that slot's event lists -- but ids we have REPURPOSED are
    very much alive, and they no longer look like what they were. Vanilla Ch2's three
    village texts (0x969-0x96C) are ch01's lord-select candidate blurbs now; a block drawn
    over them would compile, ship, and garble a scene nobody was looking at.

    NOT a complete list of what the build spends, and it cannot be: an id computed at inject
    time (`vanilla_name_text_id(slot)`, a host's `chapTitleTextId`) has no constant to find.
    `live_ids_in_declared_blocks` folds `HOSTED_CHAPTER_MESSAGE_IDS` on top for that reason --
    naming this limit is what keeps the guard from resting on a convention nothing enforces.

    A BARE LITERAL at the call site has no constant either, and that hole is now closed from
    the other side: `literal_message_ids` (inject/hosts.py) reads them out of the injector's
    SOURCE and they are folded in below, so a literal no longer waits on a human to notice it
    (#346). `check_message_literals_are_registered` is the half that still asks for a NAME --
    only a named id lands in HOSTED_CHAPTER_MESSAGE_IDS, and only that gives it an owner.

    A constant may hold its ids in a dict as readily as a tuple -- `PC_DEATH_QUOTE_MSGS` maps
    unit -> id -- and reading only the tuple shape hid all 13 of its death quotes while its
    NAME followed the convention perfectly.
    """
    out = {}
    for name, value in sorted(injector_constants(r'_MSGS?$').items()):
        if isinstance(value, dict):
            values = list(value.values())
        elif isinstance(value, (tuple, list, set)):
            values = value
        else:
            values = (value,)
        # No lower bound: every chapter's objective window/status string lives below 0x300,
        # and an undocumented floor there silently exempted all ten of them.
        for mid in values:
            if isinstance(mid, int) and 0 < mid < VANILLA_MESSAGE_COUNT:
                out.setdefault(mid, name)
    # And the ids with no constant to be found by: a BARE LITERAL at the `set_message_body`
    # call site (#346). The prologue and ch01 write twelve, and they were visible here only
    # because someone grepped for them and hand-transcribed them into PROLOGUE_LITERAL_MSGS /
    # CH01_LITERAL_MSGS -- so for that class the promise above ("registering a new one is
    # enough") held only for whoever remembered to do the transcribing. `literal_message_ids`
    # reads them out of the injector's own SOURCE, so the next one registers itself the moment
    # it is written. 0xC25 is why it matters: it sits 0x33 above ch05's pool, and extending
    # that range upward -- the obvious next move -- would have overwritten a defeat quote.
    for lit in literal_message_ids():
        if 0 < lit.msg_id < VANILLA_MESSAGE_COUNT:
            out.setdefault(lit.msg_id, 'literal in %s (%s:%d)'
                           % (lit.chapter or 'a module-level helper',
                              os.path.basename(lit.path or '<source>'), lit.lineno))
    return out


def live_ids_in_declared_blocks(blocks=None, claims=None):
    """Ids inside a declared block that something else already spends. Empty == safe.

    A chapter's own claims are fine -- that is what a block is FOR. What is refused is a
    range drawn over an id another part of the build hardcodes, because nothing downstream
    would notice: the build succeeds, the ROM ships, and one scene reads another's text.
    """
    owned = (claims if claims is not None else HOSTED_CHAPTER_MESSAGE_IDS)
    # BOTH sources, because neither is complete on its own. `injector_message_ids` finds ids by
    # NAME (`*_MSG` / `*_MSGS`), which misses any held in a constant called something else --
    # ch02's two hut visits live in `CH02_VILLAGE_SLOTS`, so 0xAC0/0xAC1 were invisible to it and
    # a future block drawn over them would have built clean and garbled a scene, which is the one
    # thing this guard exists to stop. The per-chapter claims below are the authoritative list of
    # what we spend and depend on no naming convention, so they are read too.
    spent = injector_message_ids()
    for chapter, ids in sorted(owned.items()):
        for mid in ids:
            if isinstance(mid, int) and 0 < mid < VANILLA_MESSAGE_COUNT:
                spent.setdefault(mid, '%s claim' % chapter)
    bad = []
    for chapter, ranges in sorted((blocks if blocks is not None
                                   else HOSTED_CHAPTER_MESSAGE_BLOCKS).items()):
        mine = set(owned.get(chapter, ()))
        for lo, hi in ranges:
            bad += ['%s 0x%X (%s)' % (chapter, m, spent[m])
                    for m in range(lo, hi + 1) if m in spent and m not in mine]
    return bad


def assert_message_blocks_disjoint(blocks=None):
    """Guard: no two hosted chapters may declare OVERLAPPING id blocks.

    `assert_message_ids_unique` catches two chapters writing the same id. This catches the
    setup that makes that inevitable -- two chapters told to help themselves to the same
    range -- before either has spent it.
    """
    flat = sorted(((lo, hi), name)
                  for name, ranges in (blocks if blocks is not None
                                       else HOSTED_CHAPTER_MESSAGE_BLOCKS).items()
                  for lo, hi in ranges)
    ordered = [(name, span) for span, name in flat]
    for (a, (a_lo, a_hi)), (b, (b_lo, b_hi)) in zip(ordered, ordered[1:]):
        if b_lo <= a_hi:
            sys.exit('ERROR: %s (0x%X-0x%X) and %s (0x%X-0x%X) declare OVERLAPPING message '
                     'ranges -- two ranges cannot both be free to spend the same ids%s'
                     % (a, a_lo, a_hi, b, b_lo, b_hi,
                        ' (and they are the SAME chapter, which would double-count its own '
                        'headroom)' if a == b else ''))
    return True


_RAW_PID_RE = re.compile(r'^0x[0-9a-f]{2}$')
_RAW_PID_CONST_RE = re.compile(r'^(CH\d+|PROLOGUE)_[A-Z0-9_]*PIDS?$')


def raw_pid_claims(scope=None):
    """{raw pid: the set of chapter prefixes whose constants claim it}.

    DISCOVERED from the injector's own `CHNN_*PID`/`*PIDS` constants (`inject.namespace`) -- string, tuple or dict --
    rather than a hand-kept list, for the reason the list would exist: the constant that got this
    wrong carried a comment enumerating which pids were taken, and the comment simply did not know
    about ch04's five (#26).
    """
    scope = injector_constants(_RAW_PID_CONST_RE.pattern) if scope is None else scope
    claims = collections.defaultdict(set)
    for name, value in sorted(scope.items()):
        match = _RAW_PID_CONST_RE.match(name)
        if not match:
            continue
        if isinstance(value, dict):
            values = list(value.values())
        elif isinstance(value, (tuple, list, set, frozenset)):
            values = list(value)
        else:
            values = [value]
        for pid in values:
            if isinstance(pid, str) and _RAW_PID_RE.match(pid):
                claims[pid].add(match.group(1))
    return dict(claims)


def assert_named_raw_pids_are_exclusive(portraits=None, scope=None):
    """Guard: a raw pid that gets a NAME PLATE may be claimed by only one chapter.

    `RAW_PID_PORTRAITS` writes `nameTextId` into `gCharacterData[pid - 1]`, and that table has ONE
    row per pid with **no chapter dimension** -- unlike `gDefeatTalkList`, where ch03's grell and
    ch04's mogall share 0xb7 quite legally because each entry is keyed by chapter too. So a shared
    GENERIC pid is fine (ch05 and ch06 both spend 0x80 on autolevelled trash) while a shared NAMED
    one silently retitles somebody else's units.

    ch06's two boats took 0xb4/0xb5, which `CH04_PACK_PIDS` already owned, and two of ch04's five
    Mauthe Doogs would have read "Fishing Boat" on the unit window. Nothing caught it:
    `assert_pack_pids_addressable` checks that ch04's pack is addressable within ch04, and the
    0xB0-range occupancy lived in prose in three separate comments, none of which was complete.
    """
    portraits = RAW_PID_PORTRAITS if portraits is None else portraits
    claims = raw_pid_claims(scope)
    for pid, (_unit_id, _slot, _portrait_id, name) in sorted(portraits.items()):
        owners = claims.get(pid, set())
        if len(owners) > 1:
            sys.exit(
                'ERROR: raw pid %s is NAMED %r but claimed by %s. A name plate is written into '
                'gCharacterData[%s - 1], which has one row per pid and no chapter dimension, so '
                'every unit on that pid in EVERY chapter takes the name. Give the named unit a '
                'pid of its own (an unnamed 0x255 gap).'
                % (pid, name, ' and '.join(sorted(owners)), pid))
    return claims


def assert_message_ids_unique(claims=None):
    """Guard: no two hosted chapters may claim the same message id.

    Called from main() before any injector runs, so a collision fails the BUILD rather than
    shipping a chapter whose text was quietly overwritten by the next one. Add a chapter's
    block to HOSTED_CHAPTER_MESSAGE_IDS when it starts hosting -- that registry is the
    declaration of ownership, and this is what makes it binding.
    """
    owner = {}
    for chapter, ids in sorted((claims if claims is not None
                                else HOSTED_CHAPTER_MESSAGE_IDS).items()):
        for mid in ids:
            if mid in owner:
                sys.exit('ERROR: message id 0x%X is claimed by BOTH %s and %s. Hosted '
                         'chapters take their host slot\'s dead message block -- pick ids '
                         'from the block %s actually owns (see HOSTED_CHAPTER_MESSAGE_IDS).'
                         % (mid, owner[mid], chapter, chapter))
            owner[mid] = chapter
    return owner


def assert_literals_are_claimed(literals=None, claims=None):
    """Guard: a message id written as a BARE LITERAL must still be CLAIMED by its chapter.

    Discovery (`inject.hosts.literal_message_ids`) makes a bare literal SAFE -- it folds into
    `injector_message_ids`, so the deadness check sees it whether or not anyone wrote it down.
    What discovery cannot do is give the id an OWNER. `HOSTED_CHAPTER_MESSAGE_IDS` is what
    `assert_message_ids_unique` collides on and what `make chapter CH=chNN` reads for headroom,
    and a chapter that spends an id it does not claim reads as having room it has already
    spent. 0xC25 is the case that pays for this: it sits 0x33 above ch05's pool, so extending
    that range upward would have silently overwritten Scramsax's defeat quote.

    This lives HERE, at build time, and not in `check.py`, because here the registry is a real
    dict. #356's review killed the static version: the registry is written as generators,
    subscripts and splats, so reading it with an AST evaluator was wrong in both directions --
    it missed ch04's 0x9C3/0x9C6 (tuple-unpacked constants) and demanded a registration that
    makes `assert_message_ids_unique` exit, and it over-collected ch05's box counts and let an
    unclaimed 0x13 through. Import the registry where it is real; never re-derive it.
    """
    from inject import hosts
    literals = hosts.literal_message_ids() if literals is None else literals
    claims = HOSTED_CHAPTER_MESSAGE_IDS if claims is None else claims
    for lit in literals:
        if lit.chapter is None:
            continue                              # check.py's discovery guard owns this shape
        if lit.msg_id not in set(claims.get(lit.chapter, ())):
            holder = ('PROLOGUE_LITERAL_MSGS' if lit.chapter == 'ch00'
                      else '%s_LITERAL_MSGS' % lit.chapter.upper())
            sys.exit(
                'ERROR: %s:%d writes message 0x%X as a BARE LITERAL in %s, but '
                '%s does not claim it in HOSTED_CHAPTER_MESSAGE_IDS -- so the id has no owner, '
                'assert_message_ids_unique cannot collide on it, and `make chapter CH=%s` '
                'counts it as free headroom it has already spent. Add 0x%X to %s.'
                % (os.path.relpath(lit.path, REPO) if lit.path and os.path.isabs(lit.path)
                   else lit.path or '<source>', lit.lineno, lit.msg_id, lit.chapter,
                   lit.chapter, lit.chapter, lit.msg_id, holder))
    return literals
