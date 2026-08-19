#!/usr/bin/env python3
"""Print a vanilla FE8 chapter's scenes as readable dialogue, from the decomp.

Pairs an eventscript's scene blocks (message ids, in source order) with the
decoded message bodies in texts/texts.txt, so our authored scenes can be staged
beside the vanilla ones for pacing reference (dialogue-pass §Inputs #4).

A scene mixes two text CHANNELS and both are reported, because the channel sets
the line width we hand-box to:
  * on-map   -- units staged by LOAD1, the speaker anchors a bubble; wraps at 29 chars
  * backdrop -- a still BG_* image with the map faded out; full-width text, wraps ~42
and NEITHER is readable from the text call. Reading only `TEXTSHOW` hides whole
scenes: FE8 Ch5's opening puts the two Grado command scenes (0x9BC Glen/Saar,
0x9BD Glen/Cormag) on `Text_BG`, so a TEXTSHOW-only scan reports its 11-message
opening as 8. And reading `TEXTSHOW` as *on-map* mislabels every scene vanilla
plays as `SetBackground` + a bare `TEXTSHOW` -- Ch5's whole ENDING is one, and
that artifact was copied out of here into ch05's own locked scene notes.

    python3 vanilla_scene.py ch5 [SceneNameFragment]
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc                                          # noqa: E402

DEC = bc.DECOMP


def _decomp_text(relpath):
    """Vanilla (HEAD) text of a decomp file -- NEVER the working tree.

    The build patches `texts/texts.txt` in place (it is the first entry in
    `build_campaign.PATCHED_DECOMP_FILES`), so after any `make` the on-disk file holds OUR
    injected campaign text under vanilla's own MSG ids. Reading it directly would make this
    tool report our own lines back as the vanilla pacing benchmark -- the exact failure
    `bc.vanilla_decomp_text` exists to prevent, and the one `difficulty.py` warns about beside
    its own reads. A miner that under-reports is bad; one that reports our text as vanilla's
    is worse, because it reads as independent evidence."""
    return bc.vanilla_decomp_text(relpath)


def load_messages():
    """MSG id (int) -> raw body text, from the decomp at HEAD."""
    out, cur, buf = {}, None, []
    for line in _decomp_text('texts/texts.txt').splitlines(keepends=True):
        m = re.match(r'##\s*MSG_([0-9A-Fa-f]+)', line)
        if m:
            if cur is not None:
                out[cur] = ''.join(buf)
            cur, buf = int(m.group(1), 16), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = ''.join(buf)
    return out


# Portrait/staging markup -> a readable speaker hint, then stripped.
FID = re.compile(r'\[LoadFace\]\[FID_(\w+)\]')


def render(body):
    """Decoded message -> boxed dialogue lines with speaker changes marked."""
    speaker, lines, cur = None, [], []
    for chunk in body.split('\n'):
        f = FID.search(chunk)
        if f:
            speaker = f.group(1)
        # ORDER IS LOAD-BEARING: the codes that carry MEANING are turned into their characters
        # first ([LF] is a real line break, [.] a real period, [A] the box break we must detect),
        # and only then does the catch-all sweep the rest. Naming individual staging codes here
        # is redundant -- [OpenLeft], [ToggleSmile] and friends all fall to `\[[^\]]*\]` below,
        # and an explicit list silently rots as new codes appear in the decomp.
        txt = FID.sub('', chunk)                       # speaker already captured above
        txt = txt.replace('[.]', '.').replace('[LF]', '\n').replace('[X]', '')
        boxbreak = '[A]' in txt
        txt = txt.replace('[A]', '')
        txt = re.sub(r'\[[^\]]*\]', '', txt).rstrip()
        if txt.strip():
            cur.append((speaker, txt))
        if boxbreak and cur:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return lines


# The channel is SCENE STATE, not a property of the text call -- which is the whole reason
# this tool was misleading twice. `TEXTSHOW` prints into whatever surface is currently up, so
# the scan tracks the backdrop and asks it at each text call:
#   * up   -- SetBackground(BG_X) / BACG(BG_X) / Text_BG(BG_X, id)   (events_script_utils.c:224:
#             EventScr_SetBackground is FADI + REMOVEPORTRAITS + BACG + FADU)
#   * down -- CLEAN, and CALL(EventScr_TextShowWithFadeIn), which is FADI + TEXTSTART + CLEAN +
#             FADU back onto the MAP (events_script_utils.c:211). `Text_BG` ends with that call,
#             so it puts its own backdrop away.
# `REMA` does NOT take a backdrop down -- it ends the TEXT. That is not a detail: vanilla Ch5's
# 0x9BF has a REMA before it and no SetBackground of its own, and it is still BG_TOWN.
# The scan is LINEAR and does not follow branches. Every branched scene in the decomp sets its
# backdrop before the branch (EventScr_Ch5_EndingScene does), so linear order is the state each
# arm actually sees; a scene that set a DIFFERENT backdrop per arm would need a real walk.
SCENE_STEP = re.compile(
    r'TEXTSHOW\((0x[0-9A-Fa-f]+)\)'
    r'|Text_BG\(\s*(\w+)\s*,\s*(0x[0-9A-Fa-f]+)\s*\)'
    r'|(?:SetBackground|BACG)\(\s*(\w+)\s*\)'
    r'|\b(CLEAN)\b'
    r'|CALL\(\s*(EventScr_TextShowWithFadeIn)\s*\)')


def scene_text_ids(path, name_fragment=None, src=None):
    """[(scene_name, [(msg_id, channel), ...])] in source order.

    channel is 'map' for an on-map bubble, else the BG_* backdrop the scene plays over --
    tracked as scene STATE (see SCENE_STEP), because a bare `TEXTSHOW` prints into whatever
    surface is up and reading the call alone reports every backdrop scene as on-map.
    `src` overrides reading `path` from disk -- main() passes the HEAD text, because
    eventscript headers are patched in place by the build too (ch1/ch2/ch3/prologue are in
    `PATCHED_DECOMP_FILES` today, and ch5's slot is where inject_ch04 hosts our Ch4).
    """
    src = open(path, encoding='utf-8').read() if src is None else src
    out = []
    for m in re.finditer(r'CONST_DATA EventListScr (\w+)\[\] = \{(.*?)\n\};', src, re.S):
        name, body = m.group(1), m.group(2)
        if name_fragment and name_fragment.lower() not in name.lower():
            continue
        ids, backdrop = [], None
        for c in SCENE_STEP.finditer(body):
            show, bg_id, bg_msg, set_bg, clean, fade_in = c.groups()
            if show:                                   # bare TEXTSHOW -- ask the surface
                ids.append((int(show, 16), backdrop or 'map'))
            elif bg_msg:                               # Text_BG: sets, shows, puts away
                ids.append((int(bg_msg, 16), bg_id))
                backdrop = None
            elif set_bg:
                backdrop = set_bg
            elif clean or fade_in:
                backdrop = None
        if ids:
            out.append((name, ids))
    return out


def main():
    ch = sys.argv[1] if len(sys.argv) > 1 else 'ch5'
    frag = sys.argv[2] if len(sys.argv) > 2 else None
    msgs = load_messages()
    relpath = 'src/events/%s-eventscript.h' % ch
    path = os.path.join(DEC, relpath)
    for name, ids in scene_text_ids(path, frag, src=_decomp_text(relpath)):
        print('=' * 72)
        print(name, '  (%d message(s))' % len(ids))
        print('=' * 72)
        boxes = 0
        for mid, chan in ids:
            body = msgs.get(mid)
            if body is None:
                print('  [MSG_%X missing]' % mid)
                continue
            print('  -- MSG_%X (%s)' % (mid, chan))
            for box in render(body):
                boxes += 1
                who = box[0][0] or '?'
                text = ' / '.join(t.replace('\n', ' / ') for _s, t in box)
                print('  %-12s %s' % (who + ':', text.strip()))
        print('  --- %d message(s), %d boxes ---\n' % (len(ids), boxes))


if __name__ == '__main__':
    main()
