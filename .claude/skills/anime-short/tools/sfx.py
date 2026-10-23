"""Anime sound design from a cue sheet, locked to the picture: one stereo stem (48 kHz, edit time 0 = sample 0).

  python3 sfx.py <project>/sound.json

sound.json:
  {
    "out": "sfx/sfx.wav",                      // relative to the project
    "duration": 13.4,                          // optional: defaults to the edit's length
    "peak": 0.9,
    "cues": [
      {"type": "charge", "end": "fight:impact0", "dur": 1.0},      // power charge, cut to silence `gap` (0.05) before `end`
      {"type": "cannon", "at": "fight:impact0"},                    // the hit as a cannon blast
      {"type": "ring", "at": "fight:impact0", "dur": 1.2, "gain": 0.4},   // time-freeze tinnitus under an ink hold
      {"type": "taiko", "at": ["fight:impact0+0.25", "fight:impact0+0.5"], "gain": 0.3},   // one hit per new drawing
      {"type": "whoosh", "at": "fight:shot1+0.3", "dur": 0.4, "f0": 400, "f1": 3000},
      {"type": "file", "path": "assets/audio/door.wav", "at": 2.0}
    ],
    "duck": [{"from": "fight:impact0-0.05", "to": "fight:impact0+0.1", "db": -10, "release": 0.3}]   // dips the whole stem
  }
Times: seconds or references (see audio.py): "<clip>+s", "<clip>:impactN", "<clip>:shotN", "<clip>:end", each with +/- offset.
Every cue takes "at" (a time or a list), "gain" (linear), "pan" (-1..1); "seed" changes the random parts.

Cue types: punch, cannon, charge, whoosh, swish, ring, taiko, crash, sub_drop, debris, rumble, vwoom, reverse_swell,
riser, sparkle, heartbeat, footstep, stamp, file. Design notes (what reads as anime): references/sound-and-music.md.
"""
import json
import sys
from pathlib import Path

import numpy as np

from audio import SR, Project, bandpass, envelope, load, place, soft_band, stereo, write

rng = np.random.default_rng(11)


def tt(d):
    return np.arange(int(d * SR)) / SR


def stft_filter(x, center_fn, width_oct=0.6):
    """time-varying band-pass: center_fn(t) -> Hz."""
    w, hop = 2048, 512
    win = np.hanning(w)
    pad = np.concatenate([np.zeros(w), x, np.zeros(w)])
    out, norm = np.zeros(len(pad)), np.zeros(len(pad))
    lf = np.log2(np.maximum(np.fft.rfftfreq(w, 1 / SR), 1))
    for i in range(1 + (len(pad) - w) // hop):
        a = i * hop
        c = np.log2(max(center_fn(max((a - w / 2) / SR, 0)), 20))
        mask = np.exp(-0.5 * ((lf - c) / width_oct) ** 2)
        out[a:a + w] += np.fft.irfft(np.fft.rfft(pad[a:a + w] * win) * mask, n=w) * win
        norm[a:a + w] += win ** 2
    return (out / np.maximum(norm, 1e-6))[w:w + len(x)]


def reverb(x, length=1.6, decay=0.6, bright=7000, seed=3):
    r = np.random.default_rng(seed)
    t = tt(length)
    ir = soft_band(r.standard_normal((len(t), 2)) * np.exp(-t / decay * 3)[:, None], 120, bright)
    ir /= np.sqrt((ir ** 2).sum(axis=0, keepdims=True))
    x = stereo(x)
    n = x.shape[0] + ir.shape[0]
    nf = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nf, axis=0) * np.fft.rfft(ir, nf, axis=0), nf, axis=0)[: x.shape[0] + ir.shape[0]]


# ---------------- the sounds ----------------
def punch(c):
    """a fist landing: a leather/skin crack, a body thump and a short low kick, saturated, with a room."""
    t = tt(0.6)
    crack = bandpass(rng.standard_normal(len(t)), 1500, 13000) * np.exp(-t / 0.006)
    thump = np.sin(2 * np.pi * np.cumsum(70 + 90 * np.exp(-t / 0.02)) / SR) * np.exp(-t / 0.09)
    body = bandpass(rng.standard_normal(len(t)), 120, 1800) * np.exp(-t / 0.035)
    dry = np.tanh((crack * 1.6 + thump * 1.2 + body) * 1.8)
    return stereo(dry) + reverb(dry, 0.8, 0.25)[: len(t)] * 0.25


