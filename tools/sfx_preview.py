#!/usr/bin/env python3
"""Render vanilla FE8 sound effects to WAV, straight from the decomp -- no ROM, no emulator.

WHY THIS EXISTS. Picking a sound effect used to cost a ROM build plus a watched playtest run
per candidate, and Nicolas sat through several of those for ch05's moose bellow (2026-08-15)
before asking for something he could just listen to. Every ingredient is already in the
decomp, so nothing needs to be captured from a running game:

    song id -> sound/song_table.s          (index IS the id; entry 0 is dummy_song)
            -> sound/songs/midi/songNNN_*.s  -- its voicegroup, VOICE and note
            -> sound/voicegroups/voicegroupNNN.s -- that voice's SAMPLE and base key
            -> sound/direct_sound_samples/<name>.bin -- 8-bit signed PCM + a GBA header

THE HEADER is four little-endian words: type, pitch, loop start, length. `pitch` is the
sample rate shifted left by 10, so rate = pitch / 1024. Playback rate is then scaled by the
interval between the note the song plays and the sample's own base key -- which is not a
detail: ch05's dragon scream is a 10.5 kHz sample played seven semitones up, and half of what
makes a sound read as "big" or "small" is that ratio.

!! THE BATTLE-ANIMATION SOUND OPCODE IS A DIFFERENT TABLE. `banim_code_sound_*` in
banim_code.inc encodes `0x850000XX`, and XX is NOT a song id. Reading it as one is how this
session ended up auditioning `se_sys_hp2` (an HP-bar tick) as a monster roar and calling it a
wolf. Song ids come from `song_table.s` and nowhere else.

Usage:
    tools/sfx_preview.py --grep dragon --out /tmp/sfx      # every song whose name matches
    tools/sfx_preview.py --ids 0x26A,0x2F5 --out /tmp/sfx
    tools/sfx_preview.py --grep 'dragon|bomb' --html /tmp/sfx.html   # a page with play buttons
"""
import argparse
import base64
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DECOMP = os.path.join(os.path.dirname(HERE), 'fireemblem8u')


def song_table():
    """[song label] indexed by song id -- the table's ORDER is the id space."""
    path = os.path.join(DECOMP, 'sound', 'song_table.s')
    with open(path, encoding='utf-8', errors='replace') as fh:
        return [l.split()[1].rstrip(',') for l in fh if l.strip().startswith('song ')]


def note_numbers():
    """MPlayDef's note names -> midi numbers (Cn3 = 60)."""
    path = os.path.join(DECOMP, 'include', 'MPlayDef.s')
    out = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'\s*\.equ\s+([A-G][nsb]?-?\d),\s*(\d+)', line)
            if m:
                out[m.group(1)] = int(m.group(2))
    return out


def song_voice_and_notes(label):
    """(voicegroup number, [(voice, note name), ...]) for one song's sequence."""
    path = os.path.join(DECOMP, 'sound', 'songs', 'midi', label + '.s')
    if not os.path.isfile(path):
        return None, [], False
    with open(path, encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    grp = re.search(r'_grp,\s*voicegroup(\d+)', text)
    events, voice = [], None
    # TIE is a note too -- a HELD one. The rumble ch05 uses (song618) has no Nxx at all, only a
    # TIE under a run of pitch bends, so a regex that knows only Nxx silently skips it.
    for m in re.finditer(r'\.byte\s+(VOICE|TIE|N\d+)\s*,\s*([A-Za-z0-9_+-]+)', text):
        if m.group(1) == 'VOICE':
            voice = int(m.group(2))
        elif voice is not None:
            events.append((voice, m.group(2)))
    return (int(grp.group(1)) if grp else None), events, bool(re.search(r'\bBEND\b', text))


def voice_sample(group_no, voice_no):
    """(sample label, base key) for one voicegroup entry, or (None, None)."""
    path = os.path.join(DECOMP, 'sound', 'voicegroups', 'voicegroup%03d.s' % group_no)
    if not os.path.isfile(path):
        return None, None
    with open(path, encoding='utf-8', errors='replace') as fh:
        rows = [l.strip() for l in fh if l.strip().startswith('voice_')]
    if voice_no >= len(rows):
        return None, None
    row = rows[voice_no]
    m = re.match(r'voice_directsound\s+(\d+),\s*\d+,\s*DirectSoundData_(\w+)', row)
    if not m:
        return None, None          # square/noise/programmable wave -- no PCM to export
    return m.group(2), int(m.group(1))


def sample_pcm(name):
    """(signed-8bit bytes, sample rate) from a decomp DirectSound .bin."""
    path = os.path.join(DECOMP, 'sound', 'direct_sound_samples', name + '.bin')
    if not os.path.isfile(path):
        return None, None
    with open(path, 'rb') as fh:
        raw = fh.read()
    _type, pitch, _loop, length = struct.unpack('<IIII', raw[:16])
    return raw[16:16 + length], pitch / 1024.0


def wav_bytes(pcm_signed, rate):
    """8-bit SIGNED GBA PCM -> a RIFF WAV (which wants UNSIGNED 8-bit)."""
    data = bytes((b + 128) & 0xFF for b in pcm_signed)
    rate = int(max(1, round(rate)))
    hdr = (b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt '
           + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate, 1, 8)
           + b'data' + struct.pack('<I', len(data)))
    return hdr + data


