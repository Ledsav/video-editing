"""HTML/CSS/JS motion graphics -> alpha video, rendered frame-by-frame in headless Chromium.

Any HTML page that follows the runtime contract (mograph/lib/runtime.js) can be a
graphic: the bundled templates, or custom pages written for a specific edit.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
from pathlib import Path

from .timeline import template_meta, template_path
from .util import MOGRAPH_DIR, TEMPLATES_DIR, VeditError, log, run, stable_hash

RENDERER = MOGRAPH_DIR / "render.mjs"
RUNTIME = MOGRAPH_DIR / "lib" / "runtime.js"


def available() -> tuple[bool, str]:
    if not shutil.which("node"):
        return False, "node not found (install Node.js >= 18)"
    if not (MOGRAPH_DIR / "node_modules" / "playwright").is_dir():
        return False, "playwright not installed (run scripts/setup.sh)"
    return True, "ok"


def _check() -> None:
    ok, why = available()
    if not ok:
        raise VeditError(f"motion graphics unavailable: {why}")


def resolve(item: dict, base: Path | None = None) -> tuple[Path, dict]:
    ref = item.get("html") or item.get("template")
    if not ref:
        raise VeditError("graphic needs 'template' or 'html'")
    path = template_path(ref, base)
    return path, template_meta(str(path))


ASSET_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".json", ".mp3", ".wav")


def resolve_assets(params, base: Path):
    """Turn relative asset paths inside params (images, Lottie JSON...) into file:// URLs."""
    if isinstance(params, dict):
        return {k: resolve_assets(v, base) for k, v in params.items()}
    if isinstance(params, list):
        return [resolve_assets(v, base) for v in params]
    if isinstance(params, str) and params.lower().endswith(ASSET_EXTS) and "://" not in params:
        p = Path(params).expanduser()
        p = p if p.is_absolute() else (base / p)
        if p.exists():
            return p.resolve().as_uri()
    return params


def deps(html: Path) -> list:
    """Files a page declares it depends on (<meta name="vedit:deps" content="lib.js,data/x.json">, relative to the
    page): part of the render cache key, so editing a shared script re-renders the pages that use it. Text files count
    by content, others by size and modification time; missing files are ignored."""
    import re
    m = re.search(r'<meta\s+name="vedit:deps"\s+content="([^"]*)"', html.read_text())
    out = []
    for name in (m.group(1).split(",") if m else []):
        f = html.parent / name.strip()
        if name.strip() and f.is_file():
            out.append(f.read_text() if f.suffix in (".js", ".mjs", ".css", ".html", ".json") else f)
    return out