def cannon(c):
    """a cannon blast, sharp and close: an N-wave crack and bright burst, a wide punch, a low body and a short sub kick,
    saturated; bright slap echoes, debris and a short tail (a long dark rumble reads as slow motion)."""
    r = np.random.default_rng(c.get('seed', 13))
    n = int(2.0 * SR)
    t = np.arange(n) / SR
    crack = np.zeros(n)
    m = int(0.0012 * SR)
    crack[:m] = np.linspace(1, -1, m)
    crack += bandpass(r.standard_normal(n), 1500, 14000) * np.exp(-t / 0.005)
    pun = bandpass(r.standard_normal(n), 150, 6000) * np.exp(-t / 0.05) * np.minimum(1, t / 0.001) * 2.4
    body = bandpass(r.standard_normal(n), 60, 300) * np.exp(-t / 0.08) * 0.8
    sub = np.sin(2 * np.pi * np.cumsum(52 + 30 * np.exp(-t / 0.03)) / SR) * np.exp(-t / 0.2) * 0.8
    dry = bandpass(np.tanh((crack * 1.8 + pun + body + sub) * 1.6), 30, 15000)
    out = np.stack([dry, dry], 1)
    for dly, g, p, lo, hi in ((0.11, 0.35, -0.6, 200, 5000), (0.24, 0.2, 0.6, 300, 4000)):
        a = int(dly * SR)
        e = bandpass(dry[: n - a], lo, hi) * g
        out[a:, 0] += e * (1 - p)
        out[a:, 1] += e * (1 + p)
    env = (1 - np.exp(-t / 0.02)) * np.exp(-t / 0.45)
    out += np.stack([bandpass(r.standard_normal(n), 80, 2500) for _ in range(2)], 1) * env[:, None] * 0.3
    deb = np.zeros(n)
    for i in np.flatnonzero((r.random(n) < 260 / SR) & (t > 0.03) & (t < 0.6)):
        k = min(n - i, 150)
        deb[i:i + k] += r.standard_normal(k) * np.exp(-np.arange(k) / 18) * np.exp(-t[i] / 0.25)
    return out + np.stack([bandpass(deb, 2000, 12000)] * 2, 1) * 0.2


def charge(c):
    """an anime power charge: a whine sweeping 110 Hz -> 2.6 kHz, pulsing faster (6 -> 45 Hz), crackle getting denser, a
    swelling rumble; placed so it cuts to silence `gap` before `end` (the hit)."""
    r = np.random.default_rng(c.get('seed', 11))
    dur = c.get('dur', 1.0)
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = t / dur
    f = c.get('f0', 110) * (c.get('f1', 2600) / c.get('f0', 110)) ** (u ** 1.7)
    ph = 2 * np.pi * np.cumsum(f) / SR
    whine = (np.sin(ph) + 0.45 * np.sin(2 * ph + 0.3) + 0.2 * np.sin(3 * ph + 1.1)) * u ** 1.4
    whine *= 0.55 + 0.45 * np.sin(2 * np.pi * np.cumsum(6 + 39 * u ** 2) / SR)
    clicks = np.zeros(n)
    for i in np.flatnonzero(r.random(n) < (40 + 2200 * u ** 2.5) / SR):
        k = min(n - i, 90)
        clicks[i:i + k] += r.standard_normal(k) * np.exp(-np.arange(k) / 12) * (0.3 + u[i])
    crackle = bandpass(clicks, 1800, 12000) * 0.5 + bandpass(r.standard_normal(n), 2500, 9000) * u ** 3 * 0.25
    rum = bandpass(r.standard_normal(n), 25, 110) * u ** 2 * 1.4
    x = np.tanh((whine * 0.9 + crackle + rum) * 1.6) * np.minimum(1, t / 0.05)
    return stereo(x)


