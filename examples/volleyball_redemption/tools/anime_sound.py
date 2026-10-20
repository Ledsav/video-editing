#!/usr/bin/env python3
"""Anime score + sound design for story_full.json, synthesised with numpy and locked to the picture.

Writes three stems (48 kHz stereo, edit time 0 = sample 0):
  music/anime_score.wav   the cue: lonely piano (past) -> ostinato build -> anime rock drop -> silence
                          before the hit -> full chorus -> piano callback -> final chord
  sfx/anime_sfx.wav       one sound per action, no repeats: steps, squeaks, takeoff, whip, contact,
                          time-freeze ring, ball pass, BAM, debris, roll, sparkle, heartbeat
  sfx/anime_crowd.wav     arena crowd: muffled in the past, alive today, erupting on 26:24

usage: python3 tools/anime_sound.py            (from the project folder)
"""
from pathlib import Path
import numpy as np

SR = 48000
DUR = 26.1 + 0.4
N = int(DUR * SR)
rng = np.random.default_rng(11)

# ---------------- picture events (edit seconds), from STORY_TIMES / SPIKE_TIMES ----------------
LAND_PAST = 2.218            # last year's spike hits the floor (inverted hold 0.2 s)
SCORE_PAST = 3.30            # 24 : 26
LINE_PAST = 4.55             # "He never forgot that point."
FLASH = 5.42                 # white flash into colour
EYES = 5.50
MATCH_POINT = 5.95
SET = 6.95                   # setter's touch
ATTACK = 7.05                # "THIS TIME, HE ATTACKS." -> the drop
SPIKE = 8.2
STEPS = [8.36, 8.735, 9.42]  # run-up footfalls (mocap plants)
TAKEOFF = 10.023             # liftoff (hold 0.13)
RISE = 10.4
RAGE = 11.05                 # the rage close-up (red, the scream): the music drops out here
COMIC = RAGE                 # (the silence runs from the rage cut to the contact)
COMIC_CUT = 11.85            # cut into the comic frame: the drawn bow
CONTACT = 12.30              # hit: a gunshot; the impact frame holds 1 s, switching look every 0.25 s
HIT_HOLD = 1.0
REENTRY = CONTACT + HIT_HOLD
SMASH = 13.75                # ball flight shot
FLOOR = 14.20                # BAM
ROAR = 15.3
SCORE = 15.55                # 26 : 24
OUTRO = 18.5                 # grey: last year's ball rolls to a stop
MATCH_CUT = 20.5             # today's ball, colour
CARD = 22.7
TITLE = 23.05                # NEVER GIVE UP.
END = 26.1

BEAT = (CONTACT - ATTACK) / 12          # 141.7 bpm: the contact lands on a downbeat, 3 bars after the drop
BAR = 4 * BEAT


# ---------------- dsp helpers ----------------
def secs(d):
    return np.arange(int(d * SR)) / SR


def fft_filter(x, lo=0.0, hi=SR / 2, slope=1.0):
    """zero-phase band filter with soft (Gaussian-ish) edges, works on mono or (n, 2)."""
    n = x.shape[0]
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if lo > 0:
        g *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** (4 * slope))
    if hi < SR / 2:
        g *= 1 / (1 + (f / hi) ** (4 * slope))
    if x.ndim == 2:
        g = g[:, None]
    return np.fft.irfft(X * g, n=n, axis=0)


def stft_filter(x, center_fn, width_oct=0.6):
    """time-varying band-pass: center_fn(t) -> Hz (vectorised over frame times)."""
    w, hop = 2048, 512
    win = np.hanning(w)
    pad = np.concatenate([np.zeros(w), x, np.zeros(w)])
    frames = 1 + (len(pad) - w) // hop
    out = np.zeros(len(pad))
    norm = np.zeros(len(pad))
    f = np.fft.rfftfreq(w, 1 / SR)
    lf = np.log2(np.maximum(f, 1))
    for i in range(frames):
        a = i * hop
        seg = pad[a:a + w] * win
        tc = (a - w + w / 2) / SR
        c = np.log2(max(center_fn(max(tc, 0)), 20))
        mask = np.exp(-0.5 * ((lf - c) / width_oct) ** 2)
        out[a:a + w] += np.fft.irfft(np.fft.rfft(seg) * mask, n=w) * win
        norm[a:a + w] += win ** 2
    return (out / np.maximum(norm, 1e-6))[w:w + len(x)]


def env_exp(n, attack, decay):
    t = np.arange(n) / SR
    a = np.minimum(1, t / max(attack, 1e-4))
    return a * np.exp(-t / max(decay, 1e-4))


