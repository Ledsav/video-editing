"""Fit a song (yours, or one made with Suno / Udio) to the picture: cut on its beats, dipped (never stopped) under the
action, muffled for memories, plus extra cuts (the title card's bars) and a pitched voice line (a shout).

  python3 music_fit.py <project>/music.json

music.json (times: seconds or references, see audio.py; song times: seconds in the song, from `bin/vedit beats <song>`):
  {
    "song": "assets/audio/song.mp3",
    "clean": true,                                   // lift the AI sheen off the vocal (see clean())
    "out": "music/score.wav",
    "duration": 13.4,                                // optional: the edit's length
    "start": "op:end",                               // optional: silent before this (the title card has its own stem)
    "align": {"song": 14.095, "at": "fight:impact0"},   // one piece: the song plays so that song time `song` lands on `at`
    "pieces": [                                      // or explicit pieces (song time `from` placed at edit time `at`, up to `until`)
      {"from": 0.0, "at": 0, "until": 9.0, "fade_out": 0.02},
      {"from": 27.80, "at": 9.0, "until": 13.4, "fade_in": 0.02, "fade_out": 0.6}     // a jump to the final chord, downbeat to downbeat
    ],
    "dips": [{"from": "fight:shot2-0.06", "to": "fight:impact0+0.9", "db": -10}],     // under the action: down, not out
    "muffle": [{"from": 8.0, "to": 9.5}],                                             // heard as a memory (low-passed, quieter)
    "stems": [{"out": "music/op.wav", "from": 14.015, "dur": 3.5, "fade_out": 0.03}],  // extra cuts of the song (the title card)
    "voice": {"source": "assets/audio/shout.mp3", "from": 8.35, "at": "fight:shot2", "until": "fight:impact0-0.05",
              "pitch": 4, "out": "sfx/voice.wav"}                                      // semitones up: a boy's voice from a man's
  }
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from audio import SR, Project, bandpass, envelope, load, write


def clean(path):
    """less AI sheen on the voice: the stereo side (where generators leave swirly, phasey artefacts; the voice sits in the
    middle) cut by half from 1.5 to 9 kHz; a de-esser; the harsh band (6.5 kHz) and the hiss above 11 kHz down; the mud
    (320 Hz) down and the presence (2.8 kHz) up for a clearer voice; light glue compression."""
    chain = ('highpass=f=28,deesser=i=0.35:m=0.5:f=0.5:s=o,equalizer=f=320:t=q:w=1.0:g=-2.5,equalizer=f=2800:t=q:w=1.0:g=2,'
             'equalizer=f=6500:t=q:w=1.4:g=-2.5,highshelf=f=11000:g=-3,acompressor=threshold=-20dB:ratio=1.8:attack=15:release=200')
    x = load(path, chain)
    mid, side = (x[:, 0] + x[:, 1]) / 2, (x[:, 0] - x[:, 1]) / 2
    side = side - 0.5 * bandpass(side, 1500, 9000)
    return np.stack([mid + side, mid - side], 1)


def put(out, song, song_t, at, until, fade_in=0.01, fade_out=0.03, gain=1.0):
    """song from song_t placed at edit time `at` up to `until`, equal-power fades at both ends."""
    a, b = int(at * SR), min(out.shape[0], int(until * SR))
    s0 = int(song_t * SR)
    if s0 < 0:
        a, s0 = a - s0, 0
    seg = song[s0:s0 + max(0, b - a)].copy()
    n = len(seg)
    if n <= 0:
        return
    env = np.ones(n)
    fi, fo = min(n, int(fade_in * SR)), min(n, int(fade_out * SR))
    if fi:
        env[:fi] = np.sin(np.linspace(0, np.pi / 2, fi))
    if fo:
        env[-fo:] *= np.cos(np.linspace(0, np.pi / 2, fo))
    out[a:a + n] += seg * env[:, None] * gain


def main(path):
    plan_path = Path(path).resolve()
    plan = json.loads(plan_path.read_text())
    proj = Project(plan_path.parent)
    end = proj.t(plan.get('duration', proj.total))
    N = int(end * SR)
    if 'song' in plan and not proj.path(plan['song']).exists():
        sys.exit(f"no song at {proj.path(plan['song'])}: put the user's song there (or a placeholder: "
                 f"bin/vedit synth-music --mood hype --duration 40 --out {proj.path(plan['song'])})")
    if 'song' in plan:
        song = clean(proj.path(plan['song'])) if plan.get('clean') else load(proj.path(plan['song']))
        if plan.get('clean'):
            write(song, proj.path('work/song_clean.wav'))
        mus = np.zeros((N, 2))
        if 'align' in plan:
            at = proj.t(plan['align']['at'])
            off = at - plan['align']['song']                     # edit time of song time 0
            put(mus, song, max(0.0, -off), max(0.0, off), end, fade_in=0.0 if off >= 0 else 0.02, fade_out=plan['align'].get('fade_out', 0.5))
        for p in plan.get('pieces', []):
            put(mus, song, p['from'], proj.t(p['at']), proj.t(p.get('until', end)), p.get('fade_in', 0.01), p.get('fade_out', 0.03), p.get('gain', 1.0))
        if 'start' in plan:                                     # silent before `start` (e.g. under the title card, which has its own stem)
            a = int(proj.t(plan['start']) * SR)
            mus[:a] = 0
            k = min(int(0.01 * SR), N - a)
            mus[a:a + k] *= np.linspace(0, 1, k)[:, None]
        if plan.get('dips'):
            pts = [(0, 0)]
            for d in plan['dips']:
                a, b = proj.t(d['from']), proj.t(d['to'])
                pts += [(a - 0.06, 0), (a, d.get('db', -10)), (b, d.get('db', -10)), (b + d.get('release', 0.1), 0)]
            mus *= envelope(N, sorted(pts), 0.06)[:, None]
        for m in plan.get('muffle', []):
            a, b = int(proj.t(m['from']) * SR), int(proj.t(m['to']) * SR)
            w = np.zeros(N)
            w[a:b] = 1
            k = np.hanning(int(0.15 * SR))
            w = np.convolve(w, k / k.sum(), 'same')
            muff = np.stack([bandpass(mus[:, c], 20, m.get('cutoff', 1100)) for c in range(2)], 1) * m.get('gain', 0.6)
            mus = mus * (1 - w[:, None]) + muff * w[:, None]
        write(mus, proj.path(plan.get('out', 'music/score.wav')), plan.get('peak', 0.95))
        for s in plan.get('stems', []):
            n = int(s['dur'] * SR)
            seg = song[int(s['from'] * SR):int(s['from'] * SR) + n].copy()
            fo = int(s.get('fade_out', 0.03) * SR)
            if fo:
                seg[-fo:] *= np.cos(np.linspace(0, np.pi / 2, fo))[:, None]
            write(seg, proj.path(s['out']), s.get('peak', 0.95))
    v = plan.get('voice')
    if v:
        st = v.get('pitch', 0)
        af = f'rubberband=pitch={2 ** (st / 12):.5f}:formant=shifted:pitchq=quality,highpass=f=220' if st else None
        try:
            voice = load(proj.path(v['source']), af)
        except subprocess.CalledProcessError:              # ffmpeg without librubberband: asetrate + atempo (formants move too)
            r = 2 ** (st / 12)
            voice = load(proj.path(v['source']), f'asetrate={int(SR * r)},aresample={SR},atempo={1 / r:.5f}' if st else None)
        out = np.zeros((N, 2))
        put(out, voice, v['from'], proj.t(v['at']), proj.t(v['until']), v.get('fade_in', 0.02), v.get('fade_out', 0.03))
        write(out, proj.path(v.get('out', 'sfx/voice.wav')), v.get('peak', 0.98))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])
