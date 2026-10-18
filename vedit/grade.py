"""Color grading: parameter model, 3D LUT generation and ffmpeg finishing filters.

A grade is a flat dict of parameters (NEUTRAL lists them all). Tone presets and
story-arc keyframes are partial dicts that get blended with NEUTRAL by intensity
and interpolated over time, so every frame of the edit can have its own look.

Color math happens in a generated .cube LUT (fast in ffmpeg via lut3d), while
spatial/temporal effects (grain, vignette, bloom, sharpening, lens fringing) are
appended as ffmpeg filters.
"""
from __future__ import annotations

import copy
import math
from pathlib import Path

import numpy as np

from .tones import TONES
from .util import VeditError, hex_to_rgb, stable_hash

NEUTRAL: dict = {
    # --- LUT parameters --------------------------------------------------------
    "exposure": 0.0,          # stops, -2..2
    "contrast": 0.0,          # -1..1, S-curve around pivot
    "pivot": 0.45,            # contrast pivot (display value)
    "saturation": 1.0,        # 0..2
    "vibrance": 0.0,          # -1..1, boosts low-saturation colors more
    "temperature": 0.0,       # -1 (cool) .. 1 (warm)
    "tint": 0.0,              # -1 (green) .. 1 (magenta)
    "lift": [0.0, 0.0, 0.0],  # per-channel shadow offset, -0.2..0.2
    "gamma": [1.0, 1.0, 1.0], # per-channel midtone power, 0.5..2 (>1 brightens)
    "gain": [1.0, 1.0, 1.0],  # per-channel highlight multiplier, 0.5..1.5
    "shadow_tint": [0.0, 0.0, 0.0],     # RGB offset added to shadows (or {"color","amount"})
    "highlight_tint": [0.0, 0.0, 0.0],  # RGB offset added to highlights
    "tint_balance": 0.0,      # -1 favours shadow tint .. 1 favours highlight tint
    "black_point": 0.0,       # >0 lifts blacks (matte/faded), <0 crushes
    "highlight_rolloff": 0.0, # 0..1 soft film-like shoulder
    "bleach": 0.0,            # 0..1 bleach bypass
    "mono": 0.0,              # 0..1 black and white
    "mono_mix": [0.30, 0.59, 0.11],  # channel mixer for mono (e.g. [0.5,0.4,0.1] = red filter)
    # --- finishing (ffmpeg filters) -----------------------------------------
    "grain": 0.0,             # 0..1 film grain
    "vignette": 0.0,          # 0..1
    "bloom": 0.0,             # 0..1 highlight glow
    "sharpen": 0.0,           # 0..1
    "chroma_shift": 0.0,      # 0..1 lens RGB fringing
}

LUT_KEYS = ["exposure", "contrast", "pivot", "saturation", "vibrance", "temperature", "tint",
            "lift", "gamma", "gain", "shadow_tint", "highlight_tint", "tint_balance",
            "black_point", "highlight_rolloff", "bleach", "mono", "mono_mix"]
FINISH_KEYS = ["grain", "vignette", "bloom", "sharpen", "chroma_shift"]

LUMA = np.array([0.2126, 0.7152, 0.0722])


# ----------------------------------------------------------------------------
# Parameter handling
# ----------------------------------------------------------------------------

def _tint_to_offset(value) -> list[float]:
    if isinstance(value, dict):
        rgb = np.array(hex_to_rgb(value["color"]))
        amount = float(value.get("amount", 0.15))
        return list((rgb - float(rgb @ LUMA)) * amount)
    if isinstance(value, str):
        color, _, amount = value.partition("@")
        return _tint_to_offset({"color": color, "amount": float(amount or 0.15)})
    return [float(v) for v in value]


def normalize(params: dict) -> dict:
    """Fill defaults and convert authoring shorthands into plain numbers."""
    out = copy.deepcopy(NEUTRAL)
    for k, v in (params or {}).items():
        if k not in NEUTRAL:
            raise VeditError(f"unknown grade parameter {k!r}. Known: {', '.join(NEUTRAL)}")
        if k in ("shadow_tint", "highlight_tint"):
            out[k] = _tint_to_offset(v)
        elif isinstance(NEUTRAL[k], list):
            out[k] = [float(x) for x in (v if isinstance(v, list) else [v, v, v])]
        else:
            out[k] = float(v)
    return out


def lerp_params(a: dict, b: dict, t: float) -> dict:
    out = {}
    for k in NEUTRAL:
        va, vb = a[k], b[k]
        if isinstance(va, list):
            out[k] = [x + (y - x) * t for x, y in zip(va, vb)]
        else:
            out[k] = va + (vb - va) * t
    return out


def look(tone: str | None = None, intensity: float = 1.0, overrides: dict | None = None) -> dict:
    """Resolve a tone preset (+ intensity, + raw overrides) into a full parameter dict."""
    base = {}
    if tone:
        if tone not in TONES:
            raise VeditError(f"unknown tone {tone!r}. Run `vedit tones` to list them.")
        base = TONES[tone]["params"]
    params = lerp_params(normalize({}), normalize(base), float(intensity))
    if overrides:
        ov = normalize(overrides)
        for k in overrides:
            params[k] = ov[k]
    return params