def _workers(frames: int) -> int:
    env = os.environ.get("VEDIT_MOGRAPH_WORKERS")
    if env:
        return max(1, int(env))
    return max(1, min((os.cpu_count() or 2) - 1, 4, frames // 45))


def render(html: Path, out_dir: Path, *, width: int, height: int, fps: float, duration: float,
           params: dict | None = None, opaque: bool = False, beats: list[float] | None = None,
           workers: int | None = None) -> Path:
    """Render a page to video. Cached by content + params.

    opaque=False: ProRes 4444 .mov with alpha (overlays). opaque=True: H.264 .mp4 from JPEG
    frames, about 3x faster (full-screen scenes). Long renders are split into frame ranges
    rendered by parallel browser workers and joined losslessly."""
    _check()
    params = params or {}
    beats = [round(b, 4) for b in (beats or [])]
    key = stable_hash(html.read_text(), RUNTIME.read_text(), RENDERER.read_text(), params, width, height, fps,
                      round(duration, 4), opaque, beats, *deps(html))
    ext = ".mp4" if opaque else ".mov"
    out = out_dir / f"{html.stem}_{key}{ext}"
    if out.exists():
        return out
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{os.getpid()}.{threading.get_ident()}"
    beats_file = None
    if beats:
        beats_file = out_dir / f".beats_{key}_{tag}.json"
        beats_file.write_text(json.dumps(beats))
    frames = max(1, round(duration * fps))
    n = workers or _workers(frames)
    log(f"rendering {'scene' if opaque else 'motion graphic'} {html.name} "
        f"({duration:.2f}s @ {width}x{height}, {n} worker{'s' if n > 1 else ''})")
    base = ["node", RENDERER, "--html", html, "--width", width, "--height", height, "--fps", fps,
            "--duration", f"{duration:.4f}", "--params", json.dumps(params)]
    if opaque:
        base.append("--opaque")
    if beats_file:
        base += ["--beats", beats_file]
    try:
        if n == 1:
            tmp = out.with_name(f"{out.stem}.{tag}.tmp{ext}")
            run([*base, "--out", tmp], capture=True)
            tmp.replace(out)
            return out
        bounds = [round(frames * i / n) for i in range(n + 1)]
        parts = [out.with_name(f"{out.stem}.{tag}.part{i}{ext}") for i in range(n)]
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=n) as ex:
            futs = [ex.submit(run, [*base, "--out", parts[i], "--from-frame", bounds[i], "--to-frame", bounds[i + 1]],
                              capture=True) for i in range(n)]
            for f in futs:
                f.result()
        listing = out.with_name(f"{out.stem}.{tag}.txt")
        listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
        tmp = out.with_name(f"{out.stem}.{tag}.tmp{ext}")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", listing, "-c", "copy", tmp], capture=True)
        tmp.replace(out)
        listing.unlink(missing_ok=True)
        for p in parts:
            p.unlink(missing_ok=True)
        return out
    finally:
        if beats_file:
            beats_file.unlink(missing_ok=True)


def stills(html: Path, times: list[float], prefix: Path, *, width: int, height: int,
           duration: float | None = None, params: dict | None = None) -> list[Path]:
    _check()
    prefix.parent.mkdir(parents=True, exist_ok=True)
    args = ["node", RENDERER, "--html", html, "--out", prefix, "--width", width, "--height", height,
            "--stills", ",".join(f"{t:.4f}" for t in times), "--params", json.dumps(params or {})]
    if duration:
        args += ["--duration", f"{duration:.4f}"]
    proc = run(args, capture=True)
    return [Path(p) for p in json.loads(proc.stdout.decode().strip().splitlines()[-1])]


def contact_strip(html: Path, out: Path, *, times: list[float] | None = None, count: int = 6,
                  width: int = 1280, height: int = 720, duration: float | None = None,
                  params: dict | None = None, background: Path | None = None) -> Path:
    """Render several moments of a graphic side by side (over a checkerboard or a frame)."""
    from PIL import Image, ImageDraw

    meta = template_meta(str(html))
    dur = duration or float(meta.get("duration", 2.0))
    if not times:
        times = [dur * (i + 0.5) / count for i in range(count)]
    tmp_prefix = out.parent / f".strip_{html.stem}"
    files = stills(html, times, tmp_prefix, width=width, height=height, duration=dur, params=params)
    tw, th = 480, round(480 * height / width)
    cols = min(len(files), 3)
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 26)), (24, 24, 24))
    if background and background.exists():
        bg = Image.open(background).convert("RGBA").resize((tw, th))
    else:
        bg = Image.new("RGBA", (tw, th), (90, 90, 90, 255))
        d = ImageDraw.Draw(bg)
        for y in range(0, th, 24):
            for x in range(0, tw, 24):
                if (x // 24 + y // 24) % 2:
                    d.rectangle([x, y, x + 23, y + 23], fill=(130, 130, 130, 255))
    blend_screen = meta.get("blend") == "screen"
    for i, (f, t) in enumerate(zip(files, times)):
        fg = Image.open(f).convert("RGBA").resize((tw, th))
        if blend_screen:
            from PIL import ImageChops
            tile = ImageChops.screen(bg.convert("RGB"), fg.convert("RGB"))
        else:
            tile = Image.alpha_composite(bg, fg).convert("RGB")
        x, y = (i % cols) * tw, (i // cols) * (th + 26)
        sheet.paste(tile, (x, y))
        ImageDraw.Draw(sheet).text((x + 8, y + th + 6), f"t={t:.2f}s", fill=(230, 230, 230))
        f.unlink(missing_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def list_templates() -> list[dict]:
    rows = []
    for p in sorted(TEMPLATES_DIR.glob("*.html")):
        m = template_meta(str(p))
        rows.append({"name": p.stem, "kind": m.get("kind", "overlay"), "duration": m.get("duration"),
                     "cover_at": m.get("cover_at"), "blend": m.get("blend", "normal"),
                     "description": m.get("description", ""), "params": m.get("params", "")})
    return rows