def pan2(x, p=0.0):
    """mono -> stereo, equal power, p in [-1, 1]."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def make_ir(length=2.4, decay=0.9, bright=6000, seed=3):
    r = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    ir = r.standard_normal((n, 2)) * np.exp(-t / decay * 3)[:, None]
    ir = fft_filter(ir, 120, bright)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]
    return ir / np.sqrt((ir ** 2).sum(axis=0, keepdims=True))


def convolve(x, ir):
    n = x.shape[0] + ir.shape[0]
    nf = 1 << (n - 1).bit_length()
    X = np.fft.rfft(x, nf, axis=0)
    H = np.fft.rfft(ir, nf, axis=0)
    return np.fft.irfft(X * H, nf, axis=0)[: x.shape[0]]


HALL = make_ir(2.6, 1.0, 7000, 3)
ROOM = make_ir(1.1, 0.45, 9000, 5)


def compress(x, thr_db=-20.0, ratio=4.0, att=0.004, rel=0.18, knee=6.0):
    """feed-forward bus compressor on 5 ms blocks (peak detector, attack/release smoothing)."""
    blk = 240
    nb = int(np.ceil(x.shape[0] / blk))
    pad = np.zeros((nb * blk, x.shape[1]))
    pad[: x.shape[0]] = x
    pk = np.abs(pad).reshape(nb, blk, -1).max(axis=(1, 2))
    lvl = 20 * np.log10(pk + 1e-9)
    over = lvl - thr_db
    gr = np.where(over <= -knee / 2, 0.0, np.where(over >= knee / 2, over * (1 - 1 / ratio),
                  (1 - 1 / ratio) * (over + knee / 2) ** 2 / (2 * knee)))
    a_c, r_c = np.exp(-blk / SR / att), np.exp(-blk / SR / rel)
    sm = np.zeros(nb)
    g = 0.0
    for i in range(nb):
        c = a_c if gr[i] > g else r_c
        g = c * g + (1 - c) * gr[i]
        sm[i] = g
    gain = 10 ** (-np.repeat(sm, blk)[: x.shape[0]] / 20)
    return x * gain[:, None]


class Bus:
    def __init__(self):
        self.x = np.zeros((N, 2))

    def add(self, sig, t, gain=1.0, p=0.0):
        if sig.ndim == 1:
            sig = pan2(sig, p)
        a = int(round(t * SR))
        if a >= N:
            return
        if a < 0:
            sig, a = sig[-a:], 0
        b = min(N, a + sig.shape[0])
        self.x[a:b] += sig[: b - a] * gain


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


NOTE = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
        'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}


def hz(name):
    """'D5' -> Hz"""
    p, o = name[:-1], int(name[-1])
    return midi(12 * (o + 1) + NOTE[p])


# ---------------- instruments ----------------
def piano(f, dur, vel=1.0):
    n = int((dur + 2.5) * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    B = 0.00035
    for k in range(1, 10):
        fk = f * k * np.sqrt(1 + B * k * k)
        if fk > 16000:
            break
        x += (1 / k ** 1.15) * np.exp(-t * (0.9 + 0.55 * k) * (1 + (f > 600))) * np.sin(2 * np.pi * fk * t + k)
    rel = np.ones(n)
    r0 = int(dur * SR)
    rel[r0:] = np.exp(-np.arange(n - r0) / SR / 0.25)
    x *= rel * np.minimum(1, t / 0.003)
    ham = fft_filter(rng.standard_normal(int(0.02 * SR)) * np.exp(-np.arange(int(0.02 * SR)) / SR / 0.004), 800, 6000)
    x[: len(ham)] += 0.15 * ham
    return x * vel * 0.35


def saw(f, n, phase=0.0):
    t = np.arange(n) / SR
    return 2 * np.mod(f * t + phase, 1.0) - 1


def supersaw(f, dur, voices=5, cents=12, lo=0, hi=5000, attack=0.02, release=0.3, vib=0.0):
    n = int((dur + release) * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for v in range(voices):
        d = (v - (voices - 1) / 2) / max(1, (voices - 1) / 2) * cents
        ff = f * 2 ** (d / 1200)
        if vib:
            ph = np.cumsum(ff * (1 + vib * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.4))) / SR
            x += 2 * np.mod(ph + rng.random(), 1.0) - 1
        else:
            x += saw(ff, n, rng.random())
    x /= voices
    e = np.minimum(1, t / attack)
    r0 = int(dur * SR)
    e[r0:] *= np.exp(-np.arange(n - r0) / SR / (release / 4))
    return fft_filter(x * e, lo, hi)


def strings(chord, dur, gain=1.0, hi=3500, attack=0.25):
    x = sum(supersaw(hz(c), dur, 6, 14, 90, hi, attack, 0.6, vib=0.003) for c in chord)
    return x * gain / len(chord)


def choir(chord, dur, gain=1.0, attack=0.4):
    raw = sum(supersaw(hz(c), dur, 5, 18, 0, 12000, attack, 0.8, vib=0.004) for c in chord) / len(chord)
    x = 0.0
    for fc, bw, g in ((720, 1.25, 1.0), (1150, 1.3, 0.6), (2600, 1.2, 0.25)):     # "aah" formants
        x = x + g * fft_filter(raw, fc / bw, fc * bw, 1.5)
    return x * gain


def brass(chord, dur, gain=1.0):
    out = 0.0
    for c in chord:
        f = hz(c)
        n = int((dur + 0.3) * SR)
        t = np.arange(n) / SR
        x = supersaw(f, dur, 3, 8, 0, 14000, 0.015, 0.3)
        # filter envelope: bright attack, settles
        bright = fft_filter(x, 0, 5000) * np.exp(-t / 0.25)[: len(x)] + fft_filter(x, 0, 1500) * 0.7
        out = out + bright
    return np.tanh(out * 1.6 / len(chord)) * gain


def lead(notes, gain=1.0):
    """notes: list of (name, start_beat, beats) -> mono signal starting at 0, bright synth-brass lead."""
    total = max(s + d for _, s, d in notes) * BEAT + 1.0
    x = np.zeros(int(total * SR))
    for name, s, d in notes:
        sig = supersaw(hz(name), d * BEAT * 0.95, 3, 7, 0, 7000, 0.01, 0.25, vib=0.006)
        sig = np.tanh(sig * 1.4)
        a = int(s * BEAT * SR)
        x[a:a + len(sig)] += sig[: len(x) - a]
    return x * gain


def bass_line(roots, start_bar_beats, gain=1.0):
    """eighth-note driving bass. roots: list of note names per bar."""
    total = len(roots) * 4 * BEAT + 0.5
    x = np.zeros(int(total * SR))
    for b, r in enumerate(roots):
        f = hz(r)
        for e in range(8):
            n = int(BEAT / 2 * 0.92 * SR)
            t = np.arange(n) / SR
            s = 0.6 * np.sin(2 * np.pi * f * t) + 0.5 * fft_filter(saw(f, n), 0, 900)
            s *= np.minimum(1, t / 0.004) * np.exp(-t / 0.25)
            a = int((b * 4 + e * 0.5) * BEAT * SR)
            x[a:a + n] += s[: len(x) - a]
    return x * gain


def power_chords(roots, mode='chug', gain=1.0):
    """distorted guitar: root + fifth + octave. chug = palm-muted 8ths, ring = sustained, trem = 16ths."""
    total = len(roots) * 4 * BEAT + 1.0
    x = np.zeros(int(total * SR))
    for b, r in enumerate(roots):
        f = hz(r)
        hits = {'chug': [(e * 0.5, 0.45, 0.07) for e in range(8)], 'ring': [(0, 4, 1.2)],
                'trem': [(e * 0.25, 0.24, 0.12) for e in range(16)]}[mode]
        for s, d, dec in hits:
            n = int(d * BEAT * SR)
            t = np.arange(n) / SR
            raw = saw(f, n) + saw(f * 1.4983, n, 0.3) + 0.6 * saw(f * 2, n, 0.6) + 0.4 * saw(f * 1.006, n, 0.1)
            sig = np.tanh(raw * 5) * np.minimum(1, t / 0.003) * np.exp(-t / dec)
            a = int((b * 4 + s) * BEAT * SR)
            x[a:a + n] += sig[: len(x) - a]
    x = fft_filter(x, 90, 4200)
    return x * gain


def kick(g=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t / 0.035)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22)
    x[: int(0.003 * SR)] += rng.standard_normal(int(0.003 * SR)) * 0.5
    return np.tanh(x * 1.5) * g


def snare(g=1.0):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    nz = fft_filter(rng.standard_normal(n), 1200, 9000) * np.exp(-t / 0.11)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.06)
    return (nz * 0.9 + tone * 0.6) * g


def hat(g=1.0, open_=False):
    n = int((0.35 if open_ else 0.08) * SR)
    t = np.arange(n) / SR
    return fft_filter(rng.standard_normal(n), 7000, 16000) * np.exp(-t / (0.12 if open_ else 0.025)) * g


def crash(g=1.0, length=2.4):
    n = int(length * SR)
    t = np.arange(n) / SR
    nz = fft_filter(rng.standard_normal(n), 2500, 15000) * np.exp(-t / (length / 3.2))
    shim = sum(np.sin(2 * np.pi * f * t + rng.random() * 6) for f in (3170, 4230, 5410, 6890)) * 0.05 * np.exp(-t / 0.9)
    x = nz + shim
    x[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    return x * g


def taiko(g=1.0, f0=72):
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    f = f0 * (1 + 0.5 * np.exp(-t / 0.03))
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.45)
    skin = fft_filter(rng.standard_normal(n), 60, 700) * np.exp(-t / 0.05)
    return np.tanh((body + 0.7 * skin) * 1.3) * g


def tom(f0=110, g=1.0):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    f = f0 * (1 + 0.6 * np.exp(-t / 0.04))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22) * g


def timpani(f0, g=1.0, length=1.6):
    n = int(length * SR)
    t = np.arange(n) / SR
    x = sum(a * np.sin(2 * np.pi * f0 * r * t) * np.exp(-t / (0.9 / r)) for r, a in ((1, 1), (1.5, 0.5), (1.99, 0.35), (2.44, 0.2)))
    x += fft_filter(rng.standard_normal(n), 50, 900) * np.exp(-t / 0.03) * 0.6
    return x * g


def orch_hit(chord, g=1.0):
    """the anime stab: brass + strings + choir + timpani + crash, very short attack."""
    b = brass(chord, 0.45, 1.0)
    s = strings(chord, 0.5, 0.8, 6000, 0.005)
    c = choir(chord, 0.6, 0.5, 0.01)
    L = max(len(b), len(s), len(c))
    mix = np.zeros(L)
    for y in (b, s, c):
        mix[: len(y)] += y
    tp = timpani(hz(chord[0][:-1] + '2'), 0.9)
    mix2 = np.zeros(max(L, len(tp)))
    mix2[:L] += mix
    mix2[: len(tp)] += tp
    return mix2 * g


# ---------------- sound effects ----------------
def whoosh(dur, f0, f1, g=1.0, width=0.7, curve=2.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    nz = rng.standard_normal(n)
    x = stft_filter(nz, lambda tc: f0 * (f1 / f0) ** min(1, (tc / dur)), width)
    e = np.sin(np.pi * np.minimum(1, t / dur)) ** curve
    return x * e * g


def ball_pass(dur=0.55, g=1.0):
    """doppler: rising hiss + hum into the pass, falling after."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    mid = dur * 0.45
    fc = lambda tc: 900 + 2600 * np.exp(-((tc - mid) / 0.09) ** 2)
    x = stft_filter(rng.standard_normal(n), fc, 0.5)
    hum_f = 220 * np.where(t < mid, 1.15, 0.85)
    hum = np.sin(2 * np.pi * np.cumsum(hum_f) / SR) * 0.3
    e = np.exp(-((t - mid) / (dur * 0.28)) ** 2)
    return (x + hum) * e * g


