"""Message text: name plates, goal windows, and the FE script -> message compiler.

`set_message_body` is the one writer into the decomp's text table; `_script_to_message`
turns a YAML script beat into FE8 control codes, wrapped to the talk box.
"""
import re
import sys

import fe8_talk_font
from inject.message_alloc import allocated_message_ids
from inject.paths import CHARACTERS_C, TEXTS_TXT


# Dev placeholder -- the reusable "next chapter isn't built yet" landing. A chapter whose
# `unlocks_chapter` target isn't hosted yet ends HERE instead of MNC2'ing onto an unbuilt
# slot (which would drop the player on a leftover vanilla map): RBG delivers a cheese-pun
# "thanks for playtesting" line over the campfire BG, then MNTS returns to the title
# screen (a pure event scene -- no map/units needed). Punt it forward (call
# dev_placeholder_scene) at each new chapter boundary until the real next chapter lands.
# See docs/decisions.md "Dev placeholder".
DEV_PLACEHOLDER_MSG = 0x954   # free slot-2 id (the old unused "ingots recovered" body)

# FE8's unit-name buffer; longer names overflow and garble the display.
FE_NAME_MAX = 12


def display_name(unit):
    """The <=12-char name FE8 shows; fe_name overrides a too-long `name`."""
    name = unit.get('fe_name') or unit.get('name')
    if not name:
        sys.exit('ERROR: unit %r has no name/fe_name' % unit.get('id'))
    name = str(name).strip()
    if len(name) > FE_NAME_MAX:
        sys.exit('ERROR: name %r is %d chars (>%d); add a shorter fe_name'
                 % (name, len(name), FE_NAME_MAX))
    return name


