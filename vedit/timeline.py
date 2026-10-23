"""Edit spec loading, validation and timeline resolution.

The spec (edit.json) describes WHAT the edit is; this module turns it into a
frame-accurate plan: where each clip lands on the output timeline, how it
transitions, and which grade it carries at its first and last frame (following
the story arc). See .claude/skills/video-edit/references/edit-spec.md.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import grade as G
from .util import (IMAGE_EXTS, SFX_DIR, VeditError, parse_time, probe,
                   require)

DEFAULT_OUTPUT = {"width": 1920, "height": 1080, "fps": 30, "crf": 18, "preset": "medium",
                  "audio_bitrate": "256k", "path": "out/final.mp4"}

# Named transitions -> how to build them. Any raw ffmpeg xfade name also works.
TRANSITION_PRESETS: dict[str, dict] = {
    "cut": {"kind": "cut"},
    "crossfade": {"kind": "xfade", "xfade": "fade", "duration": 0.6},
    "dissolve": {"kind": "xfade", "xfade": "dissolve", "duration": 0.7},
    "dip_black": {"kind": "xfade", "xfade": "fadeblack", "duration": 0.8},
    "dip_white": {"kind": "xfade", "xfade": "fadewhite", "duration": 0.6},
    "flash": {"kind": "xfade", "xfade": "fadewhite", "duration": 0.25, "sfx": "impact"},
    "whip_left": {"kind": "xfade", "xfade": "smoothleft", "duration": 0.3, "sfx": "whoosh"},
    "whip_right": {"kind": "xfade", "xfade": "smoothright", "duration": 0.3, "sfx": "whoosh"},
    "whip_up": {"kind": "xfade", "xfade": "smoothup", "duration": 0.3, "sfx": "whoosh"},
    "whip_down": {"kind": "xfade", "xfade": "smoothdown", "duration": 0.3, "sfx": "whoosh"},
    "slide_left": {"kind": "xfade", "xfade": "slideleft", "duration": 0.45, "sfx": "whoosh"},
    "slide_right": {"kind": "xfade", "xfade": "slideright", "duration": 0.45, "sfx": "whoosh"},
    "iris_open": {"kind": "xfade", "xfade": "circleopen", "duration": 0.7},
    "iris_close": {"kind": "xfade", "xfade": "circleclose", "duration": 0.7},
    "zoom_in": {"kind": "xfade", "xfade": "zoomin", "duration": 0.5, "sfx": "whoosh"},
    "blur": {"kind": "xfade", "xfade": "hblur", "duration": 0.5},
    "pixelate": {"kind": "xfade", "xfade": "pixelize", "duration": 0.6, "sfx": "glitch"},
    "radial": {"kind": "xfade", "xfade": "radial", "duration": 0.7},
    "wind": {"kind": "xfade", "xfade": "hlwind", "duration": 0.6, "sfx": "whoosh"},
    "slice": {"kind": "xfade", "xfade": "hrslice", "duration": 0.5},
    "fade_grays": {"kind": "xfade", "xfade": "fadegrays", "duration": 0.8},
    "glitch": {"kind": "cut", "effect": {"type": "glitch", "duration": 0.3, "intensity": 1.0},
               "sfx": "glitch"},
    "zoom_punch": {"kind": "cut", "punch": 0.22, "punch_duration": 0.35, "sfx": "impact",
                   "effect": {"type": "flash", "duration": 0.18, "intensity": 0.6}},
    "light_leak": {"kind": "xfade", "xfade": "fade", "duration": 1.0,
                   "overlay": {"hyperframes": "light-leak"}},
    "film_burn": {"kind": "cut", "overlay": {"hyperframes": "film-burn"},
                  "sfx": "whoosh"},
}


@lru_cache(maxsize=1)
def xfade_names() -> frozenset[str]:
    try:
        out = subprocess.run([require("ffmpeg"), "-hide_banner", "-h", "filter=xfade"],
                             capture_output=True, text=True).stdout
    except VeditError:
        return frozenset()
    names, grab = set(), False
    for line in out.splitlines():
        tok = line.strip().split()
        if not tok:
            continue
        if tok[0] == "transition":
            grab = True
            continue
        if grab:
            if tok[0] in ("duration", "offset", "expr"):
                break
            names.add(tok[0])
    names.discard("custom")
    return frozenset(names)


# ----------------------------------------------------------------------------
# Data classes
# ----------------------------------------------------------------------------

@dataclass
class Transition:
    kind: str = "cut"           # cut | xfade
    name: str = "cut"
    xfade: str | None = None
    duration: float = 0.0       # seconds the transition lasts
    overlap_frames: int = 0     # frames the two clips overlap (xfade only)
    sfx: str | None = None
    sfx_volume: float = 0.8
    effect: dict | None = None  # final-pass effect centred on the cut
    overlay: dict | None = None # graphics item centred on the cut
    punch: float = 0.0          # zoom-punch amount applied to the incoming clip
    punch_duration: float = 0.35
    boundary: float = 0.0       # output time of the cut / transition midpoint


@dataclass
class Clip:
    index: int
    id: str
    kind: str                   # video | image | color
    path: Path | None
    color: str | None
    src_in: float
    speed: float
    frames: int
    start_frame: int = 0
    fps: float = 30.0
    volume: float = 1.0
    has_audio: bool = False
    fit: str = "cover"
    crop: list | None = None
    motion: dict | None = None
    transition: Transition = field(default_factory=Transition)
    grade_spec: object = None
    grade_start: dict | None = None
    grade_end: dict | None = None
    src_duration: float = math.inf
    label: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.frames / self.fps

    @property
    def start(self) -> float:
        return self.start_frame / self.fps

    @property
    def end(self) -> float:
        return (self.start_frame + self.frames) / self.fps

    @property
    def src_span(self) -> float:
        return self.duration * self.speed


@dataclass
class Plan:
    spec: dict
    base_dir: Path
    output: dict
    clips: list[Clip]
    total_frames: int
    arc: list[dict]
    beats: list[float] | None = None

    @property
    def fps(self) -> float:
        return float(self.output["fps"])

    @property
    def duration(self) -> float:
        return self.total_frames / self.fps

    def clip_by_id(self, cid: str) -> Clip:
        for c in self.clips:
            if c.id == cid:
                return c
        raise VeditError(f"no clip with id {cid!r}")

    def resolve_time(self, item: dict, key: str = "start", default: float = 0.0) -> float:
        """Resolve start times that may be absolute, percentages, or clip-anchored."""
        anchor = item.get("at_clip")
        if anchor is not None:
            clip = self.clips[anchor] if isinstance(anchor, int) else self.clip_by_id(anchor)
            base = clip.start
            if item.get("anchor") == "end":
                base = clip.end
            return base + parse_time(item.get("offset", 0.0))
        if key in item:
            return parse_time(item[key], self.duration)
        return default

    def resolve_span(self, item: dict, default_duration: float = 3.0) -> tuple[float, float]:
        start = self.resolve_time(item)
        if "end_at_clip" in item:
            ref = item["end_at_clip"]
            clip = self.clips[ref] if isinstance(ref, int) else self.clip_by_id(ref)
            end = (clip.end if item.get("end_anchor") == "end" else clip.start) + parse_time(item.get("end_offset", 0.0))
        elif "end" in item:
            end = parse_time(item["end"], self.duration)
        elif "duration" in item:
            end = start + parse_time(item["duration"], self.duration)
        elif item.get("at_clip") is not None:
            anchor = item["at_clip"]
            clip = self.clips[anchor] if isinstance(anchor, int) else self.clip_by_id(anchor)
            end = clip.end
        else:
            end = start + default_duration
        return max(0.0, start), min(self.duration, end)

    def grade_at(self, t: float) -> dict:
        return arc_grade(self.arc, t)


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------

def load_spec(path: str | Path) -> tuple[dict, Path]:
    p = Path(path)
    if not p.exists():
        raise VeditError(f"spec not found: {p}")
    try:
        spec = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise VeditError(f"{p}: invalid JSON: {e}") from e
    return spec, p.resolve().parent


def resolve_path(base: Path, value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else (base / p)


def resolve_source(spec: dict, base: Path, ref: str) -> Path:
    sources = spec.get("sources", {})
    if ref in sources:
        entry = sources[ref]
        ref = entry["path"] if isinstance(entry, dict) else entry
    return resolve_path(base, ref)


def resolve_sfx(base: Path, name: str) -> Path:
    if name.endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac")):
        return resolve_path(base, name)
    p = SFX_DIR / f"{name}.wav"
    if not p.exists():
        avail = ", ".join(sorted(x.stem for x in SFX_DIR.glob("*.wav"))) or "none (run scripts/setup.sh)"
        raise VeditError(f"unknown sfx {name!r}. Available: {avail}")
    return p


# ----------------------------------------------------------------------------
# Transitions
# ----------------------------------------------------------------------------

def legacy_keys(item: dict) -> dict:
    """Specs written for the old Playwright renderer: `html` (a vedit page), `scene` / `template` (now built-ins)
    and `params` map onto `hyperframes` and `variables`."""
    ref = item.get("html") or item.get("scene") or item.get("template")
    if not ref or "hyperframes" in item or "source" in item:
        return item
    out = {k: v for k, v in item.items() if k not in ("html", "scene", "template", "params")}
    out["hyperframes"] = ref
    if "params" in item and "variables" not in item:
        out["variables"] = item["params"]
    return out


def resolve_transition(raw, fps: float) -> Transition:
    if raw is None:
        return Transition()
    if isinstance(raw, str):
        raw = {"type": raw}
    raw = dict(raw)
    if raw.get("type") == "mograph":            # old renderer: a template or vedit page covering the cut
        raw = {**legacy_keys(raw), "type": "hyperframes"}
    name = raw.get("type", "cut")
    base: dict
    if name in TRANSITION_PRESETS:
        base = dict(TRANSITION_PRESETS[name])
    elif name in xfade_names():
        base = {"kind": "xfade", "xfade": name, "duration": 0.6}
    elif name == "hyperframes":
        project = raw.get("project") or raw.get("hyperframes")
        if not project:
            raise VeditError("hyperframes transition needs 'project' (a HyperFrames project, vedit page or built-in)")
        base = {"kind": "cut", "overlay": {"hyperframes": project,
                                           **{k: raw[k] for k in ("variables", "blend", "cover_at", "duration", "opacity")
                                              if k in raw}}}
    else:
        raise VeditError(f"unknown transition {name!r}. Use a preset ({', '.join(TRANSITION_PRESETS)}), "
                         f"an ffmpeg xfade name, or 'hyperframes'.")
    t = Transition(kind=base["kind"], name=name, xfade=base.get("xfade"))
    t.duration = float(raw.get("duration", base.get("duration", 0.0)))
    if t.kind == "xfade":
        t.overlap_frames = max(1, round(t.duration * fps))
        t.duration = t.overlap_frames / fps
    sfx = raw.get("sfx", base.get("sfx"))
    t.sfx = None if sfx in (None, False, "none") else sfx
    t.sfx_volume = float(raw.get("sfx_volume", 0.8))
    if "effect" in base or "effect" in raw:
        t.effect = {**base.get("effect", {}), **(raw.get("effect") or {})}
    if "overlay" in base or "overlay" in raw:
        ov = {**base.get("overlay", {}), **(raw.get("overlay") or {})}
        if name in ("light_leak", "film_burn") and "variables" in raw:
            ov["variables"] = raw["variables"]
        t.overlay = ov
    t.punch = float(raw.get("punch", base.get("punch", 0.0)))
    t.punch_duration = float(raw.get("punch_duration", base.get("punch_duration", 0.35)))
    return t


# ----------------------------------------------------------------------------
# Story arc
# ----------------------------------------------------------------------------

def _ease(mode: str, x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    if mode == "linear":
        return x
    if mode == "hold":
        return 0.0
    if mode == "snap":
        return 1.0 if x > 0 else 0.0
    return x * x * (3 - 2 * x)  # smooth


def build_arc(spec: dict, total: float, clips: list | None = None) -> list[dict]:
    story = spec.get("story", {}) or {}
    raw_arc = story.get("arc") or []
    if not raw_arc and story.get("tone"):
        raw_arc = [{"at": 0, "tone": story["tone"], "intensity": story.get("intensity", 1.0)}]
    base_overrides = story.get("look", {}) or {}
    base_overrides = {k: v for k, v in base_overrides.items() if k in G.NEUTRAL}
    arc = []
    for kf in raw_arc:
        kf = dict(kf)
        if kf.get("at_clip") is not None and clips:
            ref = kf["at_clip"]
            match = [c for c in clips if c.id == ref] if not isinstance(ref, int) else [clips[ref]]
            if not match:
                raise VeditError(f"story.arc: no clip with id {ref!r}")
            c = match[0]
            t = (c.end if kf.get("anchor") == "end" else c.start) + parse_time(kf.get("offset", 0.0))
        else:
            t = parse_time(kf.get("at", 0), total)
        overrides = {**base_overrides, **(kf.get("overrides") or {})}
        overrides.update({k: v for k, v in kf.items() if k in G.NEUTRAL})
        params = G.look(kf.get("tone") or story.get("tone"), float(kf.get("intensity", 1.0)), overrides)
        arc.append({"t": t, "params": params, "label": kf.get("label", ""), "tone": kf.get("tone"),
                    "ease": kf.get("ease", "smooth"), "intensity": kf.get("intensity", 1.0)})
    arc.sort(key=lambda k: k["t"])
    if not arc:
        arc = [{"t": 0.0, "params": G.look(None, 1.0, base_overrides), "label": "", "tone": None,
                "ease": "smooth", "intensity": 1.0}]
    return arc


def arc_grade(arc: list[dict], t: float) -> dict:
    if t <= arc[0]["t"]:
        return arc[0]["params"]
    for a, b in zip(arc, arc[1:]):
        if a["t"] <= t <= b["t"]:
            span = b["t"] - a["t"]
            x = 1.0 if span <= 0 else (t - a["t"]) / span
            return G.lerp_params(a["params"], b["params"], _ease(b.get("ease", "smooth"), x))
    return arc[-1]["params"]


def arc_label(arc: list[dict], t: float) -> str:
    label = arc[0]["label"]
    for kf in arc:
        if kf["t"] <= t + 1e-6:
            label = kf["label"] or label
    return label


# ----------------------------------------------------------------------------
# Resolution
# ----------------------------------------------------------------------------

def _motion(raw) -> dict | None:
    if not raw:
        return None
    if isinstance(raw, str):
        raw = {"type": raw}
    return dict(raw)


def build_plan(spec_or_path, base_dir: Path | None = None) -> Plan:
    if isinstance(spec_or_path, (str, Path)):
        spec, base_dir = load_spec(spec_or_path)
    else:
        spec = spec_or_path
        base_dir = base_dir or Path.cwd()
    output = {**DEFAULT_OUTPUT, **(spec.get("output") or {})}
    fps = float(output["fps"])
    for k in ("width", "height"):
        output[k] = int(output[k]) // 2 * 2
    raw_clips = spec.get("timeline") or []
    if not raw_clips:
        raise VeditError("spec has an empty 'timeline'")

    clips: list[Clip] = []
    for i, rc in enumerate(raw_clips):
        if not isinstance(rc, dict):
            raise VeditError(f"timeline[{i}] must be an object")
        rc = legacy_keys(rc)
        cid = str(rc.get("id", f"c{i + 1}"))
        speed = float(rc.get("speed", 1.0))
        if speed <= 0:
            raise VeditError(f"clip {cid}: speed must be > 0")
        if "color" in rc and "source" not in rc:
            kind, path, info = "color", None, None
            src_in = 0.0
        elif "hyperframes" in rc and "source" not in rc:
            # a full-screen HyperFrames composition (or vedit page) used as a clip
            from . import hyperframes as HF
            kind, info = "scene", None
            path = HF.resolve(rc["hyperframes"], base_dir)
            src_in = 0.0
            if "duration" not in rc and "out" not in rc:
                rc = {**rc, "duration": HF.meta(path)["duration"]}
        else:
            if "source" not in rc:
                raise VeditError(f"clip {cid}: needs 'source' (or 'color' for a solid slug)")
            path = resolve_source(spec, base_dir, rc["source"])
            if not path.exists():
                raise VeditError(f"clip {cid}: source not found: {path}")
            info = probe(path)
            kind = "image" if info["is_image"] else "video"
            src_in = parse_time(rc.get("in", 0.0))
        if "out" in rc:
            span = parse_time(rc["out"]) - src_in
        elif "duration" in rc:
            span = parse_time(rc["duration"]) * speed
        elif kind == "video":
            span = info["duration"] - src_in
        else:
            span = 3.0 * speed
        if span <= 0:
            raise VeditError(f"clip {cid}: out must be after in (in={src_in}, span={span:.3f})")
        src_duration = info["duration"] if kind == "video" else math.inf
        if kind == "video" and src_in >= src_duration:
            raise VeditError(f"clip {cid}: in={src_in} is past the end of the source ({src_duration:.2f}s)")
        if kind == "video" and src_in + span > src_duration + 0.05:
            span = src_duration - src_in
        frames = max(1, round(span / speed * fps))
        clip = Clip(
            index=i, id=cid, kind=kind, path=path, color=rc.get("color"), src_in=src_in,
            speed=speed, frames=frames, fps=fps,
            volume=0.0 if rc.get("mute") else float(rc.get("volume", 1.0)),
            has_audio=bool(info and info.get("has_audio")) and kind == "video",
            fit=rc.get("fit", "cover"), crop=rc.get("crop"), motion=_motion(rc.get("motion")),
            transition=resolve_transition(rc.get("transition"), fps) if i > 0 else Transition(),
            grade_spec=rc.get("grade"), src_duration=src_duration, label=rc.get("label", ""), raw=rc,
        )
        clips.append(clip)

    beats = _load_beats(spec, base_dir)
    _layout(clips)
    if beats:
        _snap_to_beats(clips, beats, spec.get("sync", {}), fps)
        _layout(clips)

    for c in clips:
        if c.kind == "video" and c.src_in + c.src_span > c.src_duration + 1.5 / fps:
            raise VeditError(f"clip {c.id}: needs {c.src_span:.2f}s of source from {c.src_in:.2f}s "
                             f"but the source is only {c.src_duration:.2f}s long")
        t = c.transition
        if t.kind == "xfade":
            prev = clips[c.index - 1]
            if t.overlap_frames >= min(prev.frames, c.frames):
                raise VeditError(f"clip {c.id}: transition '{t.name}' ({t.duration:.2f}s) is longer "
                                 f"than the clips it joins")

    total_frames = clips[-1].start_frame + clips[-1].frames
    total = total_frames / fps
    arc = build_arc(spec, total, clips)
    for c in clips:
        if c.transition.kind == "xfade":
            c.transition.boundary = c.start + c.transition.duration / 2
        else:
            c.transition.boundary = c.start
        if c.kind == "scene" and c.grade_spec is None and not c.raw.get("graded"):
            # designed scenes keep their exact colours unless asked to follow the story grade
            c.grade_start = c.grade_end = G.look()
        elif c.grade_spec is not None and not (isinstance(c.grade_spec, dict)
                                               and set(c.grade_spec) <= {"overrides"}):
            g = G.resolve(c.grade_spec)
            c.grade_start = c.grade_end = g
        else:
            c.grade_start = arc_grade(arc, c.start)
            c.grade_end = arc_grade(arc, c.end)
            if isinstance(c.grade_spec, dict):
                ov = c.grade_spec.get("overrides", {})
                norm = G.normalize(ov)
                c.grade_start = {**c.grade_start, **{k: norm[k] for k in ov}}
                c.grade_end = {**c.grade_end, **{k: norm[k] for k in ov}}
    return Plan(spec=spec, base_dir=base_dir, output=output, clips=clips,
                total_frames=total_frames, arc=arc, beats=beats)


def _layout(clips: list[Clip]) -> None:
    pos = 0
    for c in clips:
        c.start_frame = pos - c.transition.overlap_frames if c.index > 0 else 0
        pos = c.start_frame + c.frames


def _load_beats(spec: dict, base: Path) -> list[float] | None:
    sync = spec.get("sync") or {}
    src = sync.get("beats")
    if not src:
        return None
    if isinstance(src, list):
        return sorted(float(b) for b in src)
    data = json.loads(resolve_path(base, src).read_text())
    key = "downbeats" if sync.get("to") == "downbeats" else "beats"
    beats = data.get(key) or data.get("beats") or []
    offset = float(sync.get("offset", 0.0))
    return sorted(float(b) + offset for b in beats)


def _snap_to_beats(clips: list[Clip], beats: list[float], sync: dict, fps: float) -> None:
    """Move each cut onto a beat. Clips with "beats": N last exactly N beats."""
    if len(beats) < 2:
        return
    period = (beats[-1] - beats[0]) / (len(beats) - 1)
    max_shift = float(sync.get("max_shift", 0.75 * period))
    every = max(1, int(sync.get("every", 1)))
    grid = beats[::every]
    first = 0
    if sync.get("from_clip") is not None:
        ids = [c.id for c in clips]
        if sync["from_clip"] not in ids:
            raise VeditError(f"sync.from_clip: no clip with id {sync['from_clip']!r}")
        first = ids.index(sync["from_clip"])
    for i, c in enumerate(clips[:-1]):
        if i < first:
            continue
        nxt = clips[i + 1]
        half = nxt.transition.overlap_frames / 2
        natural = c.start + (c.frames - half) / fps
        if "beats" in c.raw:
            first = min(range(len(beats)), key=lambda k: abs(beats[k] - c.start))
            idx = min(first + int(c.raw["beats"]), len(beats) - 1)
            candidates = [beats[idx]]
        elif sync.get("snap", True) is False or c.raw.get("snap") is False:
            continue
        else:
            candidates = sorted(grid, key=lambda b: abs(b - natural))[:4]
            candidates = [b for b in candidates if abs(b - natural) <= max_shift]
        for target in candidates:
            frames = round((target - c.start) * fps + half)
            if frames < max(3, nxt.transition.overlap_frames + 1):
                continue
            if c.kind == "video" and c.src_in + frames / fps * c.speed > c.src_duration + 0.5 / fps:
                continue
            c.frames = frames
            break
        _layout(clips)


def snap_info(plan: Plan) -> list[dict]:
    """A compact, human-readable description of the plan (used by `vedit plan`)."""
    rows = []
    for c in plan.clips:
        rows.append({
            "id": c.id, "kind": c.kind,
            "source": str(c.path.name) if c.path else c.color,
            "src_in": round(c.src_in, 3), "src_out": round(c.src_in + c.src_span, 3),
            "start": round(c.start, 3), "end": round(c.end, 3), "duration": round(c.duration, 3),
            "transition_in": c.transition.name if c.index > 0 else None,
            "story": arc_label(plan.arc, c.start + c.duration / 2),
        })
    return rows


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS
