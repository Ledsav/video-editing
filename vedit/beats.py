"""Music analysis for cutting on the beat: tempo, beat grid, downbeats and energy sections.

Pure numpy: spectral-flux onset envelope, autocorrelation tempo estimate and
dynamic-programming beat tracking (Ellis 2007).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .analyze import decode_audio

SR = 22050
HOP = 512
NFFT = 2048


def onset_envelope(y: np.ndarray) -> np.ndarray:
    if len(y) < NFFT:
        return np.zeros(1)
    n = 1 + (len(y) - NFFT) // HOP
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    frames = y[idx] * np.hanning(NFFT)[None, :]
    mag = np.abs(np.fft.rfft(frames, axis=1))
    # log-compressed, coarse bands (approx. mel) to emphasise percussive change
    edges = np.unique(np.geomspace(1, mag.shape[1] - 1, 48).astype(int))
    bands = np.add.reduceat(mag, edges, axis=1)
    logb = np.log1p(10 * bands)
    flux = np.maximum(np.diff(logb, axis=0), 0).sum(axis=1)
    flux = np.concatenate([[0], flux])
    flux -= np.convolve(flux, np.ones(16) / 16, mode="same")  # remove slow trend
    flux = np.maximum(flux, 0)
    return flux / (flux.max() + 1e-9)


def estimate_tempo(env: np.ndarray, lo: float = 60, hi: float = 190, prior: float = 120) -> float:
    fps = SR / HOP
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    lags = np.arange(len(ac))
    valid = (lags >= fps * 60 / hi) & (lags <= fps * 60 / lo)
    bpm = 60 * fps / np.maximum(lags, 1)
    weight = np.exp(-0.5 * (np.log2(bpm / prior) / 0.9) ** 2)
    score = np.where(valid, ac * weight, -np.inf)
    lag = int(np.argmax(score))
    # parabolic refinement
    if 1 <= lag < len(ac) - 1:
        a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]
        denom = a - 2 * b + c
        lag = lag + (0.5 * (a - c) / denom if denom else 0)
    return float(60 * fps / lag)


def track_beats(env: np.ndarray, bpm: float, tightness: float = 100) -> np.ndarray:
    fps = SR / HOP
    period = 60 * fps / bpm
    n = len(env)
    score = env.copy()
    back = -np.ones(n, dtype=int)
    window = np.arange(-int(round(2 * period)), -int(round(period / 2)) + 1)
    penalty = -tightness * np.log(-window / period) ** 2
    for i in range(n):
        j = i + window
        ok = j >= 0
        if not ok.any():
            continue
        cand = score[j[ok]] + penalty[ok]
        k = int(np.argmax(cand))
        if cand[k] > 0:
            score[i] = env[i] + cand[k]
            back[i] = j[ok][k]
    # start from the best-scoring frame in the last period
    tail = max(0, n - int(period))
    i = tail + int(np.argmax(score[tail:]))
    beats = []
    while i >= 0:
        beats.append(i)
        i = back[i]
    beats = np.array(beats[::-1])
    # drop weak leading/trailing beats
    if len(beats) > 4:
        strong = env[beats] > 0.15 * np.median(env[beats] + 1e-9)
        beats = beats[np.argmax(strong):]
    return beats / fps + NFFT / 2 / SR  # frame index -> window centre time


def analyze_music(path: str | Path) -> dict:
    y = decode_audio(path, SR)
    duration = len(y) / SR
    env = onset_envelope(y)
    bpm = estimate_tempo(env)
    beats = track_beats(env, bpm)
    # downbeats: choose the phase (0..3) whose beats carry the most low-frequency energy/onset
    fps = SR / HOP
    if len(beats) >= 8:
        frames = np.round((beats - NFFT / 2 / SR) * fps).astype(int)
        strength = env[np.clip(frames, 0, len(env) - 1)]
        phase = int(np.argmax([strength[p::4].mean() for p in range(4)]))
        downbeats = beats[phase::4]
    else:
        downbeats = beats[:1]
    # energy sections: RMS per second, smoothed; report big rises (drops / builds)
    sec = SR
    rms = np.sqrt(np.array([np.mean(y[i:i + sec] ** 2) for i in range(0, max(len(y) - sec, 1), sec)]) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    smooth = np.convolve(db, np.ones(3) / 3, mode="same") if len(db) >= 3 else db
    rises = [float(i) for i in range(2, len(smooth)) if smooth[i] - smooth[i - 2] > 6]
    sections = []
    for r in rises:
        if not sections or r - sections[-1] > 4:
            sections.append(r)
    return {
        "file": str(path),
        "duration": round(duration, 3),
        "tempo": round(bpm, 2),
        "beat_period": round(60 / bpm, 4),
        "beats": [round(float(b), 3) for b in beats],
        "downbeats": [round(float(b), 3) for b in downbeats],
        "energy_db_per_s": [round(float(v), 1) for v in db],
        "energy_rises": sections,
    }


def save(report: dict, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))
    return out
