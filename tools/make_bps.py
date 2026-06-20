#!/usr/bin/env python3
"""Pure-Python BPS patch encoder (#37/#59) -- no external patcher (flips/beat) needed.

BPS is the standard ROM-hack delta format. We publish a small `.bps` patch (which contains
NO copyrighted ROM bytes, only the delta) on GitHub Releases; a tester applies it to their
own legal FE8 ROM to get Manchego Stars. This keeps the public artifact legal while the
pre-patched `.gba` stays a private link (docs/decisions.md -> Distribution & Scope).

We emit only SourceRead (copy unchanged bytes from the source at the current output offset)
and TargetRead (literal new bytes) actions. That's valid BPS and near-optimal for our case:
the built ROM is the vanilla ROM the same size with in-place edits, so a byte-aligned diff is
exactly what's needed -- no block-move (SourceCopy/TargetCopy) heuristics required.

Format (byuu's BPS spec):
    "BPS1" | varint source-size | varint target-size | varint metadata-size | metadata
    actions... | u32 source-crc | u32 target-crc | u32 patch-crc   (all little-endian)
Each action varint = ((length - 1) << 2) | command, command 0=SourceRead, 1=TargetRead.

CLI:  make_bps.py <source.gba> <target.gba> <out.bps>   (self-verifies before writing)
"""
import struct
import sys
import zlib


def encode_varint(n):
    """BPS variable-length number: 7 data bits/byte, high bit = stop, with the -1 carry."""
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def decode_varint(buf, pos):
    """Inverse of encode_varint. Returns (value, next_pos)."""
    data = 0
    shift = 1
    while True:
        x = buf[pos]
        pos += 1
        data += (x & 0x7F) * shift
        if x & 0x80:
            return data, pos
        shift <<= 7
        data += shift


def create_patch(source, target, metadata=b''):
    """Build a BPS patch turning `source` bytes into `target` bytes."""
    patch = bytearray(b'BPS1')
    patch += encode_varint(len(source))
    patch += encode_varint(len(target))
    patch += encode_varint(len(metadata))
    patch += metadata

    common = min(len(source), len(target))
    out = 0  # current output (target) offset

    def emit_target_read(start, end):
        patch.extend(encode_varint(((end - start) - 1) << 2 | 1))
        patch.extend(target[start:end])

    while out < len(target):
        if out < common and source[out] == target[out]:
            # extend a run of bytes identical to the source at this offset -> SourceRead
            run = out
            while run < common and source[run] == target[run]:
                run += 1
            patch += encode_varint(((run - out) - 1) << 2 | 0)
            out = run
        else:
            # extend a run that differs (or is past the source) -> TargetRead (literals)
            run = out
            while run < len(target) and not (run < common and source[run] == target[run]):
                run += 1
            emit_target_read(out, run)
            out = run

    patch += struct.pack('<I', zlib.crc32(source) & 0xFFFFFFFF)
    patch += struct.pack('<I', zlib.crc32(target) & 0xFFFFFFFF)
    patch += struct.pack('<I', zlib.crc32(bytes(patch)) & 0xFFFFFFFF)
    return bytes(patch)


def apply_patch(patch, source):
    """Apply a BPS `patch` to `source`, verifying all three CRC32s. Raises ValueError on any
    mismatch -- used as the build's ship-blocking self-verify. Supports all four BPS actions."""
    if patch[:4] != b'BPS1':
        raise ValueError('not a BPS patch (bad magic)')
    src_crc, tgt_crc, patch_crc = struct.unpack('<III', patch[-12:])
    if zlib.crc32(patch[:-4]) & 0xFFFFFFFF != patch_crc:
        raise ValueError('patch is corrupt (patch checksum mismatch)')
    if zlib.crc32(source) & 0xFFFFFFFF != src_crc:
        raise ValueError('wrong source ROM (source checksum mismatch)')

    pos = 4
    source_size, pos = decode_varint(patch, pos)
    target_size, pos = decode_varint(patch, pos)
    meta_size, pos = decode_varint(patch, pos)
    pos += meta_size

    out = bytearray()
    src_rel = 0
    tgt_rel = 0
    end = len(patch) - 12
    while pos < end:
        data, pos = decode_varint(patch, pos)
        command = data & 3
        length = (data >> 2) + 1
        if command == 0:        # SourceRead
            out += source[len(out):len(out) + length]
        elif command == 1:      # TargetRead
            out += patch[pos:pos + length]
            pos += length
        elif command == 2:      # SourceCopy
            off, pos = decode_varint(patch, pos)
            src_rel += (-1 if off & 1 else 1) * (off >> 1)
            out += source[src_rel:src_rel + length]
            src_rel += length
        else:                   # TargetCopy
            off, pos = decode_varint(patch, pos)
            tgt_rel += (-1 if off & 1 else 1) * (off >> 1)
            for _ in range(length):
                out.append(out[tgt_rel])
                tgt_rel += 1

    result = bytes(out)
    if zlib.crc32(result) & 0xFFFFFFFF != tgt_crc:
        raise ValueError('result checksum mismatch (patch did not reproduce the target)')
    return result


def main(argv):
    if len(argv) != 4:
        print('usage: make_bps.py <source.gba> <target.gba> <out.bps>', file=sys.stderr)
        return 2
    source = open(argv[1], 'rb').read()
    target = open(argv[2], 'rb').read()
    patch = create_patch(source, target)
    if apply_patch(patch, source) != target:   # self-verify before writing
        print('ERROR: BPS self-verify failed -- refusing to write %s' % argv[3], file=sys.stderr)
        return 1
    open(argv[3], 'wb').write(patch)
    print('>> wrote %s (%d bytes, %.1f%% of the ROM)'
          % (argv[3], len(patch), 100.0 * len(patch) / max(1, len(target))))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
