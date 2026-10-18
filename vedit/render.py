"""Render an edit spec: per-clip segments (cut, reframe, motion, grade) in parallel,
then one composite pass (transitions, effects, motion graphics, text, audio mix)."""
from __future__ import annotations

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import grade as G
from . import mograph
from .text import build_ass
from .timeline import Clip, Plan, build_plan, resolve_path, resolve_sfx
from .util import (FONTS_DIR, SFX_DIR, VeditError, ff_escape, ffmpeg, hex_to_rgb, log,
                   parse_time, probe, stable_hash)


@dataclass
class Overlay:
    path: Path
    start: float
    duration: float
    blend: str = "normal"
    opacity: float = 1.0


# ----------------------------------------------------------------------------
# Stage 1: segments
# ----------------------------------------------------------------------------

def _fit_chain(c: Clip, W: int, H: int, lbl: str, inp: str, out: str) -> list[str]:
    pre = ""
    if c.crop:
        x, y, w, h = c.crop
        pre = f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},"
    if c.fit == "contain":
        return [f"[{inp}]{pre}scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[{out}]"]
    if c.fit == "blur_fill":
        return [f"[{inp}]{pre}split[{lbl}a][{lbl}b]",
                f"[{lbl}a]scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,crop={W // 4}:{H // 4},"
                f"gblur=sigma=12,eq=brightness=-0.06:saturation=0.9,scale={W}:{H}[{lbl}bg]",
                f"[{lbl}b]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[{lbl}fg]",
                f"[{lbl}bg][{lbl}fg]overlay=(W-w)/2:(H-h)/2,setsar=1[{out}]"]
    if c.fit != "cover":
        raise VeditError(f"clip {c.id}: unknown fit {c.fit!r} (cover|contain|blur_fill)")
    return [f"[{inp}]{pre}scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={W}:{H},setsar=1[{out}]"]


def _motion_chain(c: Clip, W: int, H: int, inp: str, out: str) -> list[str]:
    m = dict(c.motion or {})
    punch = c.transition.punch
    if not m and not punch:
        return [f"[{inp}]null[{out}]"]
    D = max(c.duration, 1e-3)
    typ = m.get("type", "none")
    a = float(m.get("amount", {"push_in": 0.08, "pull_out": 0.08, "ken_burns": 0.12, "shake": 0.012,
                               "drift": 0.025, "crash_zoom": 0.2}.get(typ, 0.1)))
    u = f"clip(t/{D:.4f},0,1)"
    e = {"linear": u, "in": f"pow({u},2)", "out": f"(1-pow(1-{u},2))"}.get(m.get("ease", "smooth"),
                                                                       f"({u}*{u}*(3-2*{u}))")
    z, px, py = "1", "0", "0"
    if typ == "push_in":
        z = f"(1+{a}*{e})"
    elif typ == "pull_out":
        z = f"(1+{a}*(1-{e}))"
    elif typ in ("pan_left", "pan_right", "pan_up", "pan_down"):
        z = f"(1+{a})"
        s = f"(2*{e}-1)"
        px = {"pan_left": f"(-{s})", "pan_right": s}.get(typ, "0")
        py = {"pan_up": f"(-{s})", "pan_down": s}.get(typ, "0")
    elif typ == "ken_burns":
        fx, fy = m.get("from", [0.5, 0.5])
        tx, ty = m.get("to", [0.5, 0.5])
        z = f"(1+{a}*{e})" if m.get("zoom", "in") == "in" else f"(1+{a}*(1-{e}))"
        px = f"(({fx * 2 - 1}) + ({(tx - fx) * 2})*{e})"
        py = f"(({fy * 2 - 1}) + ({(ty - fy) * 2})*{e})"
    elif typ == "crash_zoom":
        # fast in-camera style zoom into a subject, then hold (Kill Bill / Tarantino crash zoom)
        at = float(m.get("at", 0.0))
        dur = max(float(m.get("duration", 0.22)), 1.0 / 30)
        p = f"(1-pow(1-clip((t-{at})/{dur},0,1),3))"
        z = f"(1+{a}*{p})"
        fx, fy = m.get("focus", [0.5, 0.45])
        px, py = f"({fx * 2 - 1})", f"({fy * 2 - 1})"
    elif typ in ("shake", "drift"):
        f = float(m.get("frequency", 1.0 if typ == "shake" else 0.15))
        z = f"(1+{a * 2.2})"
        px = f"(0.55*sin(t*{7.3 * f})+0.3*sin(t*{13.1 * f}+1.3)+0.15*sin(t*{23.7 * f}+0.4))"
        py = f"(0.5*sin(t*{6.1 * f}+2.1)+0.35*sin(t*{11.7 * f}+0.7)+0.15*sin(t*{19.3 * f}+2.9))"
    elif typ not in ("none", ""):
        raise VeditError(f"clip {c.id}: unknown motion {typ!r}")
    if punch:
        pd = max(c.transition.punch_duration, 0.05)
        z = f"({z}*(1+{punch}*pow(1-clip(t/{pd},0,1),3)))"
    sw = f"ceil({W}*{z}/2)*2"
    sh = f"ceil({H}*{z}/2)*2"
    return [f"[{inp}]scale=w='{sw}':h='{sh}':eval=frame:flags=bicubic,"
            f"crop={W}:{H}:x='(iw-{W})/2*(1+clip({px},-1,1))':y='(ih-{H})/2*(1+clip({py},-1,1))'[{out}]"]


