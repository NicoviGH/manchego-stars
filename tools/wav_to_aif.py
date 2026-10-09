#!/usr/bin/env python3
"""Turn a mono WAV into the AIFF the decomp's sample rule eats (`sound/%.bin: sound/%.aif`).

The GBA's direct-sound engine plays 8-bit SIGNED PCM, and the decomp's `aif2pcm` reads an AIFF
(big-endian, signed) and writes that, with the sample rate in the header as `rate << 10`. A WAV
stores 8-bit audio UNSIGNED, so the one real step here is the -128 shift; a 16-bit WAV is
narrowed to its high byte. The rate is carried through unchanged: the voice that plays it sits
at base key 60, so a Cn3 note plays the sample at exactly the rate it was recorded at.

No loop markers are written, so `aif2pcm` emits a one-shot sample (flags 0), which is what a cry
or a roar is.

Usage:
    python3 tools/wav_to_aif.py kyogre.wav campaigns/<c>/sounds/ms_kyogre_cry.aif
"""
import aifc
import sys
import wave


def wav_to_aif(src, dst):
    with wave.open(src, 'rb') as w:
        if w.getnchannels() != 1:
            sys.exit('ERROR: %s is not mono (%d channels); aif2pcm takes one'
                     % (src, w.getnchannels()))
        width, rate, frames = w.getsampwidth(), w.getframerate(), w.readframes(w.getnframes())
    if width == 1:
        pcm = bytes((b - 128) & 0xFF for b in frames)
    elif width == 2:
        pcm = bytes(frames[i + 1] for i in range(0, len(frames), 2))   # little-endian high byte
    else:
        sys.exit('ERROR: %s is %d-bit; take 8 or 16' % (src, width * 8))
    a = aifc.open(dst, 'wb')
    try:
        a.aiff()
        a.setnchannels(1)
        a.setsampwidth(1)
        a.setframerate(rate)
        a.writeframes(pcm)
    finally:
        a.close()
    return rate, len(pcm)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    rate, n = wav_to_aif(sys.argv[1], sys.argv[2])
    print('%s: %d Hz, %d samples (%.2fs)' % (sys.argv[2], rate, n, n / float(rate)))