def squeak(f0=2300, dur=0.09, g=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (1 + 0.25 * t / dur) * (1 + 0.02 * np.sin(2 * np.pi * 45 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)) * np.sin(np.pi * t / dur) ** 0.6
    return x * g * 0.5


def footstep(g=1.0):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    thud = np.sin(2 * np.pi * 85 * t) * np.exp(-t / 0.05)
    slap = fft_filter(rng.standard_normal(n), 400, 4000) * np.exp(-t / 0.018)
    return (thud + 0.6 * slap) * g


def smack(g=1.0):
    """palm on leather."""
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    crack = fft_filter(rng.standard_normal(n), 1500, 14000) * np.exp(-t / 0.006)
    body = np.sin(2 * np.pi * 380 * t) * np.exp(-t / 0.05) + 0.7 * np.sin(2 * np.pi * 95 * t) * np.exp(-t / 0.09)
    return np.tanh((crack * 1.4 + body) * 1.8) * g


def gunshot(g=1.0):
    """the hit as a gunshot: supersonic crack (N-wave), muzzle boom, sub punch, then a stereo slap-back off the arena walls."""
    n = int(2.6 * SR)
    t = np.arange(n) / SR
    crack = np.zeros(n)
    m = int(0.0016 * SR)
    crack[:m] = np.linspace(1, -1, m)                                              # N-wave
    crack = fft_filter(crack + rng.standard_normal(n) * np.exp(-t / 0.0025) * 0.6, 1200, 18000)
    boom = fft_filter(rng.standard_normal(n), 40, 1400) * np.exp(-t / 0.07) * 1.6
    sub = np.sin(2 * np.pi * np.cumsum(48 + 70 * np.exp(-t / 0.03)) / SR) * np.exp(-t / 0.3) * 1.2
    dry = np.tanh((crack * 3 + boom + sub) * 1.5)
    out = pan2(dry, 0.0)
    for dly, gl, pn in ((0.115, 0.35, -0.7), (0.26, 0.22, 0.7), (0.43, 0.12, -0.4), (0.62, 0.07, 0.5)):   # slap-back echoes
        a = int(dly * SR)
        echo = fft_filter(dry[: n - a], 150, 3500) * gl
        out[a:] += pan2(echo, pn)
    tail = convolve(out * 0.5, HALL)
    return (out + 0.6 * tail) * g


def sub_drop(f0=90, f1=28, length=1.6, g=1.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.25)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (length / 2.5)) * np.minimum(1, t / 0.005) * g