def _segment_args(plan: Plan, c: Clip, work: Path, W: int, H: int, quality: dict) -> list:
    fps = plan.fps
    pad = 3 / fps
    if c.kind == "video":
        inp = ["-ss", f"{c.src_in:.4f}", "-t", f"{c.src_span + pad:.4f}", "-i", c.path]
    elif c.kind == "image":
        inp = ["-loop", "1", "-framerate", f"{fps}", "-t", f"{c.duration + pad:.4f}", "-i", c.path]
    else:
        r, g, b = (round(v * 255) for v in hex_to_rgb(c.color or "#000000"))
        inp = ["-f", "lavfi", "-i", f"color=c=0x{r:02x}{g:02x}{b:02x}:s={W}x{H}:r={fps}:d={c.duration + pad:.4f}"]
    L = f"k{c.index}"
    speed = "" if c.speed == 1 else f"/{c.speed}"
    steps = [f"[0:v]setpts=(PTS-STARTPTS){speed},fps={fps},format=yuv420p[{L}in]"]
    steps += _fit_chain(c, W, H, L, f"{L}in", f"{L}fit")
    steps += _motion_chain(c, W, H, f"{L}fit", f"{L}mot")
    steps += G.grade_chain(c.grade_start, c.grade_end, c.duration, fps, work / "luts", W, H, L,
                           f"{L}mot", f"{L}gr")
    steps.append(f"[{L}gr]setsar=1,tpad=stop_mode=clone:stop_duration={pad:.3f}[vout]")
    return [*inp, "-filter_complex", ";".join(steps), "-map", "[vout]", "-frames:v", c.frames, "-an",
            "-c:v", "libx264", "-preset", quality["seg_preset"], "-crf", quality["seg_crf"],
            "-pix_fmt", "yuv420p", "-r", fps]


def _atempo(speed: float) -> str:
    parts = []
    s = speed
    while s > 2.0:
        parts.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5")
        s /= 0.5
    parts.append(f"atempo={s:.5f}")
    return ",".join(parts)


def render_segment(plan: Plan, c: Clip, work: Path, W: int, H: int, quality: dict) -> tuple[Path, Path | None]:
    seg_dir = work / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    args = _segment_args(plan, c, work, W, H, quality)
    key = stable_hash([str(a) for a in args], c.path if c.path else "")
    vpath = seg_dir / f"{c.index:03d}_{c.id}_{key}.mp4"
    if not vpath.exists():
        log(f"segment {c.id}: {c.kind} {c.duration:.2f}s")
        tmp = vpath.with_suffix(".tmp.mp4")
        ffmpeg([*args, tmp])
        tmp.rename(vpath)
    apath = None
    if c.has_audio and c.volume > 0:
        akey = stable_hash(c.path, c.src_in, c.src_span, c.speed, c.volume, c.frames, plan.fps)
        apath = seg_dir / f"{c.index:03d}_{c.id}_{akey}.wav"
        if not apath.exists():
            af = []
            if c.speed != 1:
                af.append(_atempo(c.speed))
            af += ["aresample=48000", f"volume={c.volume}", "apad", f"atrim=0:{c.duration:.4f}"]
            tmp = apath.with_suffix(".tmp.wav")
            ffmpeg(["-ss", f"{c.src_in:.4f}", "-t", f"{c.src_span + 0.1:.4f}", "-i", c.path, "-vn",
                    "-af", ",".join(af), "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", tmp])
            tmp.rename(apath)
    return vpath, apath