def render(song_id, labels, notes):
    """One song id -> (label, wav, sample name, semitone shift, caveat, seconds, envelope).

    None when there is nothing to render: a dummy_song slot, or a voice that is a square/noise/
    programmable-wave channel rather than a PCM sample. ch05's own rumble is the latter -- which
    is also why it has weight the sampled creature cries lack, and why it cannot be previewed
    here without synthesising something that is not the sound.
    """
    if song_id >= len(labels):
        return None
    label = labels[song_id]
    if label == 'dummy_song':
        return None
    grp, events, bent = song_voice_and_notes(label)
    if grp is None or not events:
        return None
    voice, note_name = events[0]
    sample, base = voice_sample(grp, voice)
    if sample is None:
        return None
    pcm, rate = sample_pcm(sample)
    if not pcm:
        return None
    key = notes.get(note_name)
    shift = 0 if key is None else key - base
    caveat = '' if len(events) == 1 else ' (first of %d notes)' % len(events)
    # A bend SWEEPS the pitch as it plays, which a static resample cannot reproduce. Say so
    # rather than present an approximation as the sound -- ch05's own rumble is one of these.
    if bent:
        caveat += ' (pitch-bent in game; preview is the unbent sample)'
    play_rate = rate * (2.0 ** (shift / 12.0))
    return (label, wav_bytes(pcm, play_rate), sample, shift, caveat,
            len(pcm) / play_rate, envelope(pcm))