def resolve(spec: dict | str | None) -> dict:
    """Accept a tone name or {"tone", "intensity", "overrides"|raw params}."""
    if spec is None:
        return look()
    if isinstance(spec, str):
        return look(spec)
    spec = dict(spec)
    tone = spec.pop("tone", None)
    intensity = spec.pop("intensity", 1.0)
    overrides = dict(spec.pop("overrides", {}) or {})
    spec.pop("ease", None)
    overrides.update({k: v for k, v in spec.items() if k in NEUTRAL})
    return look(tone, intensity, overrides)


def distance(a: dict, b: dict) -> float:
    d = 0.0
    for k in LUT_KEYS + FINISH_KEYS:
        va, vb = a[k], b[k]
        if isinstance(va, list):
            d = max(d, max(abs(x - y) for x, y in zip(va, vb)))
        else:
            d = max(d, abs(va - vb))
    return d


def is_identity(p: dict) -> bool:
    return distance(p, normalize({})) < 1e-4


# ----------------------------------------------------------------------------
# LUT math
# ----------------------------------------------------------------------------

def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def apply_grade(rgb: np.ndarray, p: dict) -> np.ndarray:
    """Apply the LUT part of a grade to display-referred RGB in [0, 1]. Shape (..., 3)."""
    x = np.clip(np.asarray(rgb, dtype=np.float64), 0.0, 1.0)

    # White balance + exposure in (approximately) linear light.
    lin = x ** 2.2
    t, g = p["temperature"], p["tint"]
    wb = np.array([1 + 0.20 * t + 0.06 * g, 1 - 0.14 * g, 1 - 0.20 * t + 0.06 * g])
    wb = wb / float(wb @ LUMA)
    lin = lin * wb * (2.0 ** p["exposure"])
    x = np.maximum(lin, 0.0) ** (1 / 2.2)

    # Lift / gamma / gain (color wheels).
    lift, gamma, gain = np.array(p["lift"]), np.array(p["gamma"]), np.array(p["gain"])
    x = x * gain + lift * (1 - np.clip(x, 0, 1))
    x = np.maximum(x, 0.0) ** (1 / np.maximum(gamma, 1e-3))

    # Contrast: pivot-preserving S-curve (keeps values above 1 for the rolloff below).
    c = p["contrast"]
    if abs(c) > 1e-6:
        pivot = min(max(p["pivot"], 0.05), 0.95)
        k = math.log(0.5) / math.log(pivot)
        xc = np.clip(x, 1e-6, 1 - 1e-6)
        w = xc ** k
        pw = math.exp(1.25 * c)
        s = w ** pw / (w ** pw + (1 - w) ** pw)
        x = s ** (1 / k) + (x - xc)

    # Highlight rolloff: tanh shoulder above a knee, otherwise hard clip.
    r = p["highlight_rolloff"]
    if r > 1e-6:
        knee = 1 - 0.45 * r
        over = x > knee
        x = np.where(over, knee + (1 - knee) * np.tanh((x - knee) / (1 - knee)), x)
    x = np.clip(x, 0.0, 1.0)

    # Black point: matte lift or crush.
    bp = p["black_point"]
    if bp > 0:
        x = bp + x * (1 - bp)
    elif bp < 0:
        x = np.clip((x + bp) / (1 + bp), 0, 1)

    # Saturation + vibrance.
    y = (x @ LUMA)[..., None]
    chroma = x - y
    cur_sat = np.clip((x.max(-1) - x.min(-1))[..., None] * 1.5, 0, 1)
    factor = p["saturation"] * (1 + p["vibrance"] * (1 - cur_sat))
    x = y + chroma * factor

    # Bleach bypass: overlay luminance onto color, partially desaturated.
    b = p["bleach"]
    if b > 1e-6:
        y = (np.clip(x, 0, 1) @ LUMA)[..., None]
        xc = np.clip(x, 0, 1)
        ov = np.where(y < 0.5, 2 * y * xc, 1 - 2 * (1 - y) * (1 - xc))
        ov = 0.5 * ov + 0.5 * (ov @ LUMA)[..., None]
        x = x + (ov - x) * b

    # Monochrome via channel mixer.
    m = p["mono"]
    if m > 1e-6:
        mix = np.array(p["mono_mix"])
        mix = mix / max(mix.sum(), 1e-6)
        ym = (np.clip(x, 0, 1) @ mix)[..., None]
        x = x + (ym - x) * m

    # Split toning (after mono so tinted black-and-white works).
    st, ht = np.array(p["shadow_tint"]), np.array(p["highlight_tint"])
    if np.any(st) or np.any(ht):
        y = np.clip(np.clip(x, 0, 1) @ LUMA, 0, 1)[..., None]
        bal = p["tint_balance"]
        ws = (1 - _smoothstep(0.0, 0.6, y)) * (1 - 0.6 * bal)
        wh = _smoothstep(0.35, 1.0, y) * (1 + 0.6 * bal)
        x = x + ws * st + wh * ht

    return np.clip(x, 0.0, 1.0)


