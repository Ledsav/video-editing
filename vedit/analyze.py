"""Footage analysis so the editor can choose shots from a prompt: scene cuts, silences,
loudness over time, and contact sheets to look at."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from .util import ffmpeg, fmt_time, probe, require, run


def decode_audio(path: str | Path, sr: int = 22050) -> np.ndarray:
    proc = run([require("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn",
                "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture=True)
    return np.frombuffer(proc.stdout, dtype=np.float32)


def scene_cuts(path: str | Path, threshold: float = 0.3) -> list[float]:
    proc = run([require("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(path), "-an",
                "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
               capture=True)
    times = [float(m.group(1)) for m in re.finditer(r"pts_time:([\d.]+)", proc.stderr.decode(errors="replace"))]
    return [round(t, 3) for t in times]


def silences(path: str | Path, noise_db: float = -35, min_dur: float = 0.5) -> list[list[float]]:
    proc = run([require("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(path), "-vn",
                "-af", f"silencedetect=n={noise_db}dB:d={min_dur}", "-f", "null", "-"], capture=True)
    err = proc.stderr.decode(errors="replace")
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        out.append([round(s, 3), round(e, 3) if e is not None else None])
    return out


def loudness_curve(path: str | Path, hop: float = 0.5) -> list[float]:
    y = decode_audio(path, 16000)
    n = int(16000 * hop)
    if len(y) < n:
        return []
    frames = y[: len(y) // n * n].reshape(-1, n)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    return [round(float(20 * np.log10(r)), 1) for r in rms]


def contact_sheet(path: str | Path, out: Path, *, interval: float | None = None, cols: int = 6,
                  width: int = 320) -> list[Path]:
    """Thumbnails every `interval` seconds with burned-in timecodes, tiled into sheets."""
    info = probe(path)
    dur = max(info["duration"], 0.1)
    if interval is None:
        interval = min(max(dur / 36, 1.0), 30.0)
    rows = 6
    out.parent.mkdir(parents=True, exist_ok=True)
    pattern = out.with_name(out.stem + "_%02d" + out.suffix)
    font = "Inter"
    vf = (f"fps=1/{interval:.3f},scale={width}:-2,"
          f"drawtext=font='{font}':text='%{{pts\\:hms}}':x=6:y=h-th-6:fontsize=18:fontcolor=white:"
          f"box=1:boxcolor=black@0.6:boxborderw=4,tile={cols}x{rows}:padding=4:color=0x181818")
    ffmpeg(["-i", path, "-an", "-vf", vf, "-fps_mode", "vfr", "-q:v", "3", pattern])
    return sorted(out.parent.glob(out.stem + "_*" + out.suffix))


def frames_at(path: str | Path, times: list[float], out_dir: Path, width: int = 960) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for t in times:
        f = out_dir / f"{Path(path).stem}_{t:08.3f}.jpg"
        ffmpeg(["-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "2", f])
        files.append(f)
    return files


def analyze(path: str | Path, out_dir: Path, *, sheet: bool = True, scene_threshold: float = 0.3) -> dict:
    info = probe(path)
    name = Path(path).stem
    report: dict = {"file": str(path), **{k: info.get(k) for k in
                    ("duration", "width", "height", "fps", "has_audio", "is_image")}}
    if info["is_image"]:
        return report
    cuts = scene_cuts(path, scene_threshold)
    report["scene_cuts"] = cuts
    bounds = [0.0] + cuts + [info["duration"]]
    report["shots"] = [{"start": round(a, 3), "end": round(b, 3), "duration": round(b - a, 3)}
                       for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]
    if info["has_audio"]:
        report["silences"] = silences(path)
        curve = loudness_curve(path)
        report["loudness_db_per_0.5s"] = curve
        if curve:
            arr = np.array(curve)
            loud = np.argsort(arr)[-5:][::-1]
            report["loudest_moments"] = [round(float(i) * 0.5, 1) for i in loud]
    if sheet:
        sheets = contact_sheet(path, out_dir / f"{name}_sheet.jpg")
        report["contact_sheets"] = [str(s) for s in sheets]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.analysis.json").write_text(json.dumps(report, indent=2))
    return report


def summarize(report: dict) -> str:
    lines = [f"{report['file']}: {fmt_time(report['duration'] or 0)}"
             + (f" {report.get('width')}x{report.get('height')} @ {report.get('fps', 0):.2f}fps"
                if report.get("width") else "")
             + (" audio" if report.get("has_audio") else " no-audio")]
    if "shots" in report:
        lines.append(f"  {len(report['shots'])} shots: " + ", ".join(
            f"{fmt_time(s['start'])}-{fmt_time(s['end'])}" for s in report["shots"][:24])
            + (" ..." if len(report["shots"]) > 24 else ""))
    if report.get("silences"):
        lines.append(f"  silences: {len(report['silences'])} (first: {report['silences'][:4]})")
    if report.get("loudest_moments"):
        lines.append(f"  loudest moments (s): {report['loudest_moments']}")
    for s in report.get("contact_sheets", []):
        lines.append(f"  contact sheet: {s}")
    return "\n".join(lines)
