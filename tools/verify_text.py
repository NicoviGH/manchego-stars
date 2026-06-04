#!/usr/bin/env python3
"""Decode FE8 message text straight out of a built ROM and verify it is clean.

Why this exists: the text path is texts.txt -> textprocess.py -> src/msg_data.c
(gMsgTable + gMsgHuffmanTable) -> ROM. A stale/partial build can ship a
tree<->data mismatch that renders every custom message as garbage in-game. This
tool reproduces the game's own Huffman decoder (see fireemblem8u
scripts/texttools/textdecoder.py and the DecodeString ARM routine) and decodes
messages by symbol address from the .map, so we can confirm text is correct
WITHOUT loading mGBA.

Usage:
  tools/verify_text.py                 # sweep all messages, report runaways
  tools/verify_text.py 0x212 0x213     # decode specific message indices
"""

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(REPO, 'fireemblem8u', 'fireemblem8.map')
ROM = os.path.join(REPO, 'fireemblem8u', 'fireemblem8.gba')
BASE = 0x08000000
MSG_COUNT = 0xD4C
# Longest legit vanilla message (an epilogue paragraph) is ~2133 decoded values;
# anything past this is almost certainly a tree<->data mismatch.
RUNAWAY_LEN = 2600


def find_syms(names):
    syms = {}
    pat = re.compile(r'^\s+0x([0-9a-fA-F]{8,16})\s+(\S+)\s*$')
    with open(MAP) as f:
        for line in f:
            m = pat.match(line)
            if m:
                name = m.group(2)
                if name in names and name not in syms:
                    syms[name] = int(m.group(1), 16)
    return syms


def is_leaf(node):
    return (node & 0xFFFF0000) == 0xFFFF0000


def decode(rom, table_off, root_idx, start_off):
    def node(i):
        return int.from_bytes(rom[table_off + 4 * i:table_off + 4 * i + 4], 'little')

    out = []
    bitpos = -1
    cur = root_idx
    off = start_off
    cur_byte = 0
    guard = 0
    while True:
        guard += 1
        if guard > 200000:
            out.append('OVERRUN')
            break
        if bitpos < 0:
            if off >= len(rom):
                out.append('RANBOUT')
                break
            cur_byte = rom[off]
            off += 1
            bitpos = 7
        bit = cur_byte & 1
        cur_byte >>= 1
        bitpos -= 1
        cur = node(cur) & 0xFFFF if bit == 0 else (node(cur) >> 16) & 0xFFFF
        nd = node(cur)
        if is_leaf(nd):
            data = nd & 0xFFFF
            out.append(data)
            if data == 0:
                break
            cur = root_idx
    return out


def render(vals):
    s = ''
    for v in vals:
        if isinstance(v, str):
            s += '<%s>' % v
            continue
        if v == 0:
            break
        bytes_ = [v & 0xFF] if v < 0x100 else [v & 0xFF, (v >> 8) & 0xFF]
        for b in bytes_:
            s += chr(b) if 0x20 <= b < 0x7F else '[%02X]' % b
    return s


def load():
    syms = find_syms({'gMsgHuffmanTable', 'gMsgHuffmanTableRoot', 'gMsgTable'})
    rom = open(ROM, 'rb').read()
    ht = syms['gMsgHuffmanTable'] - BASE
    gt = syms['gMsgTable'] - BASE
    root_addr = int.from_bytes(rom[syms['gMsgHuffmanTableRoot'] - BASE:][:4], 'little')
    root_idx = (root_addr - syms['gMsgHuffmanTable']) // 4
    return rom, ht, gt, root_idx


def msg_offset(rom, gt, idx):
    return int.from_bytes(rom[gt + 4 * idx:gt + 4 * idx + 4], 'little') - BASE


def main(argv):
    if not os.path.isfile(ROM):
        sys.exit('ERROR: no ROM at %s -- build first (make)' % ROM)
    rom, ht, gt, root_idx = load()

    if argv:
        for idx in (int(a, 0) for a in argv):
            vals = decode(rom, ht, root_idx, msg_offset(rom, gt, idx))
            print('MSG_%03X: %r' % (idx, render(vals)))
        return 0

    bad = 0
    for idx in range(MSG_COUNT):
        vals = decode(rom, ht, root_idx, msg_offset(rom, gt, idx))
        runaway = any(isinstance(v, str) for v in vals) or len(vals) > RUNAWAY_LEN
        if runaway:
            bad += 1
            if bad <= 10:
                print('  RUNAWAY MSG_%03X len=%d: %r' % (idx, len(vals), render(vals)[:80]))
    print('SWEEP: %d messages, %d runaway' % (MSG_COUNT, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