# ----------------------------------------------------------------------------
# Stage 2: graphics
# ----------------------------------------------------------------------------

def collect_overlays(plan: Plan, work: Path, W: int, H: int, pool: ThreadPoolExecutor) -> list[Overlay]:
    jobs = []
    fps = plan.fps
    for c in plan.clips:
        ov = c.transition.overlay if c.index > 0 else None
        if not ov:
            continue
        path, meta = mograph.resolve(ov, plan.base_dir)
        dur = float(ov.get("duration", meta.get("duration", 1.0)))
        meta_dur = float(meta.get("duration", dur)) or dur
        cover = float(ov.get("cover_at", meta.get("cover_at", meta_dur / 2) * dur / meta_dur))
        start = c.transition.boundary - cover
        jobs.append((path, ov.get("params", {}), start, dur, ov.get("blend", meta.get("blend", "normal")),
                     float(ov.get("opacity", 1.0))))
    for g in plan.spec.get("graphics") or []:
        path, meta = mograph.resolve(g, plan.base_dir)
        dflt = float(g.get("duration", meta.get("duration", 3.0)))
        start, end = plan.resolve_span({**g, "duration": g.get("duration", dflt)}, dflt)
        jobs.append((path, g.get("params", {}), start, end - start, g.get("blend", meta.get("blend", "normal")),
                     float(g.get("opacity", 1.0))))
    futures = []
    submitted: dict = {}  # identical graphics (same file, params, length) render once
    for path, params, start, dur, blend, opacity in jobs:
        if dur <= 0:
            continue
        key = (str(path), json.dumps(params, sort_keys=True), round(dur, 4))
        if key not in submitted:
            submitted[key] = pool.submit(mograph.render, path, work / "graphics", width=W, height=H, fps=fps,
                                         duration=dur, params=params)
        futures.append((submitted[key], start, dur, blend, opacity))
    return [Overlay(f.result(), s, d, b, o) for f, s, d, b, o in futures]


# ----------------------------------------------------------------------------
# Stage 3: composite
# ----------------------------------------------------------------------------

def _effect_filters(eff: dict, W: int, H: int, idx: int, cur: str) -> tuple[list[str], str]:
    typ = eff["type"]
    s, d = eff["start"], eff["duration"]
    k = float(eff.get("intensity", 1.0))
    en = f"enable='between(t,{s:.4f},{s + d:.4f})'"
    L = f"e{idx}"
    st: list[str] = []
    if typ == "glitch":
        a = max(2, round(W * 0.012 * k))
        st.append(f"[{cur}]rgbashift=rh=-{a}:bh={a}:rv={a // 2}:{en},"
                  f"rgbashift=rh={a * 2}:gh=-{a}:enable='between(t,{s + d * 0.3:.4f},{s + d * 0.55:.4f})',"
                  f"noise=alls={round(25 * k)}:allf=t:{en},split[{L}a][{L}b]")
        st.append(f"[{L}b]crop=iw:ih*0.14:0:ih*0.38[{L}s]")
        st.append(f"[{L}a][{L}s]overlay=x={round(W * 0.035 * k)}:y={round(H * 0.38)}:"
                  f"enable='between(t,{s + d * 0.15:.4f},{s + d * 0.7:.4f})'[{L}o]")
        return st, f"{L}o"
    if typ == "flash":
        c = s + d / 2
        st.append(f"[{cur}]eq=brightness='{0.75 * k}*max(0,1-abs(t-{c:.4f})/{d / 2:.4f})':eval=frame:{en}[{L}o]")
        return st, f"{L}o"
    if typ == "rgb_split":
        a = max(2, round(W * 0.008 * k))
        st.append(f"[{cur}]rgbashift=rh=-{a}:bh={a}:{en}[{L}o]")
        return st, f"{L}o"
    if typ == "blur":
        st.append(f"[{cur}]gblur=sigma={8 * k:.1f}:{en}[{L}o]")
        return st, f"{L}o"
    if typ == "mono":
        st.append(f"[{cur}]hue=s=0:{en}[{L}o]")
        return st, f"{L}o"
    if typ == "invert":
        st.append(f"[{cur}]negate={en}[{L}o]")
        return st, f"{L}o"
    if typ == "dim":
        st.append(f"[{cur}]eq=brightness={-0.25 * k}:{en}[{L}o]")
        return st, f"{L}o"
    raise VeditError(f"unknown effect {typ!r} (glitch|flash|rgb_split|blur|mono|invert|dim)")