def whoosh(c):
    dur = c.get('dur', 0.45)
    n = int(dur * SR)
    t = np.arange(n) / SR
    f0, f1 = c.get('f0', 400), c.get('f1', 3000)
    x = stft_filter(rng.standard_normal(n), lambda tc: f0 * (f1 / f0) ** min(1, tc / dur), c.get('width', 0.7))
    return x * np.sin(np.pi * np.minimum(1, t / dur)) ** c.get('curve', 2.0)


def swish(c):
    """a fast limb swing (a punch or kick in the air): a short, bright whoosh."""
    return whoosh({'dur': c.get('dur', 0.16), 'f0': 900, 'f1': 5200, 'width': 0.5, 'curve': 1.2})


def ring(c):
    """time-freeze tinnitus (under an impact hold)."""
    dur, f = c.get('dur', 1.2), c.get('f', 3400)
    t = tt(dur)
    x = np.sin(2 * np.pi * f * t) + 0.6 * np.sin(2 * np.pi * f * 1.0071 * t) + 0.3 * np.sin(2 * np.pi * f * 1.5 * t)
    return x * np.minimum(1, t / 0.01) * np.exp(-t / (dur / 2.5)) * 0.25


def taiko(c):
    t = tt(1.4)
    f0 = c.get('f', 72)
    body = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.5 * np.exp(-t / 0.03))) / SR) * np.exp(-t / 0.45)
    skin = soft_band(rng.standard_normal(len(t)), 60, 700) * np.exp(-t / 0.05)
    return np.tanh((body + 0.7 * skin) * 1.3)


def crash(c):
    dur = c.get('dur', 2.4)
    t = tt(dur)
    x = soft_band(rng.standard_normal(len(t)), 2500, 15000) * np.exp(-t / (dur / 3.2))
    x += sum(np.sin(2 * np.pi * f * t + rng.random() * 6) for f in (3170, 4230, 5410, 6890)) * 0.05 * np.exp(-t / 0.9)
    x[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    return x


def sub_drop(c):
    dur = c.get('dur', 1.6)
    t = tt(dur)
    f = c.get('f1', 28) + (c.get('f0', 90) - c.get('f1', 28)) * np.exp(-t / 0.25)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (dur / 2.5)) * np.minimum(1, t / 0.005)


def debris(c):
    dur = c.get('dur', 1.4)
    n = int(dur * SR)
    x = np.zeros(n)
    for p in (rng.random(int(260 * dur)) ** 1.8 * n).astype(int):
        m = int(rng.uniform(0.002, 0.012) * SR)
        if p + m < n:
            x[p:p + m] += rng.standard_normal(m) * np.exp(-np.arange(m) / (m / 4)) * rng.uniform(0.2, 1)
    return soft_band(x, 900, 9000) * np.exp(-np.arange(n) / SR / (dur / 2.2))


def rumble(c):
    dur = c.get('dur', 1.2)
    t = tt(dur)
    return soft_band(rng.standard_normal(len(t)), 25, 160) * np.exp(-t / (dur / 3)) * 3


def vwoom(c):
    """slow-motion drop: a falling tone and air."""
    dur = c.get('dur', 0.9)
    t = tt(dur)
    tone = np.sin(2 * np.pi * np.cumsum(60 + 260 * np.exp(-t / 0.18)) / SR) * np.exp(-t / (dur / 2))
    air = stft_filter(rng.standard_normal(len(t)), lambda tc: 3000 * np.exp(-tc / 0.2) + 200, 0.6) * np.exp(-t / 0.3)
    return tone + 0.6 * air


def reverse_swell(c):
    """a reversed cymbal swelling into `end`."""
    dur = c.get('dur', 1.0)
    x = reverb(crash({'dur': dur}), 1.6, 0.7)[: int(dur * SR), 0][::-1]
    return x / (np.abs(x).max() + 1e-9)


