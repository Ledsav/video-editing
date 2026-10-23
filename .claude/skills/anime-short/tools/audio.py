"""Shared audio helpers for sfx.py and music_fit.py: 48 kHz stereo float arrays, filters, I/O, and edit-time lookups.

Times in the JSON plans are seconds on the edit's timeline, or references resolved against the project:
  "fight+1.25"      1.25 s into the timeline clip with id "fight" (clip starts: cumulative durations in edit.json)
  "fight:impact0"   the first impact of an anime_shot.html clip (from work/anime_times/fight.json, written by shot_stills.py)
  "fight:shot2"     the start of its third shot
  "fight:end"       the end of the clip
"""
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 48000


class Project:
    def __init__(self, root):
        self.root = Path(root).resolve()
        spec = json.loads((self.root / 'edit.json').read_text())
        self.starts, t = {}, 0.0
        for c in spec.get('timeline', []):
            d = float(c.get('duration') or 0)
            self.starts[c.get('id')] = (t, d)
            t += d
        self.total = t

    def t(self, ref):
        """edit seconds for a number or a reference string (see the module doc)."""
        if isinstance(ref, (int, float)):
            return float(ref)
        ref = str(ref).strip()
        off = 0.0
        for sign in ('+', '-'):
            i = ref.rfind(sign)
            if i > 0:
                off = float(ref[i:])
                ref = ref[:i]
                break
        if ':' in ref:
            cid, what = ref.split(':', 1)
            start, dur = self.starts[cid]
            if what == 'end':
                return start + dur + off
            times = json.loads((self.root / 'work' / 'anime_times' / f'{cid}.json').read_text())
            if what.startswith('impact'):
                return start + times['impacts'][int(what[6:] or 0)]['at'] + off
            if what.startswith('shot'):
                return start + times['shots'][int(what[4:] or 0)]['start'] + off
            raise ValueError(f'unknown reference {ref}')
        try:
            return float(ref) + off
        except ValueError:
            return self.starts[ref][0] + off

    def path(self, p):
        p = Path(p)
        return p if p.is_absolute() else self.root / p


def load(path, af=None):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path)] + (['-af', af] if af else []) + ['-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def write(x, path, peak=0.95):
    """normalised to `peak` (0.95 by default; keep headroom for AAC: previews overshoot near 1.0)."""
    x = x / (np.abs(x).max() + 1e-9) * peak
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
    print('wrote', path, f'{len(x) / SR:.2f} s')


def bandpass(x, lo, hi):
    """brick-wall FFT band (mono or stereo)."""
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(x.shape[0], 1 / SR)
    m = (f < lo) | (f > hi)
    X[m] = 0
    return np.fft.irfft(X, x.shape[0], axis=0)


def soft_band(x, lo=0.0, hi=SR / 2, slope=1.0):
    """zero-phase band filter with soft edges (mono or stereo)."""
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


def stereo(x, pan=0.0):
    if x.ndim == 2:
        return x
    a = (pan + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def place(out, sig, at, gain=1.0, pan=0.0):
    sig = stereo(sig, pan)
    a = int(round(at * SR))
    if a < 0:
        sig, a = sig[-a:], 0
    b = min(out.shape[0], a + sig.shape[0])
    if b > a:
        out[a:b] += sig[: b - a] * gain


def envelope(n, points, smooth=0.03):
    """gain curve from [(t, gain_db), ...] (held flat outside, linear in between), smoothed."""
    t = np.arange(n) / SR
    ts = [p[0] for p in points]
    g = 10 ** (np.interp(t, ts, [p[1] for p in points]) / 20)
    k = max(1, int(smooth * SR))
    return np.convolve(np.pad(g, (k, k), mode='edge'), np.ones(k) / k, 'same')[k:-k]