def _effects(plan: Plan) -> list[dict]:
    effs = []
    for c in plan.clips[1:]:
        e = c.transition.effect
        if e:
            d = float(e.get("duration", 0.3))
            effs.append({**e, "start": c.transition.boundary - d / 2, "duration": d})
    for e in plan.spec.get("effects") or []:
        start, end = plan.resolve_span({**e, "duration": e.get("duration", 0.3)}, 0.3)
        effs.append({**e, "start": start, "duration": end - start})
    return effs


def _sfx_peaks() -> dict:
    meta = SFX_DIR / "sfx.json"
    return json.loads(meta.read_text()) if meta.exists() else {}


def _audio_graph(plan: Plan, seg_audio: list[Path | None], first_input: int, inputs: list,
                 steps: list[str]) -> str:
    """Append audio inputs/filters; returns the output label."""
    total = plan.duration
    fps = plan.fps
    audio_cfg = plan.spec.get("audio") or {}
    idx = first_input
    dlg = []
    for c, ap in zip(plan.clips, seg_audio):
        if not ap:
            continue
        inputs += ["-i", ap]
        fin = c.transition.duration if c.transition.kind == "xfade" else 0.015
        nxt = plan.clips[c.index + 1] if c.index + 1 < len(plan.clips) else None
        fout = nxt.transition.duration if nxt and nxt.transition.kind == "xfade" else 0.015
        ms = round(c.start * 1000)
        steps.append(f"[{idx}:a]afade=t=in:st=0:d={fin:.3f},afade=t=out:st={max(c.duration - fout, 0):.3f}:"
                     f"d={fout:.3f},adelay={ms}:all=1[da{idx}]")
        dlg.append(f"[da{idx}]")
        idx += 1

    duck_bus, free_bus = [], []
    for j, m in enumerate(plan.spec.get("music") or []):
        path = resolve_path(plan.base_dir, m["path"])
        info = probe(path)
        start = plan.resolve_time(m, "start", 0.0)
        src_in = parse_time(m.get("in", 0.0))
        if "duration" in m or "end" in m or "end_at_clip" in m:
            _, end = plan.resolve_span(m)
        else:
            end = total
        dur = max(0.0, min(end, total) - start)
        if dur <= 0:
            continue
        if m.get("loop") or info["duration"] - src_in < dur:
            inputs += ["-stream_loop", "-1"]
        inputs += ["-i", path]
        vol = 10 ** (float(m["gain_db"]) / 20) if "gain_db" in m else float(m.get("volume", 0.8))
        fi, fo = float(m.get("fade_in", 0.5)), float(m.get("fade_out", 2.0))
        extra = f"{m['filter']}," if m.get("filter") else ""
        steps.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start={src_in:.3f},"
                     f"asetpts=PTS-STARTPTS,{extra}atrim=duration={dur:.3f},volume={vol:.4f},afade=t=in:st=0:d={fi:.3f},"
                     f"afade=t=out:st={max(dur - fo, 0):.3f}:d={fo:.3f},adelay={round(start * 1000)}:all=1[mu{idx}]")
        (duck_bus if m.get("duck", True) else free_bus).append(f"[mu{idx}]")
        idx += 1

    sfx_bus = []
    peaks = _sfx_peaks()
    sfx_items = []
    for c in plan.clips[1:]:
        if c.transition.sfx:
            sfx_items.append({"name": c.transition.sfx, "at": c.transition.boundary,
                              "volume": c.transition.sfx_volume})
    for s in plan.spec.get("sfx") or []:
        sfx_items.append({**s, "at": plan.resolve_time(s, "at" if "at" in s else "start", 0.0)})
    for s in sfx_items:
        name = s.get("name") or s.get("path")
        path = resolve_sfx(plan.base_dir, name)
        peak = float(s.get("peak", peaks.get(Path(name).stem, {}).get("peak", 0.0)))
        start = s["at"] - peak
        trim = max(0.0, -start)
        inputs += ["-i", path]
        steps.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start={trim:.3f},"
                     f"asetpts=PTS-STARTPTS,volume={float(s.get('volume', 0.8)):.3f},"
                     f"adelay={round(max(start, 0) * 1000)}:all=1[sx{idx}]")
        sfx_bus.append(f"[sx{idx}]")
        idx += 1

    def mix(labels: list[str], out: str) -> str | None:
        if not labels:
            return None
        if len(labels) == 1:
            steps.append(f"{labels[0]}anull[{out}]")
        else:
            steps.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0[{out}]")
        return f"[{out}]"

    d = mix(dlg, "dlg")
    md = mix(duck_bus, "musd")
    mf = mix(free_bus, "musf")
    sx = mix(sfx_bus, "sfx")
    duck = audio_cfg.get("duck", {}) if isinstance(audio_cfg.get("duck", {}), dict) else {}
    if d and md and audio_cfg.get("duck", True) is not False:
        steps.append(f"{d}asplit=2[dlgm][dlgsc]")
        thr = float(duck.get("threshold", 0.02))
        ratio = float(duck.get("ratio", 6))
        steps.append(f"{md}[dlgsc]sidechaincompress=threshold={thr}:ratio={ratio}:attack="
                     f"{float(duck.get('attack', 20))}:release={float(duck.get('release', 450))}:makeup=1[musdk]")
        d, md = "[dlgm]", "[musdk]"
    buses = [b for b in (d, md, mf, sx) if b]
    if not buses:
        steps.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={total:.4f}[aout]")
        return "[aout]"
    pre = mix(buses, "amaster")
    # No dynamic loudness normalisation here: it would flatten deliberate dynamics (quiet
    # intro, loud climax). The whole mix gets one static gain afterwards (normalize_loudness).
    chain = [f"apad=whole_dur={total:.4f}", f"atrim=duration={total:.4f}",
             "aresample=48000", "alimiter=limit=0.95:level=disabled", f"atrim=duration={total:.4f}"]
    steps.append(f"{pre}{','.join(chain)}[aout]")
    return "[aout]"


