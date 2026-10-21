"""The user's own tracks (Suno), cut to the picture of story_full.json, plus the scream for the attack.

Reads user_audio/ (not committed):
  owatta_nara.mp3   終わったなら  86 bpm   the past: last year's lost point (and its callback in the outro)
  uchikaese.mp3     打ち返せ      136 bpm  today: the attack, the roar, the end card
  waaaaah.mp3       Waaaaah!      152 bpm  source of the scream (8.45 s: a rising "WAAAAH", sustained to 10.7 s)
Writes (48 kHz stereo, edit time 0 = sample 0):
  music/user_score.wav    the songs, edited on their beats
  sfx/user_scream.wav     the scream on the rage close-up, cut by the gunshot at contact
  sfx/user_gunshot.wav    the hit as a pistol shot: a dry crack on top of the sound design's boom (contact, 12.30 s)

Cut points (song times found with `vedit beats` + the nearest transient):
  0.00 - 5.42  終わったなら from its start: the loud opening over the dig; its quiet, bass-less passage (2.4 s) begins as last
               year's ball hits the floor (2.22).
  5.42 - 11.05 打ち返せ, its drop (3.975 s) on "THIS TIME, HE ATTACKS." (7.05); the break before it plays under the eyes.
  11.05 -      the music cuts on the rage close-up: the scream, then the gunshot (12.30) and the 1 s impact frame in silence.
  14.20 - 18.5 打ち返せ's loudest section (44.58 s) slams in on the floor impact, under the roar.
  18.5 - 20.5  the past again: 終わったなら's quiet passage under last year's ball.
  20.5 - 26.1  打ち返せ's ending (74.55 s, the big hit at 76.31 s just before the card), out by 25.9.
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 48000
END = 26.1
N = int((END + 0.4) * SR)
root = Path(__file__).resolve().parent.parent
src = root / 'user_audio'

FLASH, ATTACK, RAGE, CONTACT, FLOOR, OUTRO, MATCH_CUT = 5.42, 7.05, 11.05, 12.30, 14.20, 18.5, 20.5


def load(name):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(src / name), '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def place(out, song, song_t, at, until, fade_in=0.01, fade_out=0.03, gain=1.0):
    """song from song_t, placed at edit time `at` up to `until` (equal-power fades at both ends)."""
    a, b = int(at * SR), min(N, int(until * SR))
    s0 = int(song_t * SR)
    seg = song[s0:s0 + (b - a)].copy()
    n = len(seg)
    env = np.ones(n)
    fi, fo = int(fade_in * SR), int(fade_out * SR)
    if fi:
        env[:fi] = np.sin(np.linspace(0, np.pi / 2, fi))
    if fo:
        env[-fo:] *= np.cos(np.linspace(0, np.pi / 2, fo))
    out[a:a + n] += seg * env[:, None] * gain


def bandpass(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def gunshot(seed=7):
    """a pistol shot in an arena: the supersonic crack (a 0.6 ms N-wave and a bright burst), the muzzle blast (mid noise, 30 ms),
    the chest thump (60 -> 38 Hz), two early reflections off the floor and the stands, then the hall's long dark tail."""
    rng = np.random.default_rng(seed)
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    crack = np.zeros(n)
    m = int(0.0006 * SR)
    crack[:m] = np.linspace(1, -1, m)
    crack += bandpass(rng.standard_normal(n), 2500, 16000) * np.exp(-t / 0.003) * 0.9
    blast = bandpass(rng.standard_normal(n), 120, 3500) * np.exp(-t / 0.03) * 1.3
    thump = np.sin(2 * np.pi * np.cumsum(38 + 22 * np.exp(-t / 0.02)) / SR) * np.exp(-t / 0.12) * 1.1
    dry = np.tanh((crack * 2.2 + blast + thump) * 2.2)
    out = np.stack([dry, dry], 1)
    for dly, g, pan in ((0.021, 0.45, -0.5), (0.058, 0.3, 0.6)):
        a = int(dly * SR)
        e = bandpass(dry[: n - a], 200, 6000) * g
        out[a:, 0] += e * (1 - pan) / 2 * 2
        out[a:, 1] += e * (1 + pan) / 2 * 2
    tail = np.stack([bandpass(rng.standard_normal(n), 80, 2200) for _ in range(2)], 1) * (np.exp(-t / 0.45) * np.minimum(1, t / 0.03))[:, None] * 0.22
    return out + tail


def write(x, path, peak=0.95):
    x = x[: int(END * SR)]
    x = x / (np.abs(x).max() + 1e-9) * peak
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
    print('wrote', path, f'{len(x) / SR:.2f}s')


if __name__ == '__main__':
    past, today, waah = load('owatta_nara.mp3'), load('uchikaese.mp3'), load('waaaaah.mp3')
    mus = np.zeros((N, 2))
    place(mus, past, 0.0, 0.0, FLASH + 0.06, fade_in=0.0, fade_out=0.08)                        # the past, out on the white flash
    off = 3.975 - ATTACK                                                                         # 打ち返せ's drop on the attack line
    place(mus, today, FLASH + off, FLASH, RAGE, fade_in=0.03, fade_out=0.04)
    place(mus, today, 44.58, FLOOR, OUTRO + 0.12, fade_in=0.04, fade_out=0.15)                  # the slam on the BAM (its transient left to the BAM)
    place(mus, past, 2.45, OUTRO, MATCH_CUT + 0.05, fade_in=0.15, fade_out=0.06, gain=0.9)        # memory
    place(mus, today, 74.55, MATCH_CUT, END, fade_in=0.004, fade_out=0.25)                       # the ending, out by 25.9
    write(mus, root / 'music' / 'user_score.wav')

    scream = np.zeros((N, 2))
    place(scream, waah, 8.35, RAGE, CONTACT + 0.01, fade_in=0.02, fade_out=0.025)                 # the rise starts 0.1 s into the close-up
    write(scream, root / 'sfx' / 'user_scream.wav', 0.98)

    shot = np.zeros((N, 2))
    g = gunshot()
    a = int(CONTACT * SR)
    shot[a:a + len(g)] += g[: N - a]
    write(shot, root / 'sfx' / 'user_gunshot.wav', 0.99)
