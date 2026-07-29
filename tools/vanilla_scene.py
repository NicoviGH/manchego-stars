#!/usr/bin/env python3
"""Print a vanilla FE8 chapter's scenes as readable dialogue, from the decomp.

Pairs an eventscript's scene blocks (message ids, in source order) with the
decoded message bodies in texts/texts.txt, so our authored scenes can be staged
beside the vanilla ones for pacing reference (dialogue-pass §Inputs #4).

A scene mixes two text CHANNELS and both are reported, because the channel sets
the line width we hand-box to:
  * TEXTSHOW  -- on-map, units staged by LOAD1; bubbles wrap at 29 chars
  * Text_BG   -- a still backdrop (BG_*); full-width text, wraps ~42
Reading only TEXTSHOW hides whole scenes: FE8 Ch5's opening puts the two Grado
command scenes (0x9BC Glen/Saar, 0x9BD Glen/Cormag) on Text_BG, so a
TEXTSHOW-only scan reports its 11-message opening as 8.

    python3 vanilla_scene.py ch5 [SceneNameFragment]
"""
import re
import sys
import os

DEC = 'fireemblem8u'


def load_messages():
    """MSG id (int) -> raw body text."""
    path = os.path.join(DEC, 'texts', 'texts.txt')
    out, cur, buf = {}, None, []
    for line in open(path, encoding='utf-8', errors='replace'):
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
        txt = chunk
        txt = FID.sub('', txt)
        txt = re.sub(r'\[ToggleMouthMove\]', '', txt)
        txt = re.sub(r'\[ToggleSmile\]', '', txt)
        txt = re.sub(r'\[(Open|Close|Move|Clear|Load|Break|CR|STc|Sound|Wait)\w*\]', '', txt)
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


MSG_CALL = re.compile(r'TEXTSHOW\((0x[0-9A-Fa-f]+)\)'
                      r'|Text_BG\(\s*(\w+)\s*,\s*(0x[0-9A-Fa-f]+)\s*\)')


def scene_text_ids(path, name_fragment=None):
    """[(scene_name, [(msg_id, channel), ...])] in source order.

    channel is 'map' for an on-map TEXTSHOW, else the BG_* backdrop name.
    """
    src = open(path, encoding='utf-8').read()
    out = []
    for m in re.finditer(r'CONST_DATA EventListScr (\w+)\[\] = \{(.*?)\n\};', src, re.S):
        name, body = m.group(1), m.group(2)
        if name_fragment and name_fragment.lower() not in name.lower():
            continue
        ids = []
        for c in MSG_CALL.finditer(body):
            if c.group(1):
                ids.append((int(c.group(1), 16), 'map'))
            else:
                ids.append((int(c.group(3), 16), c.group(2)))
        if ids:
            out.append((name, ids))
    return out


def main():
    ch = sys.argv[1] if len(sys.argv) > 1 else 'ch5'
    frag = sys.argv[2] if len(sys.argv) > 2 else None
    msgs = load_messages()
    path = os.path.join(DEC, 'src', 'events', '%s-eventscript.h' % ch)
    for name, ids in scene_text_ids(path, frag):
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