def render(spec_path: str | Path, *, preview: bool = False, output: str | Path | None = None,
           jobs: int | None = None) -> Path:
    plan = build_plan(spec_path)
    out_cfg = dict(plan.output)
    W, H = out_cfg["width"], out_cfg["height"]
    if preview:
        W, H = W // 4 * 2, H // 4 * 2
    quality = {"seg_crf": 26 if preview else int(out_cfg.get("intermediate_crf", 12)),
               "seg_preset": "ultrafast" if preview else "veryfast"}
    spec_stem = Path(spec_path).stem
    work = plan.base_dir / "work" / spec_stem / ("preview" if preview else "full")
    work.mkdir(parents=True, exist_ok=True)
    if output:
        out_path = Path(output)
    else:
        out_path = resolve_path(plan.base_dir, out_cfg["path"])
        if preview:
            out_path = out_path.with_name(out_path.stem + "_preview" + out_path.suffix)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    jobs = jobs or max(1, (os.cpu_count() or 2) // 2)
    log(f"plan: {len(plan.clips)} clips, {plan.duration:.2f}s @ {W}x{H} {plan.fps}fps"
        f"{' (preview)' if preview else ''}")

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        seg_futures = [pool.submit(render_segment, plan, c, work, W, H, quality) for c in plan.clips]
        overlays = collect_overlays(plan, work, W, H, pool)
        segs = [f.result() for f in seg_futures]

    inputs: list = []
    steps: list[str] = []
    fps = plan.fps
    for i, (vp, _) in enumerate(segs):
        inputs += ["-i", vp]
        steps.append(f"[{i}:v]setpts=PTS-STARTPTS,fps={fps},settb=AVTB,setsar=1[s{i}]")
    cur = "s0"
    for c in plan.clips[1:]:
        i = c.index
        t = c.transition
        o = f"j{i}"
        if t.kind == "xfade":
            steps.append(f"[{cur}][s{i}]xfade=transition={t.xfade}:duration={t.duration:.4f}:"
                         f"offset={c.start:.4f}[{o}]")
        else:
            steps.append(f"[{cur}][s{i}]concat=n=2:v=1:a=0[{o}]")
        cur = o

    for k, eff in enumerate(_effects(plan)):
        st, cur = _effect_filters(eff, W, H, k, cur)
        steps += st

    n_in = len(segs)
    total = plan.duration
    for k, ov in enumerate(overlays):
        inputs += ["-i", ov.path]
        o = f"ov{k}"
        if ov.blend == "screen":
            pre = max(ov.start, 0.0)
            trim = max(-ov.start, 0.0)
            post = max(total - pre - ov.duration + trim, 0.0) + 0.5
            op = f":all_opacity={ov.opacity:.3f}" if ov.opacity < 1 else ""
            steps.append(f"[{n_in}:v]format=gbrp,trim=start={trim:.4f},setpts=PTS-STARTPTS,"
                         f"tpad=start_duration={pre:.4f}:stop_duration={post:.4f}:color=black,fps={fps}[ol{k}]")
            steps.append(f"[{cur}]format=gbrp[ob{k}]")
            steps.append(f"[ob{k}][ol{k}]blend=all_mode=screen{op}:shortest=1,format=yuv420p[{o}]")
        else:
            fade = f",colorchannelmixer=aa={ov.opacity:.3f}" if ov.opacity < 1 else ""
            trim = f"trim=start={-ov.start:.4f}," if ov.start < 0 else ""
            steps.append(f"[{n_in}:v]{trim}format=yuva420p{fade},"
                         f"setpts=PTS-STARTPTS+{max(ov.start, 0.0):.4f}/TB[ol{k}]")
            steps.append(f"[{cur}][ol{k}]overlay=eof_action=pass:format=auto[{o}]")
        cur = o
        n_in += 1

    look = (plan.spec.get("story") or {}).get("look") or {}
    lb = look.get("letterbox") or out_cfg.get("letterbox")
    if lb:
        bar = max(0, round((H - W / float(lb)) / 2))
        if bar > 0:
            steps.append(f"[{cur}]drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,"
                         f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill[lbx]")
            cur = "lbx"

    ass = build_ass(plan, work / "text.ass")
    if ass:
        fonts = f":fontsdir='{ff_escape(FONTS_DIR)}'" if FONTS_DIR.is_dir() else ""
        steps.append(f"[{cur}]ass=filename='{ff_escape(ass)}'{fonts}[txt]")
        cur = "txt"
    steps.append(f"[{cur}]format=yuv420p,trim=end_frame={plan.total_frames}[vout]")

    aout = _audio_graph(plan, [a for _, a in segs], n_in, inputs, steps)

    graph = work / "composite.ffgraph"
    graph.write_text(";\n".join(steps))
    codec = out_cfg.get("codec", "libx264")
    venc = ["-c:v", codec, "-pix_fmt", "yuv420p"]
    if codec in ("libx264", "libx265"):
        venc += ["-preset", "ultrafast" if preview else out_cfg.get("preset", "medium"),
                 "-crf", str(28 if preview else out_cfg.get("crf", 18))]
        if codec == "libx265":
            venc += ["-tag:v", "hvc1"]
    elif codec == "prores_ks":
        venc = ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
    log(f"compositing {total:.2f}s -> {out_path}")
    ffmpeg([*inputs, "-filter_complex_script", graph, "-map", "[vout]", "-map", aout,
            *venc, "-r", fps, "-c:a", "aac", "-b:a", out_cfg.get("audio_bitrate", "256k"),
            "-ar", "48000", "-movflags", "+faststart", "-frames:v", plan.total_frames, out_path])
    lufs = (plan.spec.get("audio") or {}).get("loudness", -14)
    if lufs is not None:
        normalize_loudness(out_path, float(lufs), out_cfg.get("audio_bitrate", "256k"))
    log(f"done: {out_path}")
    return out_path


def measure_loudness(path: Path) -> float | None:
    import re
    import subprocess
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-vn",
                           "-af", "ebur128=framelog=quiet", "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", proc.stderr)
    return float(m[-1]) if m else None


def normalize_loudness(path: Path, target: float, bitrate: str) -> None:
    """Bring the whole mix to `target` LUFS with one static gain (keeps the edit's dynamics)."""
    measured = measure_loudness(path)
    if measured is None or measured < -70 or abs(measured - target) < 0.5:
        return
    gain = target - measured
    tmp = path.with_name(path.stem + ".loud" + path.suffix)
    ffmpeg(["-i", path, "-map", "0", "-c:v", "copy", "-af",
            f"volume={gain:.2f}dB,alimiter=limit=0.89:attack=3:release=60:level=disabled",
            "-c:a", "aac", "-b:a", bitrate, "-movflags", "+faststart", tmp])
    tmp.replace(path)
    log(f"loudness {measured:.1f} -> {target:.1f} LUFS (static gain {gain:+.1f} dB)")