def riser(c):
    """noise + tone rising into `end` (tension before a cut)."""
    dur = c.get('dur', 1.5)
    t = tt(dur)
    u = t / dur
    nz = stft_filter(rng.standard_normal(len(t)), lambda tc: 300 * (8000 / 300) ** min(1, tc / dur), 0.5)
    tone = np.sin(2 * np.pi * np.cumsum(120 * (900 / 120) ** u) / SR) * 0.4
    return (nz + tone) * u ** 2


def sparkle(c):
    """'kira': a bell arpeggio up high."""
    out = np.zeros(int(1.6 * SR))
    for i, f in enumerate((1318.5, 1975.5, 2637.0, 3322.4)):
        t = tt(1.2)
        b = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t / (0.5 / r)) for r, a in ((1, 1), (2.76, 0.4), (5.4, 0.2)))
        a0 = int(i * 0.045 * SR)
        out[a0:a0 + len(t)] += b[: len(out) - a0] * (0.8 ** i)
    return out * 0.3


def heartbeat(c):
    t = tt(0.6)
    lub = np.sin(2 * np.pi * 52 * t) * np.exp(-t / 0.06)
    t2 = np.maximum(0, t - 0.24)
    dub = np.sin(2 * np.pi * 44 * t2) * np.exp(-t2 / 0.05) * (t > 0.24) * 0.75
    return soft_band(np.tanh((lub + dub) * 2), 20, 300)


def footstep(c):
    t = tt(0.25)
    return np.sin(2 * np.pi * 85 * t) * np.exp(-t / 0.05) + 0.6 * soft_band(rng.standard_normal(len(t)), 400, 4000) * np.exp(-t / 0.018)


def stamp(c):
    """a title stamp: taiko + a short crash + a slap (the opening page's kanji, one per beat)."""
    a, b = taiko({'f': c.get('f', 80)}), crash({'dur': 0.9}) * 0.35
    n = max(len(a), len(b))
    x = np.zeros(n)
    x[: len(a)] += a
    x[: len(b)] += b
    t = tt(0.05)
    x[: len(t)] += bandpass(rng.standard_normal(len(t)), 1500, 12000) * np.exp(-t / 0.004) * 0.8
    return x


SOUNDS = {k: v for k, v in globals().items() if k in ('punch', 'cannon', 'charge', 'whoosh', 'swish', 'ring', 'taiko', 'crash', 'sub_drop', 'debris',
                                                    'rumble', 'vwoom', 'reverse_swell', 'riser', 'sparkle', 'heartbeat', 'footstep', 'stamp')}
ENDING = ('charge', 'reverse_swell', 'riser')   # placed by "end" (they lead into a moment)


def main(path):
    plan_path = Path(path).resolve()
    plan = json.loads(plan_path.read_text())
    proj = Project(plan_path.parent)
    dur = proj.t(plan.get('duration', proj.total)) + 0.5
    out = np.zeros((int(dur * SR), 2))
    for c in plan.get('cues', []):
        kind = c['type']
        if kind == 'file':
            sig = load(proj.path(c['path']))
        elif kind in SOUNDS:
            sig = SOUNDS[kind](c)
        else:
            raise SystemExit(f"unknown cue type {kind} (types: {', '.join(sorted(SOUNDS))}, file)")
        sig = stereo(np.asarray(sig, dtype=np.float64), c.get('pan', 0.0))
        times = c.get('at', c.get('end'))
        for at in times if isinstance(times, list) else [times]:
            t = proj.t(at)
            if kind in ENDING and 'end' in c:
                t -= sig.shape[0] / SR + c.get('gap', 0.05 if kind == 'charge' else 0.0)
            place(out, sig, t, c.get('gain', 1.0))
    if plan.get('duck'):
        pts = [(0, 0)]
        for d in plan['duck']:
            a, b = proj.t(d['from']), proj.t(d['to'])
            pts += [(a - 0.005, 0), (a, d.get('db', -10)), (b, d.get('db', -10)), (b + d.get('release', 0.3), 0)]
        out *= envelope(out.shape[0], sorted(pts), 0.005)[:, None]
    write(out[: int((dur - 0.5) * SR)], proj.path(plan.get('out', 'sfx/sfx.wav')), plan.get('peak', 0.9))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])
