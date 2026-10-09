#!/usr/bin/env python3
"""See a scene without building a ROM (#311).

The only way to look at one of our scenes used to be to build a ROM and boot it, which is why
ch05 authored dialogue at one scene per session for fifteen sessions. This renders an authored
scene exactly as FE8 will wrap it -- from the chapter YAML, with no build and no emulator.

It reads the SHIPPING body. The chapter's own message builders (`ch05_opening_messages` and
friends) are pure `chap -> [(msg_id, body)]` functions, so the preview calls them and reads
their output back rather than re-implementing the wrap. A preview that renders a scene its own
way is a preview that can disagree with the ROM, which would make it worse than nothing.

A script no builder wires yet renders as a DRAFT through the same body code, with default seats
(see `draft_scenes`), and never enters the golden book.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.cast
import inject.chapter_ids
import inject.chapters.ch05
import inject.chapters.ch06
import inject.hosting
import inject.scenes
import inject.text
import fe8_talk_font

CAMPAIGN = 'rime-of-the-frostmaiden'

# Text codes, from fireemblem8u/texts/textdefs.txt.
_TAG = re.compile(r'\[([A-Za-z0-9_.]+)\]')

Box = collections.namedtuple('Box', 'kind podium face lines speaker')
Stage = collections.namedtuple('Stage', 'kind podium face lines speaker')


def read_scene(body):
    """Walk a rendered message body into the STEPS a scene plays: boxes and stage beats.

    The newlines in a body are texts.txt layout and carry nothing, so they go first: the
    engine sees one run of codes and printable text.

    A stage beat costs no A-press, which is why it is a step and not a box -- but dropping it
    shows a face standing at its podium through lines it has already walked off from.
    """
    body = body.replace('\n', '')
    podium, faces, out = None, {}, []
    lines, cur, pos = [], '', 0
    pressed = False   # the previous tag was [A]: the next one decides page or new block
    block = None      # the podium this block SPEAKS from; None is faceless
    for m in _TAG.finditer(body):
        cur += body[pos:m.start()]
        pos = m.end()
        tag = m.group(1)
        if pressed:
            # `_script_to_message` joins a turn's pages with `[A][LF]`, so an [LF] here is the
            # PAGE BREAK and the block continues. Reading it as a line would open every
            # continued box with a phantom blank. Anything else starts a fresh block.
            pressed = False
            if tag == 'LF':
                continue
            block = None
        if tag.startswith('Open'):
            # An [OpenX] is either a speaker opening their own box or an anchor for the
            # [LoadFace]/[ClearFace] that FOLLOWS it, and only the first names who is talking.
            # Taking the most recent one regardless seats a faceless beat at whichever podium
            # was last managed -- a silent `present:` listener, or the podium an `exits:` just
            # vacated -- and captions narration with someone who never said a word. So an
            # [OpenX] is a speaker's until the next tag proves it was face management.
            podium = block = tag
        elif tag.startswith('FID_'):
            faces[podium] = tag[len('FID_'):]
        elif tag == 'ClearFace':
            out.append(Stage('exit', podium, faces.pop(podium, None), [], None))
            block = None
        elif tag == 'LoadFace':
            block = None
        elif tag == 'BreakTalk':
            out.append(Stage('pause', None, None, [], None))
        elif tag == 'LF':
            lines.append(cur)
            cur = ''
        elif tag == 'A':
            lines.append(cur)
            out.append(Box('box', block, faces.get(block), lines, None))
            lines, cur = [], ''
            pressed = True
    return out


def read_boxes(body):
    """Just the boxes: one per A-press, which is what a scene COSTS the player."""
    return [s for s in read_scene(body) if s.kind == 'box']


def _speakers():
    """[FID_x] face tag -> the campaign name that wears it.

    A face tag names the vanilla SLOT a portrait was injected over, so an unmapped preview
    captions ch05's opening with "Artur" and "Marisa". Sephek is the one who needs saying
    twice: his face comes from PROLOGUE_SEPHEK_SLOT, not from the guest map, and the two
    spell the same slot differently (`decisions.md` -> "A portrait SLOT name is not a face TAG").
    """
    out = {}
    for uid, slot in list(inject.cast.PORTRAIT_MAP.items()) + list(inject.cast.GUEST_PORTRAIT_MAP.items()):
        out.setdefault(inject.text._fid_tag(slot)[len('[FID_'):-1], uid)
    out[inject.text._fid_tag(inject.chapter_ids.PROLOGUE_SEPHEK_SLOT)[len('[FID_'):-1]] = 'sephek-kaltro'
    return out


Scene = collections.namedtuple('Scene', 'key title msg_id width steps boxes')

TALK = fe8_talk_font.TALK_BUDGET_PX
BATTLE = fe8_talk_font.BATTLE_QUOTE_BUDGET_PX

# key -> (title, message id, the chapter's own builder, the channel's pixel budget).
#
# Keyed by MESSAGE ID rather than by the builder's list position: a builder returns a scene and
# its no-Lupin twin together, and an index would silently re-point at the other arm the first
# time one is added. The id is what the ROM uses and what every constant here is already named
# for. The titles are the chapter's own -- `CH05_*_SLOT` rows carry them.


Entry = collections.namedtuple('Entry', 'title msg_id builder width event')

# Which authored EVENT a scene renders: (trigger, slot) as the chapter YAML spells them, or
# (trigger, None) where the trigger alone identifies it. This is the join key -- it is how
# `chapter_status` says "this declared event is the one you can preview" without keeping a
# third copy of the mapping. It comes off the same constants the ids do.
Event = collections.namedtuple('Event', 'trigger slot')


def _claim(reg, key, title, msg_id, builder, width, event):
    """Register one scene, refusing to overwrite a key already claimed.

    The generated opening keys and the hand-written ones share a namespace, so a new
    CH05_OPENING_SLOTS row can generate a key a later line then silently replaces -- and the
    scene it replaced vanishes from the tool and from the golden book without failing anything.
    """
    if key in reg:
        raise KeyError('two scenes claim %r: %r and %r -- one of them would vanish from '
                       '--list, from `make scene` and from the golden book'
                       % (key, reg[key].title, title))
    reg[key] = Entry(title, msg_id, builder, width, event)


def _ch05_registry():
    arrival = inject.chapter_ids.CH05_ARRIVAL_SLOT
    join = inject.chapter_ids.CH05_BASIL_JOIN_SLOT
    alone = inject.chapter_ids.CH05_SAHNAR_ALONE_SLOT
    moose = inject.chapter_ids.CH05_MOOSE_CHARGE_SLOT
    talk = inject.chapters.ch05.ch05_sahnar_talk_messages
    ending = inject.chapters.ch05.ch05_ending_messages
    opening = lambda slot: Event('chapter_start', slot)
    reg = collections.OrderedDict()
    for n, (slot, msg, _boxes, what) in enumerate(inject.chapter_ids.CH05_OPENING_SLOTS, 1):
        _claim(reg, 'ch05/%d' % n, what, msg, inject.chapters.ch05.ch05_opening_messages, TALK, opening(slot))
    _claim(reg, 'ch05/4', arrival[3], arrival[1], inject.chapters.ch05.ch05_opening_messages, TALK,
           opening(arrival[0]))
    _claim(reg, 'ch05/4-no-lupin', arrival[3] + ' (no Lupin)',
           inject.chapter_ids.CH05_ARRIVAL_NO_LUPIN_MSG, inject.chapters.ch05.ch05_opening_messages, TALK, opening(arrival[0]))
    _claim(reg, 'ch05/5', join[3], join[1], inject.chapters.ch05.ch05_basil_join_messages, TALK,
           opening(join[0]))
    _claim(reg, 'ch05/5-no-lupin', join[3] + ' (no Lupin)',
           inject.chapter_ids.CH05_BASIL_JOIN_NO_LUPIN_MSG, inject.chapters.ch05.ch05_basil_join_messages, TALK,
           opening(join[0]))
    _claim(reg, 'ch05/6', alone[3], alone[1], inject.chapters.ch05.ch05_sahnar_alone_message, TALK,
           opening(alone[0]))
    _claim(reg, 'ch05/7', moose[3], moose[1], inject.chapters.ch05.ch05_moose_charge_message, TALK,
           opening(moose[0]))
    _claim(reg, 'ch05/7-quip', moose[3] + ' (the punchline)',
           inject.chapter_ids.CH05_MOOSE_QUIP_MSG, inject.chapters.ch05.ch05_moose_charge_message, TALK, opening(moose[0]))
    _claim(reg, 'ch05/talk-recruit', 'Basil talks Sahnar out of the sarcophagus',
           inject.chapter_ids.CH05_SAHNAR_TALK_MSG, talk, TALK, Event('sahnar_talk', None))
    _claim(reg, 'ch05/talk-recruit-no-lupin',
           'Basil talks Sahnar out of the sarcophagus (no Lupin)',
           inject.chapter_ids.CH05_SAHNAR_TALK_NO_LUPIN_MSG, talk, TALK, Event('sahnar_talk', None))
    _claim(reg, 'ch05/eruption', 'Ravisin warns the party, turn 2',
           inject.chapter_ids.CH05_ERUPTION_MSG, inject.chapters.ch05.ch05_eruption_message, TALK,
           Event('eruption_turn', None))
    _claim(reg, 'ch05/ravisin-taunt', 'Ravisin, first engagement',
           inject.chapter_ids.CH05_RAVISIN_TAUNT_MSG, inject.chapters.ch05.ch05_ravisin_taunt_message, BATTLE,
           Event('boss_battle', None))
    _claim(reg, 'ch05/ravisin-death', 'Ravisin dies',
           inject.chapter_ids.CH05_RAVISIN_DEATH_MSG, inject.chapters.ch05.ch05_ravisin_death_message, BATTLE,
           Event('boss_death', None))
    _claim(reg, 'ch05/ending', 'the ending, Sahnar recruited',
           inject.chapter_ids.CH05_ENDING_MSGS[True], ending, TALK,
           Event('chapter_end', inject.chapters.ch05.CH05_ENDING_SLOT))
    _claim(reg, 'ch05/ending-no-sahnar', 'the ending, the berry exchange cut',
           inject.chapter_ids.CH05_ENDING_MSGS[False], ending, TALK,
           Event('chapter_end', inject.chapters.ch05.CH05_ENDING_SLOT))
    _claim(reg, 'ch05/ending-basil-died', "the ending, over Basil's body",
           inject.chapter_ids.CH05_ENDING_LOST_MSG, ending, TALK,
           Event('chapter_end', inject.chapters.ch05.CH05_ENDING_LOST_SLOT))
    # DELIBERATELY absent: the arena tutorial (`ch05_arena_messages`). Its two boxes are locked
    # to vanilla MSG_9D5/9D6 VERBATIM and the builder proves that by reading them out of the
    # decomp's texts.txt -- so previewing it would put a decomp read inside the one tool whose
    # whole claim is that it needs no build. It is not authored prose and has its own gate.
    return reg


def _ch06_registry():
    ids = inject.chapter_ids
    opening = inject.chapters.ch06.ch06_opening_messages
    reg = collections.OrderedDict()
    _claim(reg, 'ch06/opening-hall', 'Bremen: Dorbulgruf hires the party',
           ids.CH06_OPENING_MSGS[0], opening, TALK, Event('chapter_start', None))
    _claim(reg, 'ch06/opening-ice', 'on the ice: the boats, the shadows',
           ids.CH06_OPENING_MSGS[1], opening, TALK, Event('chapter_start', None))
    _claim(reg, 'ch06/opening-quip', 'the merfolk surface; Meesmickle answers',
           ids.CH06_OPENING_QUIP_MSG, opening, TALK, Event('chapter_start', None))
    boarding = lambda chap: inject.chapters.ch06.ch06_boarding_wiring(CAMPAIGN, chap)[2]
    _claim(reg, 'ch06/board-east', "boarding Grynsk's boat: the Antitoxin",
           ids.CH06_BOAT_TALK_MSGS['boat-east'], boarding, TALK, None)
    _claim(reg, 'ch06/board-west', "boarding Tali's boat",
           ids.CH06_BOAT_TALK_MSGS['boat-west'], boarding, TALK, None)
    return reg


# Generic villager faces a chapter borrows for a named NPC, captioned per CHAPTER because the
# same slot is somebody else elsewhere (ch04's logger also wears VillagerMan3).
FACE_CAPTIONS = {'ch06': {'VillagerMan3': 'grynsk', 'VillagerGirlBlackHair': 'tali'}}


# Which chapter YAML a WIRED scene key reads from. ch01-ch04 render their scenes INLINE inside
# their injectors rather than through pure builders, so covering them means extracting those
# call sites first (`decisions.md` -> "A scene is readable without a ROM"). Until then their
# scripts still preview as DRAFTS (below), which is every chapter's authoring path anyway.
CHAPTER_YAML = {'ch05': inject.chapter_ids.CH05_CHAPTER_YAML,
                'ch06': inject.chapter_ids.CH06_CHAPTER_YAML}

_REGISTRY = None


def registry():
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _ch05_registry()
        for key, entry in _ch06_registry().items():
            _claim(_REGISTRY, key, entry.title, entry.msg_id, entry.builder, entry.width,
                   entry.event)
    return _REGISTRY


# ── Drafts: a scene being WRITTEN ─────────────────────────────────────────────────────────
# A dialogue pass is spent before a scene has a message id or a builder, which is exactly when
# reading it boxed matters most. So any `script:` on an event no builder wires renders through
# the SAME code a builder uses (scene_beat_bodies -> _script_to_message), with default seats.
# Drafts never enter the golden book: that holds shipping bodies only, so what it approves is
# what the ROM says.

# Seats in order of first appearance: party on the left, the other side on the right.
DRAFT_SEATS = ('[OpenMidLeft]', '[OpenMidRight]', '[OpenFarLeft]', '[OpenFarRight]',
               '[OpenLeft]', '[OpenRight]')


def _draft_fid(spk):
    if spk == 'narration':
        return None
    for faces in (inject.cast.PORTRAIT_MAP, inject.cast.GUEST_PORTRAIT_MAP):
        if spk in faces:
            return inject.text._fid_tag(faces[spk].upper())
    return '[FID_%s]' % _faceless_tag(spk)   # no face wired yet


def _faceless_tag(spk):
    """A stand-in face tag for a speaker with no portrait yet. The reader's tag grammar has
    no `-`, so `nobody-yet` is spelled with underscores and captioned back by draft_scenes."""
    return 'DRAFT_' + spk.replace('-', '_')


def _draft_seats(script):
    seats = {}
    for entry in script:
        for spk in entry:
            if spk not in inject.text.SCRIPT_DIRECTIVES and spk != 'narration':
                seats.setdefault(spk, DRAFT_SEATS[len(seats) % len(DRAFT_SEATS)])
    return seats


def draft_scenes(chapter, chap, wired):
    """[Scene] for every scripted event in `chap` whose trigger is not in `wired`.

    One scene per message the script will become: a `beat_break` or a `stage_cut` starts a
    new one, as it does in every builder."""
    out, names = [], _speakers()
    for ev in chap.get('events') or []:
        trigger = ev.get('trigger')
        if not ev.get('script') or trigger in wired:
            continue
        seats = _draft_seats(ev['script'])
        names.update({_faceless_tag(spk): spk for spk in seats})
        _card, beats = inject.scenes._split_script_beats(ev['script'], card_required=False)
        pieces = []
        for beat in beats:
            while any('stage_cut' in e for e in beat):
                i = next(i for i, e in enumerate(beat) if 'stage_cut' in e)
                pieces.append(beat[:i])
                beat = beat[i + 1:]
            pieces.append(beat)
        pieces = [p for p in pieces if p]
        bodies = inject.scenes.scene_beat_bodies(list(range(len(pieces))), pieces, _draft_fid,
                                                 seats)
        for n, (_i, body) in enumerate(bodies, 1):
            key = '%s/draft-%s%s' % (chapter, trigger, '-%d' % n if len(pieces) > 1 else '')
            steps = [s._replace(speaker=names.get(s.face, s.face)) for s in read_scene(body)]
            width = (fe8_talk_font.SOLO_BOX_BUDGET_PX
                     if inject.scenes._beat_is_narration(pieces[n - 1]) else TALK)
            out.append(Scene(key, 'DRAFT of the %s event' % trigger, None, width, steps,
                             [s for s in steps if s.kind == 'box']))
    return out


def _chapter_files(campaign):
    d = os.path.join(REPO, 'campaigns', campaign, 'chapters')
    return {f.split('-')[0]: f for f in sorted(os.listdir(d)) if f.endswith('.yaml')}


def drafts(campaign=CAMPAIGN):
    """key -> Scene for every unwired scripted event in every chapter."""
    wired = collections.defaultdict(set)
    for key, entry in registry().items():
        if entry.event is not None:
            wired[key.split('/')[0]].add(entry.event.trigger)
    out = collections.OrderedDict()
    for chapter, fname in _chapter_files(campaign).items():
        chap = inject.hosting._load_chapter_yaml(campaign, fname)
        for scene in draft_scenes(chapter, chap, wired[chapter]):
            out[scene.key] = scene
    return out


SEAT = {'OpenFarLeft': 'far left', 'OpenMidLeft': 'mid left', 'OpenLeft': 'left',
        'OpenRight': 'right', 'OpenMidRight': 'mid right', 'OpenFarRight': 'far right'}

CHANNEL = {fe8_talk_font.TALK_BUDGET_PX: 'talk bubble',
           fe8_talk_font.SOLO_BOX_BUDGET_PX: 'auto-centered box',
           fe8_talk_font.BATTLE_QUOTE_BUDGET_PX: 'battle bubble'}


def format_scene(scene):
    """One scene as the page you read -- and as the GOLDEN that gets diffed.

    Nothing here is truncated and nothing is coloured: a golden that elides a long line cannot
    fail when that line grows, which is the one regression this is meant to catch.
    """
    presses = sum(1 for s in scene.steps if s.kind == 'box')
    out = ['%s  %s' % (scene.key, scene.title),
           '%s  %d A-press%s  %s, %dpx'
           % ('DRAFT (default seats)' if scene.msg_id is None else 'MSG_%03X' % scene.msg_id,
              presses, '' if presses == 1 else 'es',
              CHANNEL.get(scene.width, 'channel'), scene.width),
           '']
    n = 0
    for step in scene.steps:
        if step.kind == 'exit':
            out.append('       -- %s leaves the stage' % (step.speaker or 'a face'))
            continue
        if step.kind == 'pause':
            out.append('       -- the bubble closes; the event script takes over')
            continue
        n += 1
        seat = SEAT.get(step.podium, 'auto-centered')
        for i, line in enumerate(step.lines):
            px = fe8_talk_font.text_px(line)
            over = '  OVER by %dpx' % (px - scene.width) if px > scene.width else ''
            head = ('%4d  %-14s %-13s' % (n, step.speaker or 'narration', seat)
                    if i == 0 else ' ' * 34)
            out.append('%s| %s (%dpx)%s' % (head, line, px, over))
    return '\n'.join(out) + '\n'


def preview(key, campaign=CAMPAIGN):
    """Render one scene from the chapter YAML: no build, no ROM, no emulator."""
    reg = registry()
    if key not in reg and '/draft-' in key:
        found = drafts(campaign)
        if key in found:
            return found[key]
    if key not in reg:
        raise KeyError('no such scene %r (have: %s)' % (key, ', '.join(reg)))
    entry = reg[key]
    title, msg_id, builder, width = entry.title, entry.msg_id, entry.builder, entry.width
    chapter = key.split('/')[0]
    if chapter not in CHAPTER_YAML:
        raise KeyError('no chapter YAML registered for %r' % chapter)
    chap = inject.hosting._load_chapter_yaml(campaign, CHAPTER_YAML[chapter])
    built = builder(chap)
    # Two builder shapes, because a one-box scene has nothing to pair its body WITH: most
    # return [(msg_id, body)], the single-message ones return the body itself. The registry
    # names the id in both cases, so nothing downstream has to know which shape it got.
    bodies = {msg_id: built} if isinstance(built, str) else dict(built)
    if msg_id not in bodies:
        raise KeyError('%s builds no MSG_%03X -- the scene moved id' % (key, msg_id))
    names = dict(_speakers(), **FACE_CAPTIONS.get(chapter, {}))
    steps = [s._replace(speaker=names.get(s.face, s.face)) for s in read_scene(bodies[msg_id])]
    return Scene(key, title, msg_id, width, steps,
                 [s for s in steps if s.kind == 'box'])


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def book_path(chapter):
    return os.path.join(REPO, 'docs', 'scenes', '%s.md' % chapter)


def generate(chapter, campaign=CAMPAIGN):
    """A chapter's whole scene book: every registered scene, rendered, in player order.

    This is BOTH the thing you read and the golden that gets diffed -- the same file, so what
    is approved is what is checked. Fenced so GitHub renders the columns, because reading the
    chapter's dialogue on a phone is half of what this is for.
    """
    keys = [k for k in registry() if k.split('/')[0] == chapter]
    if not keys:
        raise KeyError('no scenes registered for %r' % chapter)
    out = ['# %s scenes' % chapter,
           '',
           'GENERATED by `python3 tools/scene_preview.py --write` from the chapter YAML -- do',
           'not hand-edit. `tools/test_scene_preview.py` regenerates this in memory and diffs',
           'it (so `make check` does), which means a wrap or staging change that moves a box',
           'fails WITHOUT a ROM build and without a playtest run (#311).',
           '',
           'Every line carries its drawn width in PIXELS against its channel budget, because',
           'the engine measures pixels and never characters. A press count is read off the',
           'rendered body: a turn that wraps past two lines PAGES, and each page is its own',
           'A-press, so a scene can cost more presses than it has authored boxes.',
           '']
    for key in keys:
        out += ['```', format_scene(preview(key, campaign)).rstrip('\n'), '```', '']
    return '\n'.join(out) + '\n'


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description='Preview an authored scene exactly as FE8 will wrap it -- from the '
                    'chapter YAML, with no build and no emulator (#311).')
    ap.add_argument('scene', nargs='?',
                    help='a scene key such as ch05/1, or a chapter (ch05) for all of them')
    ap.add_argument('--campaign', default=CAMPAIGN)
    ap.add_argument('--list', action='store_true', help='every scene the preview knows')
    ap.add_argument('--write', action='store_true',
                    help='regenerate the committed scene book(s) under docs/scenes/')
    args = ap.parse_args()
    if args.list:
        for key, entry in registry().items():
            print('%-34s MSG_%03X  %s' % (key, entry.msg_id, entry.title))
        for key, scene in drafts(args.campaign).items():
            print('%-34s DRAFT     %s' % (key, scene.title))
        return 0
    if args.write:
        for chapter in sorted({k.split('/')[0] for k in registry()}):
            path = book_path(chapter)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(generate(chapter, args.campaign))
            print('wrote %s' % os.path.relpath(path, REPO), file=sys.stderr)
        return 0
    if not args.scene:
        ap.error('name a scene (ch05/1), a chapter (ch05), --list or --write')
    if '/' in args.scene:
        print(format_scene(preview(args.scene, args.campaign)), end='')
        return 0
    keys = [k for k in registry() if k.split('/')[0] == args.scene]
    keys += [k for k in drafts(args.campaign) if k.split('/')[0] == args.scene]
    if not keys:
        # Silence and exit 0 is the wrong answer to a typo: `make scene SCENE=ch04` would
        # read as "that chapter has no scenes" rather than "the preview does not know it".
        ap.error('no scenes registered for %r -- known chapters: %s (use --list)'
                 % (args.scene, ', '.join(sorted({k.split('/')[0] for k in registry()}))))
    for key in keys:
        print(format_scene(preview(key, args.campaign)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