def debris(length=1.4, g=1.0, density=260):
    n = int(length * SR)
    x = np.zeros(n)
    k = int(density * length)
    pos = (rng.random(k) ** 1.8 * n).astype(int)
    for p in pos:
        m = int(rng.uniform(0.002, 0.012) * SR)
        if p + m < n:
            x[p:p + m] += rng.standard_normal(m) * np.exp(-np.arange(m) / (m / 4)) * rng.uniform(0.2, 1)
    t = np.arange(n) / SR
    return fft_filter(x, 900, 9000) * np.exp(-t / (length / 2.2)) * g


def rumble(length=1.2, g=1.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    return fft_filter(rng.standard_normal(n), 25, 160) * np.exp(-t / (length / 3)) * 3 * g


def ring(length=1.3, g=1.0, f=3400):
    """time-freeze tinnitus."""
    n = int(length * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * f * t) + 0.6 * np.sin(2 * np.pi * f * 1.0071 * t) + 0.3 * np.sin(2 * np.pi * f * 1.5 * t)
    return x * np.minimum(1, t / 0.01) * np.exp(-t / (length / 2.5)) * g * 0.25


def vwoom(length=0.9, g=1.0):
    """slow-motion drop: falling tone + air."""
    n = int(length * SR)
    t = np.arange(n) / SR
    f = 60 + 260 * np.exp(-t / 0.18)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (length / 2))
    air = stft_filter(rng.standard_normal(n), lambda tc: 3000 * np.exp(-tc / 0.2) + 200, 0.6) * np.exp(-t / 0.3)
    return (tone + 0.6 * air) * g


def reverse_swell(length=1.0, g=1.0):
    c = crash(1.0, length)
    c = convolve(pan2(c), HALL)[:, 0]
    x = c[::-1]
    return x / (np.abs(x).max() + 1e-9) * g


def sparkle(g=1.0):
    """anime 'kira': bell arpeggio up high."""
    out = np.zeros(int(1.6 * SR))
    for i, name in enumerate(['E6', 'B6', 'E7', 'G#7']):
        f = hz(name)
        n = int(1.2 * SR)
        t = np.arange(n) / SR
        b = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t / (0.5 / r)) for r, a in ((1, 1), (2.76, 0.4), (5.4, 0.2)))
        a0 = int(i * 0.045 * SR)
        out[a0:a0 + n] += b[: len(out) - a0] * (0.8 ** i)
    return out * g * 0.3


def heartbeat(g=1.0):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    lub = np.sin(2 * np.pi * 52 * t) * np.exp(-t / 0.06)
    t2 = np.maximum(0, t - 0.24)
    dub = np.sin(2 * np.pi * 44 * t2) * np.exp(-t2 / 0.05) * (t > 0.24) * 0.75
    return fft_filter(np.tanh((lub + dub) * 2), 20, 300) * g


def roll(length=1.7, g=1.0):
    """last year's ball rolling to a stop: low rumble pulsing with the rotation, slowing down."""
    n = int(length * SR)
    t = np.arange(n) / SR
    k = 1 - (1 - np.minimum(1, t / (length * 0.95))) ** 3          # matches the picture's ease-out
    speed = np.gradient(k) * SR
    rot = np.cumsum(speed / (2 * np.pi * 0.12)) / SR                # revolutions
    puls = 0.6 + 0.4 * np.sin(2 * np.pi * rot * 2) ** 2
    x = fft_filter(rng.standard_normal(n), 60, 900) * puls * np.clip(speed / speed.max(), 0, 1) ** 0.7
    return x * g * 1.6


def bounce(g=1.0, f=140):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.04) + fft_filter(rng.standard_normal(n), 600, 5000) * np.exp(-t / 0.01)) * g


# ---------------- crowd ----------------
def crowd(level_fn, cheer_fn, length=DUR, voices=36):
    """babble: many band-limited voices with syllabic amplitude; cheer adds brightness, whistles and claps."""
    n = int(length * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    lv = level_fn(t)
    ch = cheer_fn(t)
    for v in range(voices):
        fc = rng.uniform(280, 1600)
        nz = fft_filter(rng.standard_normal(n), fc / 1.6, fc * 1.6)
        rate = rng.uniform(2.5, 6.0)
        m = fft_filter(rng.standard_normal(n), 0, rate)
        m = np.maximum(0, m / (np.abs(m).max() + 1e-9) + 0.25)
        out += pan2(nz * m, rng.uniform(-0.9, 0.9))
    out /= np.sqrt(voices)
    bright = fft_filter(out, 900, 6000)
    out = out * lv[:, None] + bright * (ch * 1.4)[:, None]
    # roar: broadband swell in the cheer
    roar = fft_filter(rng.standard_normal((n, 2)), 300, 4000)
    out += roar * (ch * 0.45)[:, None]
    # whistles and claps on the cheer
    for _ in range(40):
        s = rng.uniform(0, length)
        if cheer_fn(np.array([s]))[0] < 0.3:
            continue
        d = rng.uniform(0.3, 0.9)
        m = int(d * SR)
        tt = np.arange(m) / SR
        f = rng.uniform(1800, 3200) * (1 + 0.15 * np.sin(np.pi * tt / d))
        w = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / d) * 0.12
        a = int(s * SR)
        out[a:a + m] += pan2(w, rng.uniform(-0.8, 0.8))[: n - a] * cheer_fn(np.array([s]))[0]
    for _ in range(700):
        s = rng.uniform(0, length)
        c = cheer_fn(np.array([s]))[0]
        if c < 0.2:
            continue
        m = int(0.02 * SR)
        a = int(s * SR)
        clap = fft_filter(rng.standard_normal(m), 800, 7000) * np.exp(-np.arange(m) / (0.004 * SR)) * 0.25 * c
        out[a:a + m] += pan2(clap, rng.uniform(-1, 1))[: n - a]
    return out


def smooth_steps(t, pts):
    """piecewise-linear curve through (time, value) points."""
    xs, ys = zip(*pts)
    return np.interp(t, xs, ys)


