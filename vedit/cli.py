"""vedit command line. Run `bin/vedit <command> --help` for details."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import grade as G
from .tones import TONES, find_tones_for_mood
from .util import FONTS_DIR, SFX_DIR, VeditError, ffmpeg, fmt_time, installed_font_families, log, probe


def _json(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


# ----------------------------------------------------------------------------

def cmd_doctor(a) -> int:
    from .hyperframes import available
    from .timeline import xfade_names

    ok = True

    def row(name: str, good: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= good or name.startswith("(optional)")
        print(f"  {'✔' if good else '✘'} {name}{(': ' + detail) if detail else ''}")

    print("vedit doctor")
    ff = shutil.which("ffmpeg")
    row("ffmpeg", bool(ff), ff or "missing")
    if ff:
        filters = subprocess.run([ff, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        for f in ("xfade", "lut3d", "ass", "drawtext", "sidechaincompress", "loudnorm", "blend", "rgbashift"):
            row(f"ffmpeg filter {f}", f" {f} " in filters)
        row("ffmpeg xfade transitions", bool(xfade_names()), f"{len(xfade_names())} available")
    hf, why = available()
    row("HyperFrames (scenes, overlays, designed transitions)", hf, why)
    fams = installed_font_families()
    have = [f for f in ("Bebas Neue", "Anton", "Montserrat", "Playfair Display", "Space Grotesk") if f in fams]
    row("display fonts", bool(have), ", ".join(have) or f"none (run scripts/setup.sh); fonts dir {FONTS_DIR}")
    sfx = sorted(p.stem for p in SFX_DIR.glob("*.wav"))
    row("sound effects", bool(sfx), ", ".join(sfx) or "none (bin/vedit synth-sfx)")
    try:
        import faster_whisper  # noqa: F401
        row("(optional) faster-whisper transcription", True)
    except ImportError:
        row("(optional) faster-whisper transcription", False, "scripts/setup.sh --with-whisper")
    print("ready" if ok else "some required pieces are missing: run scripts/setup.sh")
    return 0 if ok else 1


def cmd_probe(a) -> int:
    _json([probe(f) for f in a.files])
    return 0


def cmd_analyze(a) -> int:
    from .analyze import analyze, summarize

    for f in a.files:
        out = Path(a.out) if a.out else Path(f).resolve().parent.parent / "work" / "analysis"
        rep = analyze(f, out, sheet=not a.no_sheet, scene_threshold=a.threshold)
        print(summarize(rep))
        print(f"  report: {out / (Path(f).stem + '.analysis.json')}")
    return 0


def cmd_frames(a) -> int:
    from .analyze import contact_sheet, frames_at

    out = Path(a.out)
    if a.times:
        times = [float(t) for t in a.times.split(",")]
        for f in frames_at(a.file, times, out, width=a.width):
            print(f)
    else:
        for f in contact_sheet(a.file, out / (Path(a.file).stem + "_sheet.jpg"), interval=a.every, width=a.width // 3):
            print(f)
    return 0


def cmd_transcribe(a) -> int:
    from .transcribe import as_text, transcribe

    for f in a.files:
        out = Path(a.out) if a.out else Path(f).resolve().parent.parent / "work" / f"{Path(f).stem}.transcript.json"
        data = transcribe(f, out, model=a.model, language=a.language)
        print(as_text(data))
        print(f"transcript: {out}")
    return 0


def cmd_beats(a) -> int:
    from .beats import analyze_music, save

    rep = analyze_music(a.file)
    out = Path(a.out) if a.out else Path(a.file).with_suffix(".beats.json")
    save(rep, out)
    print(f"tempo {rep['tempo']} bpm (beat every {rep['beat_period']}s), {len(rep['beats'])} beats, "
          f"{len(rep['downbeats'])} downbeats; energy rises at {rep['energy_rises']}")
    print(f"first beats: {rep['beats'][:12]}")
    print(f"beats file: {out}")
    return 0


def cmd_tones(a) -> int:
    names = find_tones_for_mood(a.mood) if a.mood else list(TONES)
    for n in names:
        t = TONES[n]
        print(f"{n:18s} {t['description']}\n{'':18s} moods: {', '.join(t['moods'])}")
    if a.mood and not names:
        print(f"no tone lists the mood {a.mood!r}; pick the closest description above")
    return 0


def _grade_still(src: Path, params: dict, out: Path, work: Path, width: int = 640) -> Path:
    h = round(width * 9 / 16) // 2 * 2
    steps = [f"[0:v]scale={width}:{h}:force_original_aspect_ratio=increase,crop={width}:{h},format=yuv420p[in]"]
    steps += G.grade_chain(params, params, 1.0, 30, work, width, h, "s", "in", "out")
    ffmpeg(["-i", src, "-filter_complex", ";".join(steps), "-map", "[out]", "-frames:v", "1", out])
    return out


def _label_grid(tiles: list[tuple[Path, str]], out: Path, cols: int = 3) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    imgs = [(Image.open(p).convert("RGB"), label) for p, label in tiles]
    w, h = imgs[0][0].size
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * (h + 30)), (20, 20, 20))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for i, (im, label) in enumerate(imgs):
        x, y = (i % cols) * w, (i // cols) * (h + 30)
        sheet.paste(im, (x, y))
        ImageDraw.Draw(sheet).text((x + 8, y + h + 6), label, fill=(235, 235, 235), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=90)
    return out


def _still_from(path: Path, t: float, out: Path) -> Path:
    if probe(path)["is_image"]:
        ffmpeg(["-i", path, "-frames:v", "1", out])
    else:
        ffmpeg(["-ss", f"{max(t, 0):.3f}", "-i", path, "-frames:v", "1", out])
    return out


def cmd_look(a) -> int:
    """Compare tones on one frame of real footage."""
    work = Path(a.out).parent / ".look"
    work.mkdir(parents=True, exist_ok=True)
    frame = _still_from(Path(a.file), a.at, work / "frame.png")
    names = a.tones.split(",") if a.tones else list(TONES)
    tiles = []
    for n in names:
        params = G.look(None if n == "original" else n, a.intensity)
        tiles.append((_grade_still(frame, params, work / f"{n}.png", work), n))
    print(_label_grid(tiles, Path(a.out)))
    return 0


def cmd_lut(a) -> int:
    params = G.look(a.tone, a.intensity, json.loads(a.overrides) if a.overrides else None)
    print(G.write_cube(params, Path(a.out), size=a.size))
    return 0


def cmd_plan(a) -> int:
    from .timeline import arc_label, build_plan, snap_info

    plan = build_plan(a.spec)
    print(f"{len(plan.clips)} clips, {fmt_time(plan.duration)} ({plan.total_frames} frames @ {plan.fps}fps), "
          f"{plan.output['width']}x{plan.output['height']}")
    print("story arc:")
    for kf in plan.arc:
        print(f"  {fmt_time(kf['t'])}  {kf['label'] or '-':14s} {kf['tone'] or 'custom'} x{kf['intensity']}")
    print(f"{'id':10s} {'source':22s} {'src in-out':>17s} {'timeline':>17s} {'in-transition':14s} story")
    for r in snap_info(plan):
        print(f"{r['id']:10s} {str(r['source'])[:22]:22s} {r['src_in']:8.2f}-{r['src_out']:<8.2f} "
              f"{r['start']:8.2f}-{r['end']:<8.2f} {str(r['transition_in'] or ''):14s} {r['story']}")
    if a.json:
        _json(snap_info(plan))
    return 0


def cmd_storyboard(a) -> int:
    """One graded still per clip, using the exact grade the render will use."""
    from .timeline import arc_label, build_plan

    plan = build_plan(a.spec)
    work = plan.base_dir / "work" / Path(a.spec).stem / "storyboard"
    work.mkdir(parents=True, exist_ok=True)
    tiles = []
    for c in plan.clips:
        mid = G.lerp_params(c.grade_start, c.grade_end, 0.5)
        if c.kind == "scene":
            from . import hyperframes as HF
            src = HF.snapshot(c.path, [c.duration * 0.6], work / f"{c.id}_scene",
                              variables=c.raw.get("variables") or {}, work=plan.base_dir / "work",
                              size=(plan.output["width"] // 2, plan.output["height"] // 2),
                              base=plan.base_dir)[0]
        elif c.kind == "color":
            from PIL import Image
            from .util import hex_to_rgb
            src = work / f"{c.id}_src.png"
            Image.new("RGB", (640, 360), tuple(round(v * 255) for v in hex_to_rgb(c.color or "#000"))).save(src)
        else:
            src = _still_from(c.path, c.src_in + c.src_span / 2, work / f"{c.id}_src.png")
        g = _grade_still(src, mid, work / f"{c.id}.png", work / "luts")
        label = f"{c.id}  {fmt_time(c.start)}  {arc_label(plan.arc, c.start + c.duration / 2)}"
        tiles.append((g, label))
    out = Path(a.out) if a.out else work / "storyboard.jpg"
    print(_label_grid(tiles, out, cols=a.cols))
    return 0


def cmd_validate(a) -> int:
    from .text import build_ass
    from .timeline import build_plan

    plan = build_plan(a.spec)
    build_ass(plan, plan.base_dir / "work" / Path(a.spec).stem / "validate.ass")
    print(f"ok: {len(plan.clips)} clips, {plan.duration:.2f}s")
    return 0


def cmd_render(a) -> int:
    from .render import render

    out = render(a.spec, preview=a.preview, output=a.output, jobs=a.jobs)
    info = probe(out)
    print(f"{out}  ({info['duration']:.2f}s {info.get('width')}x{info.get('height')})")
    return 0


def cmd_hf(a) -> int:
    """HyperFrames helpers: scaffold a vedit-ready project, render it, or snapshot stills."""
    from . import hyperframes as HF

    if a.action == "list":
        for b in HF.builtins():
            extra = f", cover at {b['cover_at']}s" if b.get("cover_at") is not None else ""
            print(f"{b['name']:20s} [{b.get('kind', '?')}, {b['duration']:g}s{extra}"
                  f"{', blend=' + b['blend'] if b.get('blend') else ''}]\n{'':20s} {b['description']}\n"
                  f"{'':20s} variables: {b['variables']}")
        return 0
    if not a.project:
        raise VeditError(f"hf {a.action} needs a project")
    if a.action == "new":
        out = HF.new_project(Path(a.project), width=a.width or 1920, height=a.height or 1080, duration=a.duration or 4.0,
                             overlay=a.overlay)
        print(out)
        return 0
    project = HF.resolve(a.project, Path.cwd())
    variables = json.loads(a.variables) if a.variables else {}
    size = (a.width, a.height) if a.width and a.height else None
    work = Path("work")
    if a.action == "snapshot":
        dur = HF.meta(project)["duration"]
        times = [float(t) for t in a.times.split(",")] if a.times else \
            [round(dur * (i + 0.5) / a.count, 3) for i in range(a.count)]
        out_dir = Path(a.out or f"work/hf_stills/{project.name}")
        for f in HF.snapshot(project, times, out_dir, variables=variables, work=work, size=size, base=Path.cwd()):
            print(f)
    else:
        out_dir = Path(a.out or "work/hf_renders")
        print(HF.render(project, out_dir, alpha=a.alpha, fps=a.fps, variables=variables, quality=a.quality,
                        work=work, size=size, base=Path.cwd()))
    return 0


def cmd_synth_sfx(a) -> int:
    from .synth import make_sfx

    meta = make_sfx(Path(a.out))
    for k, v in meta.items():
        print(f"{k:14s} {v['duration']:.2f}s  peak at {v['peak']:.2f}s")
    return 0


def cmd_synth_music(a) -> int:
    from .synth import music_bed

    rep = music_bed(Path(a.out), a.mood, a.duration, a.bpm, seed=a.seed)
    beats_file = Path(a.out).with_suffix(".beats.json")
    beats_file.write_text(json.dumps({"tempo": rep["tempo"], "beat_period": rep["beat_period"],
                                      "beats": rep["beats"], "downbeats": rep["beats"][::4]}))
    print(f"{a.out}: {a.mood} {rep['tempo']} bpm, beats in {beats_file}")
    return 0


SPEC_TEMPLATE = {
    "brief": {"prompt": "", "logline": "", "audience": "", "duration_target": 60},
    "output": {"path": "out/final.mp4", "width": 1920, "height": 1080, "fps": 30, "crf": 18},
    "sources": {},
    "story": {
        "arc": [
            {"at": "0%", "label": "setup", "tone": "natural", "intensity": 0.8},
            {"at": "60%", "label": "conflict", "tone": "cold_thriller", "intensity": 0.8},
            {"at": "100%", "label": "resolution", "tone": "golden_hour", "intensity": 0.9},
        ],
        "look": {"grain": 0.15},
    },
    "timeline": [],
    "text": [],
    "graphics": [],
    "music": [],
    "sfx": [],
    "audio": {"loudness": -14},
}


def cmd_new(a) -> int:
    root = Path("projects") / a.name if not Path(a.name).is_absolute() else Path(a.name)
    for d in ("media", "music", "graphics", "work", "out"):
        (root / d).mkdir(parents=True, exist_ok=True)
    spec = root / "edit.json"
    if not spec.exists():
        spec.write_text(json.dumps(SPEC_TEMPLATE, indent=2) + "\n")
    print(f"project ready: {root}\n  put footage in {root / 'media'}, music in {root / 'music'}\n  spec: {spec}")
    return 0


def cmd_demo_media(a) -> int:
    """Synthetic footage + music so the pipeline can be exercised without real media."""
    from .synth import music_bed

    out = Path(a.out)
    (out / "media").mkdir(parents=True, exist_ok=True)
    (out / "music").mkdir(parents=True, exist_ok=True)
    W, H = a.width, a.height
    sources = {
        "city": f"gradients=s={W}x{H}:r=30:c0=0x203a5c:c1=0xe0a060:c2=0x601040:n=3:speed=0.02:d=8",
        "forest": f"gradients=s={W}x{H}:r=30:c0=0x1d4d2a:c1=0x9fc56b:c2=0x0b1f14:n=3:speed=0.015:type=radial:d=8",
        "fractal": f"mandelbrot=s={W}x{H}:r=30:end_scale=0.05",
        "life": f"life=s={W // 4}x{H // 4}:r=30:mold=10:ratio=0.2:death_color=#101030:life_color=#ffcc66,scale={W}:{H}:flags=neighbor",
        "bars": f"testsrc2=s={W}x{H}:r=30",
    }
    for name, src in sources.items():
        p = out / "media" / f"{name}.mp4"
        tone = {"city": 220, "forest": 330, "fractal": 440, "life": 550, "bars": 660}[name]
        ffmpeg(["-f", "lavfi", "-i", src, "-f", "lavfi", "-i", f"sine=f={tone}:r=48000",
                "-t", "8", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-af", "volume=0.2", "-shortest", p])
        print(p)
    rep = music_bed(out / "music" / "bed.wav", a.mood, 40)
    (out / "music" / "bed.beats.json").write_text(json.dumps({"beats": rep["beats"], "downbeats": rep["beats"][::4],
                                                             "tempo": rep["tempo"]}))
    print(out / "music" / "bed.wav")
    return 0


# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vedit", description="Prompt-driven video editing toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("doctor", help="check installed tools")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("probe", help="media info as JSON")
    s.add_argument("files", nargs="+")
    s.set_defaults(fn=cmd_probe)

    s = sub.add_parser("analyze", help="shots, silences, loudness and contact sheets for footage")
    s.add_argument("files", nargs="+")
    s.add_argument("--out", help="output dir (default: <project>/work/analysis)")
    s.add_argument("--threshold", type=float, default=0.3, help="scene-change threshold 0..1")
    s.add_argument("--no-sheet", action="store_true")
    s.set_defaults(fn=cmd_analyze)

    s = sub.add_parser("frames", help="extract stills at times, or a timecoded contact sheet")
    s.add_argument("file")
    s.add_argument("--times", help="comma-separated seconds")
    s.add_argument("--every", type=float, help="contact sheet interval (s)")
    s.add_argument("--width", type=int, default=960)
    s.add_argument("--out", default="work/frames")
    s.set_defaults(fn=cmd_frames)

    s = sub.add_parser("transcribe", help="speech to text with word timestamps")
    s.add_argument("files", nargs="+")
    s.add_argument("--model", default="small")
    s.add_argument("--language")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_transcribe)

    s = sub.add_parser("beats", help="tempo, beats, downbeats and energy rises of a music track")
    s.add_argument("file")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_beats)

    s = sub.add_parser("tones", help="list tone presets (optionally matching a mood word)")
    s.add_argument("--mood")
    s.set_defaults(fn=cmd_tones)

    s = sub.add_parser("look", help="grid comparing tones on a frame of footage")
    s.add_argument("file")
    s.add_argument("--at", type=float, default=1.0, help="time of the frame (s)")
    s.add_argument("--tones", help="comma list (default: all). 'original' = ungraded")
    s.add_argument("--intensity", type=float, default=1.0)
    s.add_argument("--out", default="work/look.jpg")
    s.set_defaults(fn=cmd_look)

    s = sub.add_parser("lut", help="export a tone as a .cube LUT (works in Resolve/Premiere too)")
    s.add_argument("tone")
    s.add_argument("--intensity", type=float, default=1.0)
    s.add_argument("--overrides", help="JSON of grade parameters")
    s.add_argument("--size", type=int, default=33)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_lut)

    s = sub.add_parser("plan", help="resolve the spec into a timeline table")
    s.add_argument("spec")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_plan)

    s = sub.add_parser("storyboard", help="graded still per clip, as the render will grade it")
    s.add_argument("spec")
    s.add_argument("--out")
    s.add_argument("--cols", type=int, default=4)
    s.set_defaults(fn=cmd_storyboard)

    s = sub.add_parser("validate", help="check a spec without rendering")
    s.add_argument("spec")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("render", help="render a spec")
    s.add_argument("spec")
    s.add_argument("--preview", action="store_true", help="half resolution, fast encode")
    s.add_argument("--output", "-o")
    s.add_argument("--jobs", "-j", type=int)
    s.set_defaults(fn=cmd_render)

    s = sub.add_parser("hf", help="HyperFrames: list built-ins, scaffold, render or snapshot a composition")
    s.add_argument("action", choices=["list", "new", "render", "snapshot"])
    s.add_argument("project", nargs="?", help="project folder, or a built-in name (bin/vedit hf list)")
    s.add_argument("--variables", help="JSON variable values")
    s.add_argument("--duration", type=float, help="new: composition length in seconds")
    s.add_argument("--overlay", action="store_true", help="new: transparent background (graphic over footage)")
    s.add_argument("--times", help="snapshot: comma-separated seconds")
    s.add_argument("--count", type=int, default=6, help="snapshot: number of evenly spaced stills")
    s.add_argument("--alpha", action="store_true", help="render: ProRes 4444 .mov with alpha")
    s.add_argument("--quality", default="looks", choices=["draft", "looks", "delivery"])
    s.add_argument("--width", type=int)
    s.add_argument("--height", type=int)
    s.add_argument("--fps", type=float, default=30)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_hf)

    s = sub.add_parser("synth-sfx", help="generate whoosh/impact/riser/... sound effects")
    s.add_argument("--out", default=str(SFX_DIR))
    s.set_defaults(fn=cmd_synth_sfx)

    s = sub.add_parser("synth-music", help="generate a placeholder music bed (+ beats file)")
    s.add_argument("--mood", default="uplifting")
    s.add_argument("--duration", type=float, default=60)
    s.add_argument("--bpm", type=float)
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_synth_music)

    s = sub.add_parser("new", help="scaffold a project folder with an edit.json")
    s.add_argument("name")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("demo-media", help="generate synthetic footage and music for testing")
    s.add_argument("--out", default="projects/demo")
    s.add_argument("--width", type=int, default=1280)
    s.add_argument("--height", type=int, default=720)
    s.add_argument("--mood", default="epic")
    s.set_defaults(fn=cmd_demo_media)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args) or 0
    except VeditError as e:
        log(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