def write_cube(params: dict, path: Path, size: int = 33) -> Path:
    v = np.linspace(0.0, 1.0, size)
    bb, gg, rr = np.meshgrid(v, v, v, indexing="ij")  # red varies fastest
    grid = np.stack([rr, gg, bb], axis=-1).reshape(-1, 3)
    out = apply_grade(grid, params)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["TITLE \"vedit\"", f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in out]
    path.write_text("\n".join(lines) + "\n")
    return path


def lut_for(params: dict, cache_dir: Path) -> Path | None:
    """Return a cached .cube for the LUT part of params (None if it is the identity)."""
    lut_params = {k: params[k] for k in LUT_KEYS}
    neutral = {k: NEUTRAL[k] for k in LUT_KEYS}
    if all(abs(_flat(lut_params[k]) - _flat(neutral[k])) < 1e-5 for k in LUT_KEYS):
        return None
    rounded = {k: (round(v, 4) if not isinstance(v, list) else [round(x, 4) for x in v])
               for k, v in lut_params.items()}
    path = cache_dir / f"lut_{stable_hash(rounded)}.cube"
    if not path.exists():
        write_cube(params, path)
    return path


def _flat(v) -> float:
    return sum(abs(x) for x in v) if isinstance(v, list) else v


# ----------------------------------------------------------------------------
# ffmpeg filters
# ----------------------------------------------------------------------------

def finishing_chain(p: dict, width: int, height: int, label: str, inp: str, out: str) -> list[str]:
    """Filtergraph statements applying grain/vignette/bloom/sharpen/fringing.

    Returns a list of statements that read [inp] and write [out]."""
    steps: list[str] = []
    cur = inp
    n = 0

    def nxt() -> str:
        nonlocal n
        n += 1
        return f"{label}f{n}"

    if p["sharpen"] > 0.01:
        o = nxt()
        steps.append(f"[{cur}]unsharp=5:5:{0.25 + 1.1 * p['sharpen']:.3f}:5:5:0[{o}]")
        cur = o
    if p["bloom"] > 0.01:
        a, b, c, o = nxt(), nxt(), nxt(), nxt()
        sigma = max(2.0, height * 0.018 * (0.6 + p["bloom"]))
        steps.append(f"[{cur}]format=gbrp,split[{a}][{b}]")
        steps.append(f"[{b}]curves=all='0/0 0.55/0 1/1',gblur=sigma={sigma:.1f}[{c}]")
        steps.append(f"[{a}][{c}]blend=all_mode=screen:all_opacity={0.2 + 0.6 * p['bloom']:.3f}[{o}]")
        cur = o
    if p["chroma_shift"] > 0.01:
        o = nxt()
        px = max(1, round(p["chroma_shift"] * width / 480))
        steps.append(f"[{cur}]rgbashift=rh=-{px}:bh={px}:edge=smear[{o}]")
        cur = o
    if p["vignette"] > 0.01:
        o = nxt()
        steps.append(f"[{cur}]vignette=angle={0.2 + 0.6 * p['vignette']:.3f}[{o}]")
        cur = o
    if p["grain"] > 0.01:
        o = nxt()
        steps.append(f"[{cur}]format=yuv420p,noise=c0s={round(3 + 26 * p['grain'])}:c0f=t+u[{o}]")
        cur = o
    steps.append(f"[{cur}]format=yuv420p[{out}]")
    return steps


def grade_chain(start: dict, end: dict, duration: float, fps: float, cache_dir: Path,
                width: int, height: int, label: str, inp: str, out: str) -> list[str]:
    """Filtergraph statements grading [inp] -> [out], ramping from `start` to `end`."""
    from .util import ff_escape

    steps: list[str] = []
    lut_a = lut_for(start, cache_dir)
    ramp = distance({k: start[k] for k in NEUTRAL}, end) > 0.015 and duration > 3 / fps
    graded = f"{label}g"
    if ramp:
        lut_b = lut_for(end, cache_dir)
        fa = f"lut3d=file='{ff_escape(lut_a)}':interp=tetrahedral" if lut_a else "null"
        fb = f"lut3d=file='{ff_escape(lut_b)}':interp=tetrahedral" if lut_b else "null"
        d = max(duration - 1.0 / fps, 1.0 / fps)
        steps.append(f"[{inp}]format=gbrp,split[{label}ra][{label}rb]")
        steps.append(f"[{label}ra]{fa}[{label}ra2]")
        steps.append(f"[{label}rb]{fb}[{label}rb2]")
        steps.append(f"[{label}ra2][{label}rb2]xfade=transition=fade:duration={d:.4f}:offset=0[{graded}]")
    elif lut_a:
        steps.append(f"[{inp}]format=gbrp,lut3d=file='{ff_escape(lut_a)}':interp=tetrahedral[{graded}]")
    else:
        steps.append(f"[{inp}]null[{graded}]")
    mid = lerp_params(start, end, 0.5)
    steps += finishing_chain(mid, width, height, label, graded, out)
    return steps