# ---------------- the score ----------------
def compose():
    past = Bus()        # muffled later
    music = Bus()
    tension = Bus()     # plays through the comic-frame silence
    sfx = Bus()

    # --- I. the past: lonely piano in D minor, cold string drone, heartbeat ---
    motif = [('A4', 0.55, 0.9), ('D5', 1.35, 0.6), ('C5', 1.95, 0.6), ('A4', 2.55, 1.2), ('F4', 3.75, 0.6),
             ('G4', 4.35, 0.5), ('A4', 4.85, 1.4)]
    for nm, t0, d in motif:
        past.add(piano(hz(nm), d, 0.9), t0, 1.0, -0.15)
    for nm, t0, d in (('D3', 0.55, 1.6), ('A3', 2.55, 1.2), ('Bb2', 3.75, 1.6)):
        past.add(piano(hz(nm), d, 0.6), t0, 0.8, -0.3)
    past.add(strings(['D3', 'A3', 'F4'], 4.6, 0.35, 1800, 1.2), 0.8, 1.0)
    for i, t0 in enumerate(np.arange(3.05, 5.3, 0.92)):                     # heartbeat, slowing
        sfx.add(heartbeat(0.9), t0 + 0.04 * i, 0.45)

    # last year's spike: the ball dives in, hits, time stops
    sfx.add(whoosh(0.32, 900, 3500, 0.6), LAND_PAST - 0.3, 0.8, 0.4)
    sfx.add(fft_filter(smack(1.0), 0, 2500), LAND_PAST, 0.9)
    sfx.add(sub_drop(70, 30, 1.0, 0.8), LAND_PAST, 1.0)
    sfx.add(ring(1.6, 1.0, 2900), LAND_PAST, 0.9)
    sfx.add(bounce(0.5, 120), 2.62, 0.6, 0.3)
    sfx.add(bounce(0.35, 120), 3.12, 0.5, 0.5)
    sfx.add(squeak(1900, 0.11, 0.6), 1.85, 0.5, -0.2)               # his late lunge
    sfx.add(footstep(0.9), 3.06, 0.9)                               # knee on the floor
    sfx.add(taiko(1.0, 55), SCORE_PAST, 0.5)                        # 24 : 26
    past.add(strings(['Bb2', 'F3', 'D4'], 2.0, 0.5, 1500, 0.6), SCORE_PAST, 1.0)

    # --- II. the flash: reverse swell -> hit -> colour ---
    music.add(reverse_swell(1.1, 0.8), FLASH - 1.1, 1.0)
    music.add(orch_hit(['D3', 'A3', 'D4', 'F4']), FLASH, 1.0)
    music.add(crash(0.7, 2.5), FLASH, 1.0)
    sfx.add(sub_drop(110, 30, 1.6, 1.0), FLASH, 0.9)
    sfx.add(sparkle(1.0), EYES + 0.1, 0.9, 0.3)

    # tension build to the drop: 16th string ostinato, timpani pulses, choir rising, snare roll
    t = FLASH + 0.08
    ost_notes = ['D4', 'D4', 'A4', 'D4', 'F4', 'D4', 'A4', 'D4']
    k = 0
    while t < ATTACK - 0.02:
        nm = ost_notes[k % 8]
        g = 0.25 + 0.6 * (t - FLASH) / (ATTACK - FLASH)
        music.add(supersaw(hz(nm), BEAT / 4 * 0.8, 4, 10, 200, 5000, 0.004, 0.05), t, g * 0.5, 0.2)
        t += BEAT / 4
        k += 1
    for b in np.arange(FLASH + BEAT, ATTACK, BEAT):
        music.add(timpani(hz('D2'), 0.7, 1.0), b, 0.8)
    music.add(choir(['D4', 'A4', 'D5'], ATTACK - FLASH, 0.5, 1.2), FLASH, 1.0)
    music.add(brass(['D3', 'A3', 'D4'], 0.35, 0.9), MATCH_POINT, 1.0)
    music.add(taiko(1.0, 70), MATCH_POINT, 1.0)
    roll_t = np.arange(ATTACK - 0.85, ATTACK - 0.01, BEAT / 4)
    for i, rt in enumerate(roll_t):
        music.add(snare(0.25 + 0.75 * i / len(roll_t)), rt, 0.6)
    sfx.add(fft_filter(smack(0.5), 0, 4000), SET, 0.6, 0.4)                 # setter's touch
    sfx.add(whoosh(0.7, 500, 2600, 0.5), SET, 0.6, 0.3)

    # --- III. the drop: anime rock (Dm Bb F C) from ATTACK to the comic cut ---
    verse_roots = ['D2', 'Bb1', 'F2', 'C2']
    bars_v = int(np.ceil((COMIC - ATTACK) / BAR)) + 1
    roots = [verse_roots[i % 4] for i in range(bars_v)]
    drums_until = COMIC

    def drums(t0, t1, fill_at=None, half=False):
        b = 0
        while True:
            tb = t0 + b * BEAT
            if tb >= t1 - 1e-6:
                break
            beat_in_bar = b % 4
            if fill_at is not None and tb >= fill_at:
                # tom + snare 16th fill into the cut
                for s in range(4):
                    ts = tb + s * BEAT / 4
                    if ts < t1:
                        music.add(tom(150 - 10 * ((b * 4 + s) % 6), 0.8), ts, 0.7, -0.4 + 0.2 * s)
                        music.add(snare(0.5), ts, 0.4)
            else:
                if beat_in_bar in (0, 2) or (not half and beat_in_bar == 3 and b % 8 == 7):
                    music.add(kick(1.0), tb, 1.4)
                if beat_in_bar in (1, 3):
                    music.add(snare(1.0), tb, 1.15)
                for e in range(2):
                    th = tb + e * BEAT / 2
                    if th < t1:
                        music.add(hat(0.7 if e == 0 else 0.45), th, 0.35, 0.3)
                if beat_in_bar == 1 and b % 2:
                    music.add(kick(0.7), tb + BEAT / 2, 0.8)
            b += 1

    music.add(crash(1.0, 2.6), ATTACK, 0.9)
    music.add(kick(1.2), ATTACK, 1.0)
    music.add(sub_drop(80, 35, 1.0, 0.8), ATTACK, 0.8)
    drums(ATTACK, drums_until, fill_at=RISE + 2 * BEAT)  # levels set in drums()
    bl = bass_line(roots, 0, 0.8)
    music.add(bl[: int((COMIC - ATTACK) * SR)], ATTACK, 1.4)
    pc = power_chords(roots, 'chug', 0.5)
    music.add(pc[: int((COMIC - ATTACK) * SR)], ATTACK, 1.3, -0.35)
    pc2 = power_chords(roots, 'chug', 0.5)
    music.add(pc2[: int((COMIC - ATTACK) * SR)], ATTACK + 0.012, 1.3, 0.35)
    chords_v = [['D4', 'F4', 'A4'], ['Bb3', 'D4', 'F4'], ['C4', 'F4', 'A4'], ['C4', 'E4', 'G4']]
    for i in range(bars_v):
        ts = ATTACK + i * BAR
        if ts < COMIC:
            d = min(BAR, COMIC - ts)
            music.add(strings(chords_v[i % 4], d, 0.35, 4000, 0.08), ts, 1.5)
    hook = [('D5', 0, 1), ('E5', 1, 0.5), ('F5', 1.5, 0.5), ('A5', 2, 1.5), ('G5', 3.5, 0.5),
            ('F5', 4, 1), ('E5', 5, 1), ('D5', 6, 2),
            ('C5', 8, 1), ('D5', 9, 0.5), ('E5', 9.5, 0.5), ('F5', 10, 1), ('A5', 11, 1),
            ('G5', 12, 3), ('E5', 15, 1)]
    ld = lead(hook, 0.75)
    music.add(ld[: int((COMIC - ATTACK) * SR)], ATTACK, 1.0, 0.1)

    # run-up: steps + sneaker squeaks; the plant into takeoff
    for i, ts in enumerate(STEPS):
        sfx.add(footstep(0.8 + 0.1 * i), ts, 0.9, -0.1)
        sfx.add(squeak(2100 + 250 * i, 0.07 + 0.02 * i, 0.8), ts + 0.01, 0.55, 0.15)
    sfx.add(whoosh(0.5, 400, 1500, 0.5), SPIKE + 0.35, 0.5, -0.4)
    sfx.add(squeak(2900, 0.13, 1.0), TAKEOFF - 0.12, 0.8)
    sfx.add(footstep(1.4), TAKEOFF - 0.1, 1.0)

    # takeoff: the ground cracks
    music.add(crash(1.0, 2.0), TAKEOFF, 0.8)
    music.add(taiko(1.4, 60), TAKEOFF, 1.0)
    sfx.add(sub_drop(120, 32, 1.4, 1.0), TAKEOFF, 1.0)
    sfx.add(debris(1.0, 0.9, 200), TAKEOFF, 0.8, -0.2)
    sfx.add(rumble(1.0, 1.0), TAKEOFF, 0.9)
    sfx.add(smack(0.6), TAKEOFF, 0.5)
    # rise: wind rush climbing, music riser
    sfx.add(whoosh(1.2, 300, 4500, 1.0, 0.8, 1.2), RISE - 0.1, 0.7, 0.2)
    riser = supersaw(hz('D4'), COMIC - RISE, 6, 25, 300, 8000, 0.9, 0.05)
    tt = np.arange(len(riser)) / SR
    riser = riser * (tt / tt[-1]) ** 2
    music.add(riser, RISE, 0.35)
    music.add(choir(['A4', 'D5', 'F5'], COMIC - RISE, 0.45, 0.8), RISE, 1.0)

    # --- IV. the rage close-up (red): the music cuts, a low burning roar under his scream ---
    # (the scream itself: the user's recording, placed at RAGE + 0.1)
    rage_n = int((COMIC_CUT - RAGE + 0.3) * SR)
    rt = np.arange(rage_n) / SR
    burn = np.tanh(fft_filter(rng.standard_normal(rage_n), 30, 260) * 5) * np.minimum(1, rt / 0.15) * np.exp(-np.maximum(0, rt - (COMIC_CUT - RAGE)) / 0.1)
    sfx.add(burn * 0.5, RAGE, 0.8)
    sfx.add(whoosh(0.7, 200, 2400, 0.8, 0.9, 1.5), RAGE - 0.05, 0.6, 0.2)
    sfx.add(sub_drop(70, 30, 0.9, 0.9), RAGE, 0.8)
    # the comic frame: silence, a held breath, a single tense note, then the whip
    sfx.add(vwoom(0.9, 0.9), COMIC_CUT, 0.3)
    tens = supersaw(hz('A5'), CONTACT - COMIC - 0.05, 4, 6, 1500, 9000, 0.25, 0.05)
    tens *= 1 + 0.4 * np.sin(2 * np.pi * 9 * np.arange(len(tens)) / SR)
    tension.add(tens, COMIC + 0.05, 0.18, 0.2)
    sfx.add(heartbeat(1.0), COMIC_CUT + 0.05, 0.45)
    sfx.add(whoosh(0.14, 900, 7000, 1.0, 0.5, 3.0), CONTACT - 0.12, 1.1, -0.3)   # the whip: ~3 frames
    tension.add(reverse_swell(0.6, 0.7), CONTACT - 0.6, 1.0)

    # contact: a gunshot, the biggest sound in the film
    sfx.add(gunshot(1.0), CONTACT, 1.3)
    sfx.add(smack(0.8), CONTACT, 0.6)
    sfx.add(sub_drop(130, 26, 2.2, 1.2), CONTACT, 0.9)
    music.add(orch_hit(['D3', 'A3', 'D4', 'A4']), CONTACT, 1.0)
    sfx.add(ring(HIT_HOLD + 0.4, 1.0, 3500), CONTACT + 0.02, 0.55)
    # the 1 s impact frame: a hit on every switch (black-and-white / red), alternating weight
    for k in (1, 2, 3):
        tk = CONTACT + 0.25 * k
        sfx.add(taiko(1.2 if k % 2 else 0.9, 58 if k % 2 else 75), tk, 0.9)
        sfx.add(sub_drop(100, 30, 0.6, 0.7), tk, 0.6)
        sfx.add(fft_filter(rng.standard_normal(int(0.03 * SR)) * np.exp(-np.arange(int(0.03 * SR)) / SR / 0.006), 2000, 12000), tk, 0.5)
    music.add(reverse_swell(0.35, 0.8), REENTRY - 0.35, 1.0)

    # --- V. re-entry: the chorus (Bb C Dm Dm), bigger: choir, open hats, octave lead ---
    t_end = OUTRO
    bars_c = int(np.ceil((t_end - REENTRY) / BAR)) + 1
    chorus_roots = ['Bb1', 'C2', 'D2', 'D2']
    roots_c = [chorus_roots[i % 4] for i in range(bars_c)]
    music.add(crash(1.0, 2.6), REENTRY, 0.9)
    music.add(kick(1.3), REENTRY, 1.0)
    b = 0
    while REENTRY + b * BEAT < t_end - 1e-6:
        tb = REENTRY + b * BEAT
        bi = b % 4
        if bi in (0, 2):
            music.add(kick(1.1), tb, 1.5)
        if bi in (1, 3):
            music.add(snare(1.1), tb, 1.25)
        music.add(hat(0.6, open_=(True)), tb + BEAT / 2, 0.3, 0.3)
        music.add(hat(0.5), tb, 0.25, 0.3)
        if b % 8 == 0 and b:
            music.add(crash(0.7, 2.0), tb, 0.6)
        b += 1
    bl = bass_line(roots_c, 0, 0.85)
    music.add(bl[: int((t_end - REENTRY) * SR)], REENTRY, 1.4)
    for p, d in ((-0.4, 0), (0.4, 0.011)):
        pc = power_chords(roots_c, 'trem', 0.45)
        music.add(pc[: int((t_end - REENTRY) * SR)], REENTRY + d, 1.25, p)
    chords_c = [['Bb3', 'D4', 'F4'], ['C4', 'E4', 'G4'], ['D4', 'F4', 'A4'], ['D4', 'F4', 'A4']]
    for i in range(bars_c):
        ts = REENTRY + i * BAR
        if ts < t_end:
            d = min(BAR, t_end - ts)
            music.add(strings(chords_c[i % 4], d, 0.45, 5000, 0.05), ts, 1.6)
            music.add(choir([c[:-1] + str(int(c[-1]) + 1) for c in chords_c[i % 4]], d, 0.35, 0.15), ts, 1.6)
    chorus = [('D6', 0, 1), ('C6', 1, 1), ('Bb5', 2, 1), ('A5', 3, 1),
              ('G5', 4, 1), ('A5', 5, 1), ('C6', 6, 2),
              ('D6', 8, 3), ('E6', 11, 0.5), ('F6', 11.5, 0.5),
              ('E6', 12, 1), ('D6', 13, 1), ('A5', 14, 2),
              ('D6', 16, 1), ('C6', 17, 1), ('Bb5', 18, 1), ('A5', 19, 1),
              ('G5', 20, 1), ('A5', 21, 1), ('C6', 22, 2)]
    ld = lead(chorus, 0.8)
    music.add(ld[: int((t_end - REENTRY) * SR)], REENTRY, 1.0, 0.05)
    ld8 = lead([(n[:-1] + str(int(n[-1]) - 1), s, d) for n, s, d in chorus], 0.45)
    music.add(ld8[: int((t_end - REENTRY) * SR)], REENTRY, 1.0, -0.1)
    # a short stop on beat into the past
    music.add(orch_hit(['D3', 'A3', 'D4', 'F4']), t_end - 0.02, 0.7)

    # the ball's flight and the floor
    sfx.add(ball_pass(0.6, 1.0), SMASH - 0.05, 1.0, 0.2)
    sfx.add(whoosh(0.45, 1200, 300, 0.7), FLOOR - 0.4, 0.6, -0.2)
    sfx.add(smack(1.3), FLOOR, 1.0)
    sfx.add(sub_drop(100, 24, 2.0, 1.3), FLOOR, 1.0)
    sfx.add(debris(1.6, 1.0, 380), FLOOR + 0.01, 0.9, 0.25)
    sfx.add(rumble(1.6, 1.2), FLOOR, 1.0)
    sfx.add(taiko(1.5, 50), FLOOR, 0.9)
    sfx.add(ring(0.9, 0.8, 4100), FLOOR + 0.05, 0.5)
    music.add(crash(1.1, 2.6), FLOOR, 0.9)
    sfx.add(bounce(1.0, 170), FLOOR + 0.32, 0.6, 0.4)
    # the roar: score slam
    music.add(brass(['D4', 'F4', 'A4', 'D5'], 0.6, 1.0), SCORE, 0.9)
    music.add(taiko(1.2, 65), SCORE, 0.9)

    # --- VI. the outro: the past again, then the answer ---
    callback = [('A4', 0.15, 0.7), ('D5', 0.75, 0.5), ('C5', 1.2, 0.5), ('A4', 1.65, 1.0)]
    for nm, t0, d in callback:
        past.add(piano(hz(nm), d, 0.9), OUTRO + t0, 1.0, -0.1)
    past.add(piano(hz('D3'), 1.6, 0.5), OUTRO + 0.15, 0.8)
    past.add(strings(['D3', 'A3', 'F4'], 1.9, 0.3, 1600, 0.4), OUTRO, 1.0)
    sfx.add(roll(1.7, 0.9), OUTRO + 0.05, 0.8, 0.5)
    sfx.add(heartbeat(0.8), OUTRO + 0.9, 0.45)
    # the match cut
    music.add(reverse_swell(0.5, 0.6), MATCH_CUT - 0.5, 1.0)
    music.add(orch_hit(['F3', 'A3', 'C4', 'F4']), MATCH_CUT, 1.0)
    music.add(crash(1.0, 2.6), MATCH_CUT, 0.9)
    sfx.add(sub_drop(90, 30, 1.2, 0.8), MATCH_CUT, 0.9)
    bars_o = int(np.ceil((CARD - MATCH_CUT) / BAR)) + 1
    roots_o = ['F2', 'C2', 'D2', 'Bb1']
    for i in range(int((CARD - MATCH_CUT) / BEAT) + 1):
        tb = MATCH_CUT + i * BEAT
        if tb < CARD:
            music.add(kick(1.0), tb, 1.4 if i % 2 == 0 else 0.9)
            if i % 2:
                music.add(snare(0.9), tb, 0.7)
            music.add(hat(0.5, True), tb + BEAT / 2, 0.25, 0.3)
    bl = bass_line([roots_o[i % 4] for i in range(bars_o)], 0, 0.8)
    music.add(bl[: int((CARD - MATCH_CUT) * SR)], MATCH_CUT, 1.4)
    pc = power_chords([roots_o[i % 4] for i in range(bars_o)], 'ring', 0.4)
    music.add(pc[: int((CARD - MATCH_CUT) * SR)], MATCH_CUT, 1.2, 0.3)
    music.add(strings(['F3', 'A3', 'C4', 'F4'], CARD - MATCH_CUT, 0.45, 5000, 0.05), MATCH_CUT, 1.6)
    music.add(choir(['F4', 'A4', 'C5'], CARD - MATCH_CUT, 0.4, 0.2), MATCH_CUT, 1.0)
    music.add(lead([('C6', 0, 1), ('A5', 1, 1), ('F5', 2, 1), ('G5', 3, 1), ('A5', 4, 2)], 0.75), MATCH_CUT, 1.0)

    # end card: swell, the title slam, final D major chord (the answer), piano motif resolved
    music.add(reverse_swell(0.35, 0.6), TITLE - 0.35, 1.0)
    for i, tb in enumerate(np.arange(CARD, TITLE, BEAT / 2)):
        music.add(taiko(0.6 + 0.2 * i, 75), tb, 0.8)
    music.add(orch_hit(['D3', 'A3', 'D4', 'F#4']), TITLE, 1.2)
    music.add(crash(1.0, 3.2), TITLE, 0.9)
    sfx.add(sub_drop(100, 28, 2.4, 1.0), TITLE, 0.9)
    music.add(strings(['D3', 'A3', 'D4', 'F#4', 'A4'], END - TITLE - 0.3, 0.55, 4500, 0.08), TITLE + 0.05, 1.0)
    music.add(choir(['D4', 'F#4', 'A4', 'D5'], END - TITLE - 0.3, 0.45, 0.3), TITLE + 0.05, 1.0)
    for nm, t0, d in (('A5', 0.6, 0.6), ('D6', 1.1, 0.5), ('C#6', 1.5, 0.5), ('D6', 1.9, 1.4)):
        music.add(piano(hz(nm), d, 0.9), TITLE + t0, 0.9, 0.2)
    music.add(sparkle(0.8), TITLE + 1.9, 0.7, -0.3)
    return past, music, tension, sfx


