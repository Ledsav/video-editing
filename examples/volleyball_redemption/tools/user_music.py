"""The user's own tracks (Suno), cut to the picture of story_full.json, plus the scream for the attack.

Reads user_audio/ (not committed):
  owatta_nara.mp3   終わったなら  86 bpm   the past: last year's lost point (and its callback in the outro)
  uchikaese.mp3     打ち返せ      136 bpm  today: the attack, the roar, the end card
  waaaaah.mp3       Waaaaah!      152 bpm  source of the scream (8.45 s: a rising "WAAAAH", sustained to 10.7 s)
Writes (48 kHz stereo, edit time 0 = sample 0):
  music/user_score.wav    the songs, edited on their beats
  sfx/user_scream.wav     the scream on the rage close-up, cut by the cannon at contact
  sfx/user_cannon.wav     the hit as a cannon: a 1 s charge (rising whine, accelerating pulse, crackle, swelling rumble) cut to
                          silence 50 ms before contact, then the cannon blast, its rumble and the arena's echoes (contact, 12.30 s)
  sfx/anime_sfx_duck.wav  tools/anime_sound.py's sound design, dipped under the blast (contact to +1 s) so the cannon is heard alone

Cut points (song times found with `vedit beats` + the nearest transient):
  0.00 - 5.42  終わったなら from its start: the loud opening over the dig; its quiet, bass-less passage (2.4 s) begins as last
               year's ball hits the floor (2.22).
  5.42 - 11.05 打ち返せ, its drop (3.975 s) on "THIS TIME, HE ATTACKS." (7.05); the break before it plays under the eyes.
  11.05 -      the music cuts on the rage close-up: the scream over the charge, then the cannon (12.30) and the 1 s impact frame.
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
GAP = 0.05                    # silence before the cannon (1.5 frames): the charge, the scream and the sound design all stop


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


def cannon_charge(dur=1.0, seed=11):
    """the charge-up into the hit (anime power charge): a whine sweeping 110 Hz -> 2.6 kHz and accelerating, pulsing faster and
    faster (6 -> 45 Hz), electric crackle getting denser, a low rumble swelling; it ends in a short upward rip."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = t / dur
    f = 110 * (2600 / 110) ** (u ** 1.7)
    ph = 2 * np.pi * np.cumsum(f) / SR
    whine = (np.sin(ph) + 0.45 * np.sin(2 * ph + 0.3) + 0.2 * np.sin(3 * ph + 1.1)) * u ** 1.4
    rate = 6 + 39 * u ** 2
    whine *= 0.55 + 0.45 * np.sin(2 * np.pi * np.cumsum(rate) / SR)
    clicks = np.zeros(n)
    for i in np.flatnonzero(rng.random(n) < (40 + 2200 * u ** 2.5) / SR):
        k = min(n - i, 90)
        clicks[i:i + k] += rng.standard_normal(k) * np.exp(-np.arange(k) / 12) * (0.3 + u[i])
    crackle = bandpass(clicks, 1800, 12000) * 0.5 + bandpass(rng.standard_normal(n), 2500, 9000) * u ** 3 * 0.25
    rumble = bandpass(rng.standard_normal(n), 25, 110) * u ** 2 * 1.4
    x = np.tanh((whine * 0.9 + crackle + rumble) * 1.6)
    x *= np.minimum(1, t / 0.05)
    return np.stack([x, x], 1)


def cannon(seed=13):
    """a cannon in an arena: the blast (a broadband burst, 12 ms), the body (low noise, 0.18 s), the sub punch (58 -> 30 Hz, 0.7 s),
    saturated; then a long rumble, falling debris and three echoes off the stands."""
    rng = np.random.default_rng(seed)
    n = int(3.6 * SR)
    t = np.arange(n) / SR
    blast = bandpass(rng.standard_normal(n), 40, 7000) * np.exp(-t / 0.012) * 1.5
    body = bandpass(rng.standard_normal(n), 30, 420) * np.exp(-t / 0.18) * np.minimum(1, t / 0.002) * 1.7
    sub = np.sin(2 * np.pi * np.cumsum(30 + 28 * np.exp(-t / 0.08)) / SR) * np.exp(-t / 0.7) * 1.5
    dry = np.tanh((blast + body + sub) * 2.0)
    out = np.stack([dry, dry], 1)
    for dly, g, pan in ((0.17, 0.4, -0.6), (0.36, 0.25, 0.6), (0.62, 0.12, -0.3)):
        a = int(dly * SR)
        e = bandpass(dry[: n - a], 30, 1500) * g
        out[a:, 0] += e * (1 - pan)
        out[a:, 1] += e * (1 + pan)
    env = (1 - np.exp(-t / 0.05)) * np.exp(-t / 1.1)
    out += np.stack([bandpass(rng.standard_normal(n), 25, 250) for _ in range(2)], 1) * env[:, None] * 0.55
    debris = np.zeros(n)
    for i in np.flatnonzero((rng.random(n) < 120 / SR) & (t > 0.05) & (t < 0.9)):
        k = min(n - i, 200)
        debris[i:i + k] += rng.standard_normal(k) * np.exp(-np.arange(k) / 30) * np.exp(-t[i] / 0.4)
    out += np.stack([bandpass(debris, 1500, 9000)] * 2, 1) * 0.12
    return out


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
    place(scream, waah, 8.35, RAGE, CONTACT - GAP, fade_in=0.02, fade_out=0.03)                  # the rise starts 0.1 s into the close-up
    t = np.arange(N) / SR                                                                         # the charge overtakes it in its last 0.4 s
    scream *= np.where(t > CONTACT - GAP - 0.4, 1 - 0.5 * np.clip((t - (CONTACT - GAP - 0.4)) / 0.4, 0, 1), 1)[:, None]
    write(scream, root / 'sfx' / 'user_scream.wav', 0.98)

    shot = np.zeros((N, 2))
    ch = cannon_charge(1.0)
    a = int((CONTACT - GAP) * SR) - len(ch)                    # the charge cuts off GAP before contact: a breath of silence
    shot[a:a + len(ch)] += ch * 0.9
    g = cannon()
    a = int(CONTACT * SR)
    shot[a:a + len(g)] += g[: N - a]
    write(shot, root / 'sfx' / 'user_cannon.wav', 0.99)

    # the sound design under the blast: -20 dB from just before contact, back up over 0.8 s (the time-freeze ring returns in the hold)
    with wave.open(str(root / 'sfx' / 'anime_sfx.wav'), 'rb') as w:
        sfx = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, 2).astype(np.float64) / 32767
    t = np.arange(len(sfx)) / SR
    dip = 10 ** (-20 / 20)
    env = np.ones(len(sfx))
    a0, a1, a2 = CONTACT - GAP - 0.005, CONTACT + 0.25, CONTACT + 1.05
    env[(t >= a0) & (t < a1)] = dip
    k = (t >= a1) & (t < a2)
    env[k] = dip + (1 - dip) * ((t[k] - a1) / (a2 - a1)) ** 2
    out = np.zeros((N, 2))
    out[:len(sfx)] = sfx * env[:, None]
    write(out, root / 'sfx' / 'anime_sfx_duck.wav', np.abs(sfx).max())