def envelope(pcm, buckets=56):
    """Peak amplitude per bucket, 0..1 -- the SHAPE of the sound.

    Worth drawing rather than decorating with: length and attack are most of what makes a
    sound read as big or small, and both are visible here before anything is played."""
    if not pcm:
        return [0.0] * buckets
    step = max(1, len(pcm) // buckets)
    out = []
    for i in range(0, step * buckets, step):
        chunk = pcm[i:i + step]
        peak = max((abs(b - 256 if b > 127 else b) for b in chunk), default=0)
        out.append(min(1.0, peak / 128.0))
    return (out + [0.0] * buckets)[:buckets]


PAGE_CSS = """<title>Moose Bellow Casting</title>
<style>
:root{
  --ground:#f5f4f1; --panel:#ffffff; --edge:#ddd9d2; --edge-hi:#c6c0b6;
  --ink:#191b20; --ink-dim:#5f646d; --ember:#b03a29; --frost:#2c7c8c;
  --wave:#b8b2a8;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#14161b; --panel:#1c1f26; --edge:#2b2f38; --edge-hi:#3d434f;
  --ink:#e8e6e2; --ink-dim:#8b9099; --ember:#d9563f; --frost:#5fa8b8;
  --wave:#454b57;
}}
:root[data-theme="dark"]{
  --ground:#14161b; --panel:#1c1f26; --edge:#2b2f38; --edge-hi:#3d434f;
  --ink:#e8e6e2; --ink-dim:#8b9099; --ember:#d9563f; --frost:#5fa8b8;
  --wave:#454b57;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ground);color:var(--ink);
  font:16px/1.55 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  padding:2.5rem 1.1rem 5rem}
.wrap{max-width:52rem;margin:0 auto;display:flex;flex-direction:column;gap:2rem}
header{display:flex;flex-direction:column;gap:.5rem}
h1{margin:0;font-size:1.75rem;letter-spacing:-.015em;text-wrap:balance}
.lede{margin:0;color:var(--ink-dim);max-width:60ch}
.brief{background:var(--panel);border:1px solid var(--edge);border-left:3px solid var(--ember);
  border-radius:4px;padding:.9rem 1.05rem;color:var(--ink-dim);font-size:.92rem;
  display:flex;flex-direction:column;gap:.5rem}
.brief strong{color:var(--ink);font-weight:600}
code{font:.82em ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--ink)}
section{display:flex;flex-direction:column;gap:.45rem}
.family{display:flex;align-items:baseline;gap:.6rem;font-size:.72rem;letter-spacing:.13em;
  text-transform:uppercase;color:var(--ink-dim);border-bottom:1px solid var(--edge);
  padding-bottom:.45rem;margin-bottom:.15rem}
.family .n{font-variant-numeric:tabular-nums;color:var(--edge-hi)}
.cut{display:grid;grid-template-columns:2.5rem minmax(0,1fr) 7rem 4rem 3.6rem;
  align-items:center;gap:.8rem;background:var(--panel);border:1px solid var(--edge);
  border-radius:4px;padding:.55rem .7rem}
.cut.on{border-color:var(--frost);box-shadow:inset 3px 0 0 var(--frost)}
.play{width:2.5rem;height:2.5rem;border-radius:50%;border:1px solid var(--edge-hi);
  background:transparent;color:var(--ink);cursor:pointer;display:grid;place-items:center;
  padding:0;transition:border-color .12s,color .12s,background .12s}
.play:hover{border-color:var(--ember);color:var(--ember)}
.play:focus-visible{outline:2px solid var(--frost);outline-offset:2px}
.cut.on .play{border-color:var(--frost);color:var(--frost)}
.play svg{width:.85rem;height:.85rem;fill:currentColor}
.name{font:13px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-word}
.prov{color:var(--ink-dim);font-size:.74rem;margin-top:.15rem}
.wave{width:100%;height:2rem;display:block}
.dur{font:12px/1 ui-monospace,Menlo,monospace;color:var(--ink-dim);
  font-variant-numeric:tabular-nums;text-align:right}
.id{font:12px/1 ui-monospace,Menlo,monospace;color:var(--ink-dim);border:1px solid var(--edge);
  border-radius:3px;padding:.32rem .3rem;text-align:center;font-variant-numeric:tabular-nums}
.cut.mute{opacity:.72}
.cut.mute .play{border-style:dashed;cursor:not-allowed;color:var(--ink-dim)}
@media (max-width:34rem){
  .cut{grid-template-columns:2.5rem minmax(0,1fr) 3.4rem;row-gap:.5rem}
  .wave{grid-column:1 / -1;order:5}
  .dur{display:none}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
"""

PLAY_SVG = '<svg viewBox="0 0 12 14" aria-hidden="true"><path d="M0 0l12 7-12 7z"/></svg>'


def _wave_svg(env):
    """The envelope as a bar sparkline -- length and attack, before anything is played."""
    n = len(env)
    bars = []
    for i, v in enumerate(env):
        h = max(1.0, v * 26.0)
        x = i * (100.0 / n)
        bars.append('<rect x="%.2f%%" y="%.2f" width="%.2f%%" height="%.2f" rx=".6"/>'
                    % (x, (28 - h) / 2, 100.0 / n * 0.62, h))
    return ('<svg class="wave" viewBox="0 0 100 28" preserveAspectRatio="none" '
            'aria-hidden="true" fill="var(--wave)">%s</svg>' % ''.join(bars))


def build_html(items, out_path):
    fams = [
        ('Dragon', r'dragon'),
        ('Demon King & summons', r'mao|mon_call|bgl'),
        ('Beasts & undead', r'mon_|zombie|cyc|gog|bae|sks|mdg'),
        ('Impact & collapse', r'bomb|shake|fall|thunder'),
    ]
    placed, groups = set(), []
    for title, pat in fams:
        rows = [it for it in items if re.search(pat, it[1], re.I) and it[0] not in placed]
        placed.update(it[0] for it in rows)
        if rows:
            groups.append((title, rows))
    rest = [it for it in items if it[0] not in placed]
    if rest:
        groups.append(('Everything else', rest))

    out = [PAGE_CSS, '<div class="wrap">', '<header>',
           '<h1>Moose Bellow Casting</h1>',
           '<p class="lede">Vanilla FE8 sound effects, rendered out of the decomp. '
           'Press play; the id in the right-hand column is what goes into '
           '<code>SOUN(...)</code>.</p></header>',
           '<div class="brief"><span><strong>These are the real samples at the real pitch.</strong> '
           'Each is the PCM the effect actually plays, resampled by the interval between the note '
           'its sequence uses and the sample&rsquo;s own base key &mdash; often most of why a sound '
           'reads as big or small.</span>'
           '<span>The waveform is the sound&rsquo;s envelope, so length and attack are visible '
           'before you play anything.</span></div>']
    for title, rows in groups:
        out.append('<section><div class="family">%s <span class="n">%d</span></div>'
                   % (title, len(rows)))
        for sid, label, b64, sample, shift, caveat, dur, env in rows:
            pretty = re.sub(r'^song\d+_', '', label)
            prov = '%s &middot; %+d st%s' % (sample, shift, caveat)
            out.append(
                '<div class="cut">'
                '<button class="play" data-src="data:audio/wav;base64,%s" '
                'aria-label="Play %s">%s</button>'
                '<div><div class="name">%s</div><div class="prov">%s</div></div>'
                '%s<div class="dur">%.2fs</div><div class="id">%03X</div></div>'
                % (b64, pretty, PLAY_SVG, pretty, prov, _wave_svg(env), dur, sid))
        out.append('</section>')
    out.append("""</div><script>
var cur=null,curRow=null;
function stop(){if(cur){cur.pause();cur=null;}if(curRow){curRow.classList.remove("on");curRow=null;}}
document.addEventListener("click",function(e){
  var b=e.target.closest("button.play");if(!b||b.disabled)return;
  var row=b.closest(".cut"),was=(curRow===row);stop();if(was)return;
  var a=new Audio(b.dataset.src);cur=a;curRow=row;row.classList.add("on");
  a.play();a.onended=stop;});
</script>""")
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out))
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--grep', help='regex over song NAMES')
    ap.add_argument('--ids', help='comma-separated song ids (0x.. or decimal)')
    ap.add_argument('--out', help='directory to write .wav files into')
    ap.add_argument('--html', help='write a play-button page here')
    a = ap.parse_args(argv)
    labels, notes = song_table(), note_numbers()
    wanted = []
    if a.ids:
        wanted = [int(x, 0) for x in a.ids.split(',')]
    elif a.grep:
        pat = re.compile(a.grep, re.I)
        wanted = [i for i, n in enumerate(labels) if pat.search(n)]
    else:
        sys.exit('ERROR: pass --grep or --ids')
    items, skipped = [], []
    for sid in wanted:
        got = render(sid, labels, notes)
        if not got:
            skipped.append(sid)
            continue
        label, wav, sample, shift, caveat, dur, env = got
        items.append((sid, label, base64.b64encode(wav).decode(), sample, shift,
                      caveat, dur, env))
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            with open(os.path.join(a.out, '%03X_%s.wav' % (sid, label)), 'wb') as fh:
                fh.write(wav)
    if a.html:
        build_html(items, a.html)
        print('wrote %s (%d sounds)' % (a.html, len(items)))
    if a.out:
        print('wrote %d wav(s) to %s' % (len(items), a.out))
    if skipped:
        print('skipped %d (dummy, no PCM voice, or synthesised): %s'
              % (len(skipped), ', '.join('0x%03X' % s for s in skipped[:12])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