def main():
    root = Path(__file__).resolve().parents[1]
    past, music, tension, sfx = compose()
    # the past is heard through a wall: low-passed, wet
    p = fft_filter(past.x, 60, 1800)
    p = 0.55 * p + 0.75 * convolve(p, HALL)
    mus = music.x + 0.28 * convolve(music.x, HALL)
    mus = compress(mus, -24, 5, 0.003, 0.2)          # dense, loud band under the stingers (anime OP energy)
    t = np.arange(N) / SR
    # duck the present music under the big hits, and gate it out in the comic silence
    duck = np.ones(N)
    for ht, depth, rel in ((REENTRY - 0.4, 0.0, 0.4), (FLOOR, 0.35, 0.4), (TAKEOFF, 0.5, 0.3)):
        m = (t >= ht) & (t < ht + rel)
        duck[m] = np.minimum(duck[m], depth + (1 - depth) * ((t[m] - ht) / rel) ** 2)
    silence = ((t > COMIC + 0.03) & (t < CONTACT - 0.003)) | ((t > CONTACT + 0.4) & (t < REENTRY - 0.36)) | ((t > OUTRO + 0.35) & (t < MATCH_CUT - 0.55))   # rage + comic; inside the impact hold; last year
    gate = np.where(silence, 0.0, 1.0)
    gate = fft_filter(gate, 0, 40)
    mus = mus * np.clip(gate, 0, 1)[:, None] * duck[:, None]
    ten = tension.x + 0.4 * convolve(tension.x, HALL)

    def rms_db(x, a, b):
        seg = x[int(a * SR):int(b * SR)]
        return 20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-12)

    def to_db(x, a, b, target):
        return x * 10 ** ((target - rms_db(x, a, b)) / 20)
    # section loudness (dBFS RMS): the past is intimate, the drop and chorus are the loudest music, the comic is near silence
    mus = to_db(mus, ATTACK + 0.2, COMIC - 0.1, -17.0)
    p = to_db(p, 0.7, FLASH - 0.1, -27.0)
    ten = to_db(ten, COMIC_CUT + 0.1, CONTACT - 0.05, -34.0)
    score = compress(mus + p + ten, -7, 4, 0.0015, 0.12)        # catch the stingers, keep the band up
    s = sfx.x + 0.18 * convolve(sfx.x, ROOM) + 0.12 * convolve(sfx.x, HALL)
    # crowd: muffled in the past, alive today, erupting on the win; silent in the comic frame
    def level(tt):
        return smooth_steps(tt, [(0, 0), (0.7, 0.35), (5.4, 0.35), (5.45, 0.55), (RAGE - 0.05, 0.6), (RAGE + 0.1, 0.0),
                                 (REENTRY - 0.1, 0.0), (REENTRY + 0.2, 0.55), (OUTRO, 0.55), (OUTRO + 0.02, 0.3), (MATCH_CUT - 0.02, 0.3),
                                 (MATCH_CUT + 0.02, 0.6), (CARD, 0.6), (CARD + 1.3, 0.2), (END, 0.0)])

    def cheer(tt):
        return smooth_steps(tt, [(0, 0), (9.9, 0), (10.1, 0.25), (RAGE - 0.05, 0.35), (RAGE + 0.1, 0), (FLOOR, 0), (FLOOR + 0.2, 0.5),
                                 (ROAR + 0.1, 1.0), (OUTRO - 0.4, 0.8), (OUTRO, 0.0), (MATCH_CUT, 0.0), (MATCH_CUT + 0.1, 0.9), (CARD, 0.7),
                                 (CARD + 1.4, 0.15), (END, 0)])
    c = crowd(level, cheer)
    past_mask = ((t < 5.42) | ((t >= OUTRO) & (t < MATCH_CUT)))[:, None]
    c = np.where(past_mask, fft_filter(c, 80, 900) * 1.6, c)
    c = c + 0.3 * convolve(c, HALL)

    def norm_write(x, path, peak=0.89):
        x = x / (np.abs(x).max() + 1e-9) * peak
        fade = np.ones(N)
        fe = int((END - 0.9) * SR)
        fade[fe:] = np.clip(1 - (np.arange(N - fe) / SR) / 0.85, 0, 1)
        x = x * fade[:, None]
        x = x[: int(END * SR)]
        path.parent.mkdir(parents=True, exist_ok=True)
        import wave
        with wave.open(str(path), 'wb') as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
        print('wrote', path, f'{len(x) / SR:.2f}s')

    norm_write(score, root / 'music' / 'anime_score.wav', 0.95)
    norm_write(compress(s, -8, 2, 0.001, 0.2), root / 'sfx' / 'anime_sfx.wav')
    norm_write(c, root / 'sfx' / 'anime_crowd.wav', 0.6)


if __name__ == '__main__':
    main()
