"""Procedural sound design (transition whooshes, impacts, risers) and placeholder music beds.

Real projects should use licensed music; the beds here exist so an edit can be timed
and previewed before the final track is chosen, and so tests have audio to work with.
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

SR = 48000


def _write(path: Path, x: np.ndarray) -> Path:
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    peak = np.abs(x).max() or 1.0
    x = x / peak * 0.89
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return path


def _fft_filter(x: np.ndarray, lo: float = 0.0, hi: float = SR / 2, sr: int = SR) -> np.ndarray:
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    resp = 1.0 / (1 + (f / max(hi, 1)) ** 4)
    if lo > 0:
        resp *= 1 - 1.0 / (1 + (f / lo) ** 4)
    return np.fft.irfft(X * resp, n=len(x))


def _tv_bandpass(x: np.ndarray, centers: np.ndarray, q: float = 1.2) -> np.ndarray:
    """Time-varying band-pass via overlap-added FFT frames. centers: Hz per sample."""
    n = 2048
    hop = n // 4
    win = np.hanning(n)
    out = np.zeros(len(x) + n)
    norm = np.zeros(len(x) + n)
    f = np.fft.rfftfreq(n, 1 / SR)
    for start in range(0, len(x), hop):
        seg = x[start:start + n]
        if len(seg) < n:
            seg = np.pad(seg, (0, n - len(seg)))
        c = centers[min(start + n // 2, len(centers) - 1)]
        resp = np.exp(-0.5 * (np.log2(np.maximum(f, 1) / c) * q) ** 2)
        y = np.fft.irfft(np.fft.rfft(seg * win) * resp, n=n)
        out[start:start + n] += y * win
        norm[start:start + n] += win ** 2
    return (out / np.maximum(norm, 1e-6))[: len(x)]


def _env(t: np.ndarray, peak: float, attack: float, release: float) -> np.ndarray:
    up = np.clip(t / max(peak, 1e-3), 0, 1) ** attack
    down = np.exp(-np.maximum(t - peak, 0) * release)
    return np.where(t <= peak, up, down)


def whoosh(rng) -> tuple[np.ndarray, float]:
    d, peak = 0.9, 0.45
    t = np.arange(int(d * SR)) / SR
    noise = rng.standard_normal(len(t))
    centers = 300 * np.exp(2.2 * np.sin(np.pi * np.clip(t / d, 0, 1)))
    x = _tv_bandpass(noise, centers, q=0.9) * _env(t, peak, 2.5, 7)
    pan = np.clip(t / d, 0, 1)
    return np.stack([x * np.cos(pan * np.pi / 2), x * np.sin(pan * np.pi / 2)], axis=1), peak


def impact(rng) -> tuple[np.ndarray, float]:
    d = 1.6
    t = np.arange(int(d * SR)) / SR
    freq = 38 + 70 * np.exp(-t * 18)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 3.2)
    click = _fft_filter(rng.standard_normal(len(t)), 200, 5000) * np.exp(-t * 45)
    tail = _fft_filter(rng.standard_normal(len(t)), 80, 1200) * np.exp(-t * 4) * 0.25
    return np.tanh(1.6 * (body + 0.6 * click + tail)), 0.0


def boom(rng) -> tuple[np.ndarray, float]:
    """Trailer 'braam': detuned low saws through a closing low-pass."""
    d = 2.8
    t = np.arange(int(d * SR)) / SR
    x = np.zeros_like(t)
    for f0 in (55, 55 * 1.005, 82.4, 110 * 0.997):
        x += 2 * ((t * f0) % 1) - 1
    x = _fft_filter(x, 30, 900) * _env(t, 0.06, 1, 1.1)
    sub = np.sin(2 * np.pi * 41 * t) * np.exp(-t * 1.3)
    return np.tanh(1.3 * (x * 0.5 + sub)), 0.05


def riser(rng) -> tuple[np.ndarray, float]:
    d = 2.5
    t = np.arange(int(d * SR)) / SR
    p = t / d
    noise = _tv_bandpass(rng.standard_normal(len(t)), 400 * 2 ** (4 * p), q=1.4)
    tone = np.sin(2 * np.pi * np.cumsum(180 * 2 ** (2.5 * p)) / SR) * 0.35
    x = (noise + tone) * p ** 2.2
    x[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    return x, d


def reverse_swell(rng) -> tuple[np.ndarray, float]:
    d = 1.4
    t = np.arange(int(d * SR)) / SR
    x = _fft_filter(rng.standard_normal(len(t)), 200, 6000) * np.exp(-t * 3.5)
    x += 0.4 * np.sin(2 * np.pi * 220 * t) * np.exp(-t * 2.5)
    x = x[::-1].copy()
    x[-int(0.008 * SR):] *= np.linspace(1, 0, int(0.008 * SR))
    return x, d


def glitch(rng) -> tuple[np.ndarray, float]:
    d = 0.45
    n = int(d * SR)
    x = np.zeros(n)
    pos = 0
    while pos < n:
        ln = int(rng.uniform(0.01, 0.05) * SR)
        f = rng.choice([110, 220, 440, 880, 1760, 3520]) * rng.uniform(0.9, 1.1)
        seg = np.sign(np.sin(2 * np.pi * f * np.arange(ln) / SR))
        if rng.random() < 0.4:
            seg = rng.standard_normal(ln)
        seg = np.round(seg * 4) / 4 * (0.4 + 0.6 * rng.random())
        x[pos:pos + ln] = seg[: n - pos]
        pos += ln + int(rng.uniform(0, 0.02) * SR)
    return x * np.exp(-np.arange(n) / SR * 4), 0.02


def tick(rng) -> tuple[np.ndarray, float]:
    t = np.arange(int(0.08 * SR)) / SR
    return np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 90), 0.0


SFX = {"whoosh": whoosh, "impact": impact, "boom": boom, "riser": riser,
       "reverse_swell": reverse_swell, "glitch": glitch, "tick": tick}


def make_sfx(out_dir: Path, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    meta = {}
    for name, fn in SFX.items():
        x, peak = fn(rng)
        _write(out_dir / f"{name}.wav", x)
        meta[name] = {"peak": peak, "duration": round(len(x) / SR, 3)}
    (out_dir / "sfx.json").write_text(json.dumps(meta, indent=1))
    return meta


# ----------------------------------------------------------------------------
# Placeholder music beds
# ----------------------------------------------------------------------------

MOODS = {
    #           bpm  scale    progression (scale degrees)  drums         brightness
    "uplifting": (118, "major", [0, 4, 5, 3], "pop", 3200),
    "tense": (96, "minor", [0, 0, 5, 6], "pulse", 1400),
    "sad": (68, "minor", [0, 5, 2, 6], None, 1100),
    "epic": (88, "minor", [0, 5, 2, 6], "epic", 2000),
    "chill": (84, "major", [0, 5, 3, 4], "soft", 1800),
    "hype": (128, "minor", [0, 5, 6, 4], "four", 4000),
    "dreamy": (76, "major", [0, 3, 5, 4], None, 2400),
}
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10]}


def _saw(f: float, n: int, detune: float = 0.0) -> np.ndarray:
    t = np.arange(n) / SR
    return sum(2 * ((t * f * (1 + d) + ph) % 1) - 1 for d, ph in ((-detune, 0.0), (detune, 0.37), (0, 0.71))) / 3


def music_bed(out: Path, mood: str = "uplifting", duration: float = 60.0, bpm: float | None = None,
              root: float = 110.0, seed: int = 1) -> dict:
    if mood not in MOODS:
        raise ValueError(f"unknown mood {mood!r}: {', '.join(MOODS)}")
    rng = np.random.default_rng(seed)
    tempo, scale_name, prog, drums, bright = MOODS[mood]
    tempo = bpm or tempo
    beat = 60 / tempo
    bar = 4 * beat
    n = int(duration * SR)
    pad = np.zeros(n)
    bass = np.zeros(n)
    drum = np.zeros(n)
    scale = SCALES[scale_name]

    def note(deg: int, octave: int = 0) -> float:
        semis = scale[deg % 7] + 12 * (deg // 7 + octave)
        return root * 2 ** (semis / 12)

    t_bar = 0.0
    i = 0
    while t_bar < duration:
        deg = prog[i % len(prog)]
        s, e = int(t_bar * SR), min(int((t_bar + bar) * SR), n)
        ln = e - s
        env = np.minimum(1, np.minimum(np.arange(ln) / (0.25 * SR), (ln - np.arange(ln)) / (0.15 * SR)))
        for k in (0, 2, 4):
            pad[s:e] += _saw(note(deg + k, 1), ln, 0.004) * env * 0.3
        for b in range(4):
            bs = s + int(b * beat * SR)
            bl = min(int(beat * SR), n - bs)
            if bl <= 0:
                break
            tt = np.arange(bl) / SR
            bass[bs:bs + bl] += np.sin(2 * np.pi * note(deg, -1) * tt) * np.exp(-tt * 2.5) * 0.8
            if drums:
                kick = np.sin(2 * np.pi * np.cumsum(45 + 120 * np.exp(-tt * 30)) / SR) * np.exp(-tt * 9)
                hit = drums == "four" or (drums in ("pop", "soft") and b in (0, 2)) or \
                      (drums == "epic" and b == 0) or drums == "pulse"
                if hit:
                    drum[bs:bs + bl] += kick * (0.5 if drums in ("soft", "pulse") else 1.0)
                if drums in ("pop", "four", "soft"):
                    hs = bs + int(beat * SR / 2)
                    hl = min(int(0.05 * SR), n - hs)
                    if hl > 0:
                        drum[hs:hs + hl] += rng.standard_normal(hl) * np.exp(-np.arange(hl) / SR * 80) * 0.25
                if drums in ("pop", "four") and b in (1, 3):
                    sl = min(int(0.2 * SR), n - bs)
                    drum[bs:bs + sl] += rng.standard_normal(sl) * np.exp(-np.arange(sl) / SR * 18) * 0.35
        t_bar += bar
        i += 1
    pad = _fft_filter(pad, 120, bright)
    hats = _fft_filter(drum, 30, 12000)
    mix = 0.55 * pad + 0.6 * _fft_filter(bass, 30, 400) + 0.55 * hats
    # gentle stereo widening on the pad + fade in/out
    left = mix + 0.08 * np.roll(pad, 240)
    right = mix - 0.08 * np.roll(pad, 240)
    st = np.stack([left, right], axis=1)
    fade = np.minimum(1, np.minimum(np.arange(n) / (1.5 * SR), (n - np.arange(n)) / (3 * SR)))[:, None]
    _write(out, np.tanh(st * fade * 1.2))
    return {"file": str(out), "mood": mood, "tempo": tempo, "beat_period": beat,
            "beats": [round(k * beat, 4) for k in range(int(duration / beat))]}