def vanilla_name_text_id(slot):
    """nameTextId of vanilla CHARACTER_<slot>, scanned from data_characters.c."""
    marker = '[CHARACTER_%s - 1]' % slot.upper()
    with open(CHARACTERS_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        if marker in line:
            for probe in lines[i:i + 12]:
                m = re.search(r'\.nameTextId\s*=\s*(0x[0-9a-fA-F]+|\d+)', probe)
                if m:
                    return int(m.group(1), 0)
    sys.exit('ERROR: could not find nameTextId for %s in %s' % (marker, CHARACTERS_C))



def write_nameplate(lines, slot, unit):
    """Rename vanilla character `slot`'s nameplate to `unit`'s display name. A boss riding a
    borrowed slot (Breguet, Bazba, Novala) otherwise shows the vanilla name on its unit window
    and its death."""
    set_message_body(lines, vanilla_name_text_id(slot), name_message_body(display_name(unit)))

GOAL_WINDOW_MAX_CHARS = 12      # vanilla's own widest: 'Defeat enemy' / 'Seize throne'


def goal_window_body(text):
    """A goal-WINDOW string, width-checked against vanilla's budget.

    The on-map objective window does not wrap or clip gracefully: a string past its width
    runs the last glyph off the right border and drops its tail onto the row below (Nicolas
    spotted the severed 'y' of an injected 'Rout the enemy', 14 chars). FE8 never risks it --
    every vanilla goal-window string fits in 12: Survive(7), Defeat boss(11), Defeat enemy(12),
    Seize gate(10), Seize throne(12). Measured across every chapter's `goal.windowTextId`, so
    the budget is the SHIPPED corpus rather than a guess.
    """
    if len(text) > GOAL_WINDOW_MAX_CHARS:
        sys.exit('ERROR: goal-window text %r is %d chars; the window fits %d '
                 '(vanilla\'s widest are "Defeat enemy" / "Seize throne"). It would spill '
                 'its last glyph past the border and wrap the tail underneath.'
                 % (text, len(text), GOAL_WINDOW_MAX_CHARS))
    return name_message_body(text)


def name_message_body(name):
    """Format a name as a terminated FE8 message, matching vanilla's convention.

    FE8 text packs printable bytes two-at-a-time into u16s (see textprocess.py
    text_to_utf8_u16_array). `[X]` is the 0x00 string terminator. If an odd number
    of name bytes precede it, that 0x00 gets paired into the last character's high
    byte instead of standing alone as 0x0000 -- so the in-game decoder never hits
    its terminator and runs away into the next message (the "Huffman corruption"
    that bit the earlier reset). Vanilla pads odd-length names with `[.]` (0x1F,
    absorbed into the last glyph) to keep the byte count even: "Seth[X]" but
    "Franz[.][X]". We do the same.

    Names come straight from YAML, so they may carry unicode punctuation the FE8
    charset can't render (an em-dash garbled the ch02 "Bryn Shander -- West Gate"
    opening card, #22). Normalize through `_fe_dialogue_text` first -- the same
    ASCII-fold `_script_to_message` applies to dialogue -- so the parity count
    below sees the bytes the encoder will actually emit, not the unicode source.
    """
    name = _fe_dialogue_text(name)
    pad = '[.]' if len(name.encode('utf-8')) % 2 == 1 else ''
    return name + pad + '[X]'


def set_message_body(lines, msg_id, body):
    """Replace the content lines of `## MSG_<id>` with `body` (in place). Idempotent:
    matches the header and rewrites everything up to the NEXT header.

    Up to the next HEADER, not to the first blank line. 74 vanilla messages carry a mid-body
    blank -- a scene with a [BreakTalk] between stanzas -- and stopping at it replaced only
    the opening stanza, leaving the rest of vanilla's scene inside our message. ch02's Halvar
    bark took MSG_AC2 and kept Ephraim and Duessel discussing the Dark Stone underneath it.
    Nothing caught it: our body ends in [X], so the ROM decoder stops there and `verify_text`
    reported no runaway. It was dead text in the table and a trap for the next id claimed out
    of the 74.

    A missing header is always an error: an id past vanilla's last message exists only once
    `reserve_message_headers` has appended it (inject/message_alloc.py), so a missing one means
    the wrong id, or one nobody declared.
    """
    header = '## MSG_%03X' % msg_id
    for i, line in enumerate(lines):
        if line.strip() == header:
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith('## MSG_'):
                j += 1
            # Keep one blank line before the next header, as the file is formatted.
            lines[i + 1:j] = [body, '']
            return True
    sys.exit('ERROR: message header %r not found in %s' % (header, TEXTS_TXT))


def reserve_message_headers(lines, msg_ids):
    """Append an empty `## MSG_<id>` for each id in `msg_ids` (ascending) not already present.

    gMsgTable[] is generated from texts.txt and self-sizes, so a trailing header EXTENDS the
    table -- but it is a dense array, so each new id must be exactly one past the last header.
    Reserving every allocated id in one place up front is what lets any later pass write any of
    them in any order; when each writer appended its own, two passes had to run in id order
    (ch06's boats once tried to append 0xD4D before ch05's moose had 0xD4C).
    """
    present = set(ln.strip() for ln in lines if ln.strip().startswith('## MSG_'))
    for msg_id in sorted(msg_ids):
        header = '## MSG_%03X' % msg_id
        if header in present:
            continue
        last = max((i for i, ln in enumerate(lines) if ln.strip().startswith('## MSG_')),
                   default=-1)
        if last < 0:
            sys.exit('ERROR: no message headers at all in %s' % TEXTS_TXT)
        last_id = int(lines[last].strip()[len('## MSG_'):], 16)
        if msg_id != last_id + 1:
            sys.exit('ERROR: reserving MSG_%03X after MSG_%03X would leave a hole or land inside '
                     'the table; gMsgTable[] is a dense array, so a gap shifts every id past it'
                     % (msg_id, last_id))
        while lines and not lines[-1].strip():
            lines.pop()
        # texts.txt ends with a trailing newline; the writer joins on '\n', so the list has to
        # end with an empty element. Dropping it left the file without its final newline and put
        # an unrelated one-line delta in the submodule on every build.
        lines.extend(['', header, '[X]', ''])
        present.add(header)
    return lines


def reserve_appended_messages(verbose=True):
    """Give every message id the build allocates (inject/message_alloc.py) its header."""
    ids = sorted(allocated_message_ids().values())
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    reserve_message_headers(lines, ids)
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    if verbose and ids:
        print('  %d appended message id(s): MSG_%03X-MSG_%03X' % (len(ids), ids[0], ids[-1]))


def _fe_dialogue_text(s):
    """Normalize locked YAML dialogue to the FE8 charset (ASCII punctuation only)."""
    for a, b in (('—', '--'), ('–', '--'), ('…', '...'),
                 ('‘', "'"), ('’', "'"), ('“', '"'), ('”', '"')):
        s = s.replace(a, b)
    return ' '.join(s.split())


# Script pseudo-entries: stage business a cutscene `script:` carries alongside its dialogue.
# They are NOT boxes (no A-press) -- see _script_box_count. `location_card`/`fade_to_black`/
# `beat_break` are staged by the EVENT SCRIPT (or split the beat into separate messages);
# `present`/`exits` are staged inside the message body, being face controls rather than scene
# controls.
#
# `present` = "this character is on screen for this scene and never speaks" (#25's Sahnar, whom
# Ravisin raises during scene 3). It is deliberately NOT the mirror of `exits`, and the asymmetry
# is the engine's, not a design choice: a face can leave at any point, but one can only ARRIVE
# before the scene's first box. `TalkPrepNextChar` (scene.c:626) reopens the talk bubble whenever
# the ACTIVE face slot differs from the SPEAKING one, so loading a silent face mid-message opens
# a bubble for it and then another for whoever actually talks -- two stacked bubbles, which is
# what the first cut of this shipped (caught on film by Nicolas, 2026-08-14). Vanilla never loads
# a face mid-message without having it speak NEXT (MSG_904, MSG_092C, MSG_095A); its silent loads
# are always preloads at the top, before any bubble exists (MSG_0954, MSG_095D, MSG_095E). So
# `present:` renders through the same `preload` path those use, and its POSITION in the script is
# not meaningful -- put it first, where it reads the way it plays.
#
# `stage_break:` is the one directive that hands the EVENT SCRIPT the middle of a message. Its
# value is the stage direction itself, so the wordless beat lives in the data rather than in a
# YAML comment beside it. It renders as vanilla's own `[BreakTalk]` (textdefs.txt: 0x80 0x04 ->
# scene.c `case 0x04: LockTalk(proc)`), which PAUSES the talk proc without closing the bubble or
# unloading a face; the script's `TEXTEND` then returns, does its business, and `TEXTCONT`
# resumes the SAME message. Vanilla splits MSG_9BF exactly this way (a silence and a delay
# between two halves of one id), and our own lore crawl already ships the idiom.
#
# WHY IT MATTERS: the alternative -- splitting the beat across two TEXTSHOWs -- costs a second
# message id per gap, and hosted-chapter ids are the scarcest thing we have (#25). A break costs
# none. What it does NOT buy is a scene change: the bubble stays up and the faces stay loaded
# across the gap, so put a camera move BEFORE the message, not inside it.
#
# `stage_cut:` is `stage_break`'s bigger sibling and the difference is PROVEN, not stylistic. A
# break only PAUSES the talk (`LockTalk`), so the scene it interrupts must leave the talk state
# intact -- unit movement, music, a camera hold. Anything that changes what is ON SCREEN does
# not: ch05's moose bellow needs `REMOVEPORTRAITS` to re-arm the BACG loader, that tears the
# talk down, and `TEXTCONT` then resumes NOTHING. Filmed 2026-08-15 -- the CG and the charge both
# played and the punchline simply never appeared. So a scene change splits the beat into TWO
# messages, which costs one id and is the only thing that does work.
SCRIPT_DIRECTIVES = ('location_card', 'fade_to_black', 'beat_break', 'present', 'exits',
                     'stage_break', 'stage_cut')
_SCRIPT_EXIT = object()   # marker block for `exits:`, kept distinct from any speaker name
_SCRIPT_BREAK = object()  # marker block for `stage_break:` -- likewise not a speaker name


def _wrap_fe_lines(text, width=fe8_talk_font.TALK_BUDGET_PX,
                   measure=fe8_talk_font.text_px):
    """Word-wrap dialogue to GBA text lines. `width` is a PIXEL budget, not a character count.

    IT USED TO BE CHARACTERS, defaulting to 29 "because vanilla's MSG_910/911 top out at 29".
    Both halves of that were true and the conclusion did not follow: MSG_910 is simply a NARROW
    message, and one short sample became a ceiling. The engine has never counted characters --
    `GetStrTalkLen` (scene.c) sums `glyph->width` in pixels and `StartTalkExt` divides that into
    the bubble's tiles -- and the talk font is variable-width, so `i` is 2px against `W`'s 8px
    and a character count is an unrelated quantity that merely correlates. Vanilla's own Talk
    recruit (MSG_9CC, the scene ch05's is the twin of) draws a 43-character line in this exact
    window. Long form + the measurements: `decisions.md` -> "We wrapped on-map talk at 29
    CHARACTERS; the engine measures PIXELS".

    ONE BUDGET, BOTH CHANNELS. The old rule split on/off-map at 29 and 42; measured in pixels
    vanilla's two channels agree (203px on-map, 201px full-screen), because both windows are
    near-full-width on a 240px screen. The split was an artifact of the wrong instrument.

    `measure` TRAVELS WITH `width`, and that pairing is the point: not every panel in this game
    is the talk window. Our own lord-select CARD is drawn by generated code through its own
    `InitText` font in a fixed narrow column, so it is authored in CHARACTERS and passes
    `measure=len` with a character width. Converting it to the talk budget silently re-wrapped
    a 20-column card to four characters a line -- caught by diffing every rendered body against
    the previous build, not by a test, which is why that diff is now the gate for a wrap change.

    A bare '--' never opens a line: the dash glues to the word before it -- and when
    that glue would not FIT, the word it is glued to moves down with it rather than the
    line running two characters over. (It used to glue unconditionally, so a line ending
    exactly at the width came out at width+2; ch05's scene 4 sits on that boundary and is
    what found it.)

    RESIDUAL, and it is a genuine conflict rather than an oversight: a word whose own
    drawn width plus ' --' already exceeds `width` cannot be placed at all without breaking one
    of the two rules. The glue wins, so such a line goes out over-width -- there is no
    shorter arrangement, since the pair is atomic. Every line this function emits is
    therefore within `width` UNLESS it is a lone word carrying its dash. No authored box
    in the campaign is anywhere near that (checked across all of them at 29 and 42); if one
    ever is, the fix is to reword it, not to loosen the glue."""
    fits = lambda s: measure(s) <= width
    out, cur = [], ''
    for w in text.split():
        if w == '--' and cur:
            if fits(cur + ' --'):
                cur += ' --'
            else:
                head, _, tail = cur.rpartition(' ')
                if head:
                    out.append(head)          # the dash takes its word to the next line
                    cur = tail + ' --'
                else:
                    cur += ' --'              # a one-word line: nothing left to break at
            continue
        cand = (cur + ' ' + w) if cur else w
        if cur and not fits(cand):
            out.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        out.append(cur)
    return out


def _script_to_message(script, staging, width=fe8_talk_font.TALK_BUDGET_PX, face_budget=4,
                       preload=None, trailing=None,
                       measure=fe8_talk_font.text_px):
    """Render a chapter-YAML cutscene `script:` block as an FE8 message body.

    Mirrors the vanilla shape (cf. MSG_910/911): faces are loaded lazily at a
    speaker's first turn (so a boss can "step out" mid-scene), [LF] joins the two
    lines of a page, [A][LF] breaks pages (2 visible lines per A-press).

    Consecutive turns by the SAME speaker are coalesced into one [OpenX] block
    with the turn boundary as a page break. This is load-bearing, not cosmetic:
    the map-bubble width measure (GetStrTalkLen, scene.c) does NOT stop at [A] --
    it adds 12px and keeps measuring until the next speaker's printable text, and
    only [LF]/[CR] reset the line accumulator. An [A][OpenX-same-face] boundary
    without [LF] therefore merges both turns into one measured "line"; widths
    over 29 tiles make PutTalkBubble's right-side branch compute x = 29 - width
    < 0 (no clamp, unlike the left branch) and the bubble wraps the tilemap --
    the offscreen/empty-bubble bug of the 2026-06-10 scenes captures. Vanilla
    never ships an [A] that isn't terminal or [LF]-followed; now neither do we.

    FACE BUDGET (the 4-slot fix, #21 Beat 1): only FACE_SLOT_COUNT = 4 faces can
    be loaded at once (the gFaces pool; include/face.h). Vanilla .h scenes cap at
    <=4 by hand, but our big set pieces (the Northlook roll-call) have ~10
    speakers in one message, so this tracks PODIUMS (screen positions), not
    speakers, as the budget. `live` maps an [OpenX] tag -> the speaker whose face
    sits there; `lru` orders podiums least-recently-used first. When a podium is
    re-used by a different speaker we emit `[OpenX][ClearFace]` (scene.c: fades
    out faces[activePosition] and frees its gFaces slot, ~16-frame fade -> reads
    as pacing between speakers); when all four are full we evict the LRU podium.
    A rotating spotlight (many speakers staged to ONE podium) thus shows one face
    at a time while other speakers stay anchored elsewhere. The temporary lock on
    [ClearFace] means the fade-out frees its slot BEFORE the following [LoadFace]
    runs, so the pool never momentarily overflows. (With <=4 distinct podiums this
    is byte-for-byte the old lazy-load behaviour -- the prologue is unaffected.)

    A `staging` value of (open_tag, None) is a FACELESS speaker (stage business):
    its text prints in a box with no [LoadFace], at a podium that should be left
    unoccupied so no loaded face mouth-moves under it.

    `preload` is a list of (open_tag, [FID_x]) faces shown BEFORE the dialogue --
    silent listeners (e.g. the party watching Hlin's monologue, or Hruna standing
    across from RBG). They seed the live map so the speaker(s) talk TO a populated
    room instead of an empty one; keep preload podiums distinct from the beat's
    speaker podiums, and the total (preload + concurrent speakers) within the
    4-face budget so no listener is evicted.

    `location_card` / `fade_to_black` / `beat_break` entries are staged by the
    event script (or split into separate messages), not the message body, and are
    skipped here. `stage_break` is the exception that IS rendered: it emits
    vanilla's `[BreakTalk]`, a pause the event script resumes with `TEXTCONT`, so
    a wordless action can happen mid-message without buying a second message id
    (see SCRIPT_DIRECTIVES). `width` is a PIXEL budget and `measure` the function that
    applies it -- fe8_talk_font.TALK_BUDGET_PX for the talk bubble, BATTLE_QUOTE_BUDGET_PX for
    a quote shown during a battle animation, SOLO_BOX_BUDGET_PX for the auto-centered helpbox.
    Passing a character count here is the failure this parameter used to invite (was:
    ~42 for a full-screen scenic BG -- see _wrap_fe_lines).

    `trailing` is a raw text-code string appended just before the [X] terminator --
    e.g. '[OpenMidLeft][ClearFace]' to fade ONLY that podium's face at the beat's
    end (scene.c: StartFaceFadeOut on faces[activeFaceSlot]), leaving the others up.
    The one low-level face control the podium auto-manager doesn't infer: a speaker
    who exits mid-scene while a co-speaker holds (the ch03 Pinky-scout -> RBG waits).
    """
    blocks = []   # (speaker, [page, ...]); page = 'line1[LF]\nline2'
    for entry in script:
        (speaker, text), = entry.items()
        if speaker == 'exits':
            # A speaker who WALKS OFF while the scene runs on. Carried through as a marker
            # rather than skipped, because it has to fire at this POINT in the message -- and
            # because it must break the same-speaker coalescing below, or the fade would play
            # after the lines it is supposed to precede.
            blocks.append((_SCRIPT_EXIT, text))
            continue
        if speaker == 'stage_cut':
            sys.exit('ERROR: `stage_cut` is a MESSAGE BOUNDARY, not a body code -- split the '
                     'script on it and render each side (see split_on_stage_cut). It exists '
                     'because the engine cannot resume a message across a scene change.')
        if speaker == 'stage_break':
            # The point where the EVENT SCRIPT takes the scene over (see SCRIPT_DIRECTIVES).
            # Carried through rather than skipped for the same reason `exits:` is: it has to
            # land at this POINT in the body, and it must break the same-speaker coalescing
            # below, or a break between two turns by one character would render after both.
            blocks.append((_SCRIPT_BREAK, text))
            continue
        if speaker in SCRIPT_DIRECTIVES:
            continue
        lines = _wrap_fe_lines(_fe_dialogue_text(text), width, measure)
        pages = ['[LF]\n'.join(lines[p:p + 2]) for p in range(0, len(lines), 2)]
        if blocks and blocks[-1][0] == speaker:
            blocks[-1][1].extend(pages)
        else:
            blocks.append((speaker, pages))
    # A `stage_break` closes the bubble, so SOMETHING has to make the engine reopen one. It
    # reopens on `!TalkHasCorrectBubble()`, which compares the speaking face slot and width --
    # so a break between two turns by the SAME speaker would resume onto a bubble the engine
    # still believes is correct, and print the next box onto a cleared tilemap. Refused here
    # rather than discovered on film: the scene would look like the text simply vanished.
    for i, (who, _pages) in enumerate(blocks):
        if who is not _SCRIPT_BREAK:
            continue
        before = next((b[0] for b in reversed(blocks[:i]) if isinstance(b[0], str)), None)
        after = next((b[0] for b in blocks[i + 1:] if isinstance(b[0], str)), None)
        if after is None:
            sys.exit('ERROR: a `stage_break` is the LAST thing in this script -- it closes the '
                     'bubble and nothing resumes it. Stage business after the final box belongs '
                     'in the event script, past TEXTEND/REMA.')
        if before == after:
            sys.exit('ERROR: `stage_break` sits between two turns by %r -- the bubble closes '
                     'and the engine will not reopen it for the same speaker at the same width, '
                     'so the next box prints onto a cleared window. Give the break a different '
                     'speaker on the far side, or move it out to the event script.' % after)

    parts = []
    live = {}   # [OpenX] tag -> speaker currently holding that podium's face
    lru = []    # [OpenX] tags, least-recently-used first
    def load_face(open_tag, fid_tag, holder):
        """Bring `holder`'s face up at `open_tag`, evicting whatever the budget requires.

        Factored out of the speaker loop so the eviction rules live in one place.
        """
        if open_tag in live:                    # podium held by someone else
            parts.append(open_tag + '[ClearFace]')
            del live[open_tag]
            lru.remove(open_tag)
        while len(live) >= face_budget:         # all podiums full -> evict LRU
            old = lru.pop(0)
            parts.append(old + '[ClearFace]')
            del live[old]
        parts.append('%s[LoadFace]%s' % (open_tag, fid_tag))
        live[open_tag] = holder
        lru.append(open_tag)

    # `present:` characters join the explicit `preload` list: both are faces that are simply
    # THERE, and the engine only accepts them before the first bubble opens (see
    # SCRIPT_DIRECTIVES). Script order among them is preserved, after any caller-supplied ones.
    seeded = list(preload or [])
    for entry in script:
        for key, name in entry.items():
            if key != 'present':
                continue
            open_tag, fid_tag = staging.get(name, (None, None))
            if open_tag is None or fid_tag is None:
                sys.exit('ERROR: `present: %s` but %s has no faced podium in this scene -- a '
                         'character staged with nowhere to stand is a silent no-op' % (name, name))
            seeded.append((open_tag, fid_tag, name))
    for seed in seeded:                       # silent listeners, loaded first
        pos, fid = seed[0], seed[1]
        parts.append('%s[LoadFace]%s' % (pos, fid))
        # A `present:` character is recorded UNDER THEIR NAME, an anonymous `preload` under a
        # sentinel that no speaker can match. The difference matters to `exits:`, which checks
        # that the leaver actually holds the podium it is about to clear: a named presence who
        # later walks off is a legal scene (staged silently, then leaves), and under the
        # sentinel that check saw an impostor and hard-exited the build.
        live[pos] = seed[2] if len(seed) > 2 else '\x00listener'
        lru.append(pos)
    for speaker, pages in blocks:
        if speaker is _SCRIPT_BREAK:
            # [CloseSpeechSlow] FIRST, and it is not a flourish: `[BreakTalk]` only LOCKS the
            # talk proc, so without it the last speaker's bubble hangs over the whole action and
            # whatever moves does so UNDERNEATH it (Nicolas, watching ch05's moose charge under
            # Pinky's box, 2026-08-15). The tag is `ClearTalkBubble()` and nothing else
            # (scene.c) -- the faces stay loaded and the talk state survives, so `TEXTCONT`
            # brings the window straight back for the next speaker. Vanilla uses it mid-message
            # for the same reason (MSG_9BF).
            # Every block already ends on [A], so this lands as [A][CloseSpeechSlow][BreakTalk].
            parts.append('[CloseSpeechSlow]\n[BreakTalk]')
            continue
        if speaker is _SCRIPT_EXIT:
            leaving = pages                       # the marker carries the speaker's name
            open_tag, _fid = staging.get(leaving, (None, None))
            if open_tag is None or live.get(open_tag) != leaving:
                sys.exit('ERROR: `exits: %s` but %s holds no podium at that point in the scene '
                         '-- a stage direction that fires on nobody is a silent no-op, which is '
                         'how the face it means to fade got left on screen to begin with'
                         % (leaving, leaving))
            parts.append(open_tag + '[ClearFace]')
            del live[open_tag]
            lru.remove(open_tag)
            continue
        open_tag, fid_tag = staging[speaker]
        if fid_tag is None:           # faceless stage business -- no face, no slot
            # Emit NO [OpenX] code: those are portrait POSITION anchors (textdefs.txt
            # [OpenMidLeft]=9 ... ); opening one without a [LoadFace] anchors the text
            # window to an absent portrait's mouth and the box renders as a cramped,
            # mis-placed sliver (the "Marty leans in..." narration bug, 2026-06-17).
            # Plain text shows in the default full-width box, which is what narration wants.
            parts.append('[A][LF]\n'.join(pages) + '[A]')
            continue
        body = open_tag + '[A][LF]\n'.join(pages) + '[A]'
        if live.get(open_tag) == speaker:           # already on screen here
            lru.remove(open_tag)
            lru.append(open_tag)
        else:
            load_face(open_tag, fid_tag, speaker)
        parts.append(body)
    return '\n'.join(parts) + (trailing or '') + '[X]'


def _script_box_count(script):
    """A-presses in a cutscene `script:` -- stage directions are not boxes.

    Scene box counts are locked and asserted against the YAML, so a directive that counted as
    a box would make every such assertion off by one the moment a scene gained one.
    """
    return sum(1 for e in script if next(iter(e)) not in SCRIPT_DIRECTIVES)


def _fid_tag(slot):
    """textdefs.txt face-tag for a vanilla character slot (CamelCase, irregulars mapped)."""
    # 'O_NEILL' is GUEST_PORTRAIT_MAP's spelling of the SAME slot PROLOGUE_SEPHEK_SLOT calls
    # 'ONEILL'. Both have to land on [FID_ONeill], the one tag textdefs.txt defines: without the
    # second key, any scene resolving Sephek through _cutscene_fid's GUEST_PORTRAIT_MAP fallback
    # emits [FID_O_Neill] and every check stays green (decisions.md -> "A portrait SLOT name is
    # not a face TAG").
    special = {'ONEILL': 'ONeill', 'O_NEILL': 'ONeill',
               'VILLAGER_WOMAN': 'VillagerWoman'}
    # Key the irregulars CASE-INSENSITIVELY. Callers reach this both ways -- PROLOGUE_SEPHEK_SLOT
    # is already upper ('ONEILL') while GUEST_PORTRAIT_MAP holds title case ('O_Neill'), and
    # _cutscene_fid upper()s only on its own paths -- so a table keyed on one spelling silently
    # misses the other and falls through to .title(), emitting a tag textdefs.txt never defines.
    return '[FID_%s]' % special.get(slot.upper(), slot.title())


def dev_placeholder_scene():
    """Event-script tail for an unbuilt chapter boundary (see DEV_PLACEHOLDER_MSG).

    Drop this in place of an `MNC2(next)` whose next chapter isn't hosted yet: the
    caller has just faded to black (FADI), so this reveals the campfire BG, shows
    RBG's "still under construction" cheese-pun line, then returns to the title
    screen (MNTS = EvtBackToTitle -> GAME_ACTION_EVENT_RETURN, eventscr.c). No chapter
    is loaded, so the player never lands on a leftover vanilla map. The matching
    message body is set by dev_placeholder_message()."""
    return (
        '    REMOVEPORTRAITS\n'
        '    BACG(BG_FIREPLACE) /* dev placeholder: RBG by the campfire */\n'
        '    FADU(16)\n'
        '    Text(0x%X) /* RBG: "still under construction" cheese pun */\n'
        '    FADI(16)\n'
        '    MNTS(0x0) /* next chapter not built yet -> back to title */\n'
        % DEV_PLACEHOLDER_MSG)


def raw_pid_name_text_id(slot):
    """The message id a raw-pid unit's name lives in.

    An int is an id we OWN and appended (the moose); a str is a vanilla donor slot whose name
    message we retitle (Ravisin on Riev). Appending spends nothing, so it is the default for a
    creature that needs a name and no bust.
    """
    return slot if isinstance(slot, int) else vanilla_name_text_id(slot)
