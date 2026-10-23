"""Bridge to HyperFrames (https://github.com/heygen-com/hyperframes), the HTML-to-video renderer
used for every designed element of an edit: full-screen scenes, graphics overlays and designed
transitions. vedit keeps the footage side (cutting, grading, beat sync, audio mix).

A composition is a HyperFrames project directory (with index.html). Rendering never touches the
source project: it is copied to a build directory where
  - libraries loaded from CDNs (gsap, lottie-web, three, ...) are replaced by local copies, so
    renders work offline and are reproducible;
  - assets/vedit/vm-shim.js is refreshed from hf/lib;
  - the variables passed by the edit spec become the declared defaults of the composition, so
    `render` and `snapshot` both show exactly what the edit asked for.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
from pathlib import Path

from .util import ROOT, VeditError, log, run, stable_hash

HF_BIN = ROOT / "bin" / "hyperframes"
NODE_MODULES = ROOT / "mograph" / "node_modules"
SHIM = ROOT / "hf" / "lib" / "vm-shim.js"
BUILTIN = ROOT / "hf" / "builtin"
CDN_RE = re.compile(r"https://(?:cdn\.jsdelivr\.net/npm|unpkg\.com)/((?:@[\w.-]+/)?[\w.-]+)@[^/\"'\s]+/([^\"'\s?#]+)")
SKIP_DIRS = {".hyperframes", "node_modules", "renders", ".git"}


def available() -> tuple[bool, str]:
    if not (NODE_MODULES / ".bin" / "hyperframes").exists():
        return False, "hyperframes CLI not installed (run scripts/setup.sh)"
    return True, "ok"


def _check() -> None:
    ok, why = available()
    if not ok:
        raise VeditError(f"HyperFrames unavailable: {why}")


def resolve(ref: str, base: Path | None = None) -> Path:
    """A project directory: relative to the edit, or the name of a built-in under hf/overlays."""
    p = Path(ref).expanduser()
    cands = [p] if p.is_absolute() else [(base or Path.cwd()) / p, BUILTIN / ref, BUILTIN / ref.replace("_", "-")]
    for c in cands:
        if (c / "index.html").exists():
            return c.resolve()
    avail = ", ".join(sorted(d.name for d in BUILTIN.iterdir() if (d / "index.html").exists())) if BUILTIN.is_dir() else ""
    raise VeditError(f"HyperFrames project not found: {ref} (needs index.html). Built-ins: {avail}")


def meta(project: Path) -> dict:
    """Root composition facts from index.html: duration, size, and vedit hints."""
    html = (project / "index.html").read_text()
    m = re.search(r"<[^>]*data-composition-id=[\"'][^\"']+[\"'][^>]*>", html)
    if not m:
        raise VeditError(f"{project}/index.html has no root element with data-composition-id")
    tag = m.group(0)
    attr = lambda name, d=None: (re.search(rf"{name}=[\"']([^\"']*)[\"']", tag) or [None, d])[1]
    out = {"path": project, "duration": float(attr("data-duration", "3")), "width": int(attr("data-width", "1920")),
           "height": int(attr("data-height", "1080"))}
    for key in ("cover-at", "blend", "kind"):
        v = attr(f"data-vedit-{key}")
        if v is not None:
            out[key.replace("-", "_")] = float(v) if key == "cover-at" else v
    return out


def builtins() -> list[dict]:
    """The compositions shipped in hf/builtin, with the description and variables from their header."""
    out = []
    for d in sorted(BUILTIN.iterdir()) if BUILTIN.is_dir() else []:
        if not (d / "index.html").exists():
            continue
        m = meta(d)
        head = re.search(r"<!--(.*?)-->", (d / "index.html").read_text(), re.S)
        text = " ".join(head.group(1).split()) if head else ""
        desc, _, variables = text.partition("variables:")
        out.append({**m, "name": d.name, "description": desc.strip(), "variables": variables.strip()})
    return out


def _project_files(project: Path):
    for p in sorted(project.rglob("*")):
        if p.is_file() and not (set(p.relative_to(project).parts) & SKIP_DIRS):
            yield p


MODULE_IMPORT_RE = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*)["'](\.{1,2}/[^"']+)["']""")


def _copy_vendored(local: Path, dest: Path) -> None:
    """Copy a library file, plus the files an ES module pulls in through relative imports."""
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(local, dest)
    if local.suffix in (".js", ".mjs"):
        for rel in MODULE_IMPORT_RE.findall(local.read_text(errors="replace")):
            dep = (local.parent / rel).resolve()
            if dep.is_file():
                _copy_vendored(dep, (dest.parent / rel).resolve())


def _vendor_html(text: str, build: Path) -> tuple[str, list[str]]:
    missing = []

    def sub(m: re.Match) -> str:
        pkg, rel = m.group(1), m.group(2)
        local = NODE_MODULES / pkg / rel
        if not local.exists():
            missing.append(m.group(0))
            return m.group(0)
        _copy_vendored(local, build / "assets" / "vendor" / pkg / rel)
        return f"./assets/vendor/{pkg}/{rel}"   # "./": a bare "assets/..." is invalid in import()

    return CDN_RE.sub(sub, text), missing


def _declare_variables(html: str, variables: dict) -> str:
    """Make the given values the declared defaults of index.html's composition variables."""
    m = re.search(r"data-composition-variables='([^']*)'", html)
    decls = json.loads(m.group(1)) if m else []
    by_id = {d["id"]: d for d in decls}
    for k, v in variables.items():
        if isinstance(v, (list, dict)):
            v, typ = json.dumps(v, ensure_ascii=False), "string"
        elif isinstance(v, bool):
            typ = "boolean"
        elif isinstance(v, (int, float)):
            typ = "number"
        else:
            v, typ = str(v), "string"
        d = by_id.get(k) or {"id": k, "type": typ, "label": k}
        if d.get("type") == "color" and isinstance(v, str):
            typ = "color"
        d["type"] = d.get("type") if k in by_id and d.get("type") in ("color", "enum") else typ
        d["default"] = v
        by_id[k] = d
    decl = json.dumps(list(by_id.values()), ensure_ascii=False).replace("'", "&#39;")
    if m:
        return html[:m.start()] + f"data-composition-variables='{decl}'" + html[m.end():]
    # a function replacement: the JSON's backslash escapes (\n, \") must reach the page verbatim
    return re.sub(r"<html\b", lambda _: f"<html data-composition-variables='{decl}'", html, count=1)


def _resize(html: str, width: int, height: int) -> str:
    """Set the root composition (and page) to width x height. Designs in vw/vh/vmin adapt."""
    m = meta_from_html(html)
    ow, oh = m["width"], m["height"]
    if (ow, oh) == (width, height):
        return html
    html = re.sub(r'(data-width=["\'])\d+(["\'])', rf"\g<1>{width}\g<2>", html)
    html = re.sub(r'(data-height=["\'])\d+(["\'])', rf"\g<1>{height}\g<2>", html)
    html = html.replace(f"width: {ow}px", f"width: {width}px").replace(f"height: {oh}px", f"height: {height}px")
    return html.replace(f"width={ow}, height={oh}", f"width={width}, height={height}")


def _set_duration(html: str, duration: float) -> str:
    """Set data-duration on the root composition element only."""
    m = re.search(r"<[^>]*data-composition-id=[\"'][^\"']+[\"'][^>]*>", html)
    if not m:
        return html
    tag = re.sub(r'(data-duration=["\'])[\d.]+(["\'])', rf"\g<1>{duration:.4f}\g<2>", m.group(0))
    return html[:m.start()] + tag + html[m.end():]


def meta_from_html(html: str) -> dict:
    m = re.search(r"<[^>]*data-composition-id=[\"'][^\"']+[\"'][^>]*>", html)
    tag = m.group(0) if m else ""
    get = lambda n, d: (re.search(rf"{n}=[\"']([^\"']*)[\"']", tag) or [None, d])[1]
    return {"width": int(get("data-width", "1920")), "height": int(get("data-height", "1080"))}


MEDIA_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".json", ".lottie", ".mp4", ".mov", ".webm",
              ".mp3", ".wav", ".m4a", ".woff2", ".ttf", ".otf")


def _media_refs(value, base: Path | None, found: dict):
    """Find variable values that are paths to files on disk (relative to the edit)."""
    if isinstance(value, dict):
        for v in value.values():
            _media_refs(v, base, found)
    elif isinstance(value, list):
        for v in value:
            _media_refs(v, base, found)
    elif isinstance(value, str) and value.lower().endswith(MEDIA_EXTS) and "://" not in value \
            and not value.startswith("assets/"):
        p = Path(value).expanduser()
        p = p if p.is_absolute() else ((base or Path.cwd()) / p)
        if p.exists():
            found[value] = p.resolve()


def _rewrite(value, mapping: dict):
    if isinstance(value, dict):
        return {k: _rewrite(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_rewrite(v, mapping) for v in value]
    return mapping.get(value, value) if isinstance(value, str) else value


def build(project: Path, work: Path, variables: dict | None = None, size: tuple[int, int] | None = None,
          base: Path | None = None, duration: float | None = None) -> Path:
    """Copy the project into a build dir with vendored libraries, the given variables and size.

    Files referenced by variables (images, Lottie JSON, clips) are copied into assets/media/ and
    the values rewritten to those root-relative paths, as HyperFrames requires. `duration` overrides
    the root composition's data-duration (compositions timed off VM.duration stretch to fit)."""
    variables = variables or {}
    media: dict = {}
    _media_refs(variables, base, media)
    files = list(_project_files(project))
    key = stable_hash(*files, *media.values(), SHIM, Path(__file__), variables, size, duration, [str(f.relative_to(project)) for f in files])
    mapping = {ref: f"assets/media/{stable_hash(p)}{p.suffix.lower()}" for ref, p in media.items()}
    variables = _rewrite(variables, mapping)
    out = work / "hf_build" / f"{project.name}_{key}"
    if (out / ".ready").exists():
        return out
    tmp = out.with_name(out.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    missing_all = []
    for f in files:
        rel = f.relative_to(project)
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix == ".html":
            text, missing = _vendor_html(f.read_text(), tmp)
            if rel.as_posix() == "index.html" and variables:
                text = _declare_variables(text, variables)
            if size:
                text = _resize(text, *size)
            if duration and rel.as_posix() == "index.html":
                text = _set_duration(text, duration)
            dest.write_text(text)
            missing_all += missing
        else:
            shutil.copy2(f, dest)
    for ref, rel in mapping.items():
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(media[ref], dest)
    if SHIM.exists():
        (tmp / "assets" / "vedit").mkdir(parents=True, exist_ok=True)
        shutil.copy2(SHIM, tmp / "assets" / "vedit" / "vm-shim.js")
    if missing_all:
        log(f"warning: {project.name}: no local copy for {sorted(set(missing_all))} (needs network)")
    (tmp / ".ready").write_text("ok")
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    tmp.replace(out)
    return out


def render(project: Path, out_dir: Path, *, alpha: bool, fps: float, variables: dict | None = None,
           quality: str = "looks", work: Path | None = None, size: tuple[int, int] | None = None,
           base: Path | None = None, duration: float | None = None) -> Path:
    """Render a composition: transparent ProRes .mov (alpha) or .mp4. Cached by content."""
    _check()
    work = work or out_dir
    b = build(project, work, variables, size, base, duration)
    ext = ".mov" if alpha else ".mp4"
    out = out_dir / f"{project.name}_{b.name.rsplit('_', 1)[-1]}_{int(fps)}_{quality}{ext}"
    if out.exists():
        return out
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f"{out.stem}.{os.getpid()}.{threading.get_ident()}.tmp{ext}")
    m = meta(b)
    log(f"HyperFrames: rendering {project.name} ({m['duration']:.2f}s @ {m['width']}x{m['height']}"
        f"{', alpha' if alpha else ''})")
    proc = run([HF_BIN, "render", "--format", "mov" if alpha else "mp4", "--fps", str(int(round(fps))),
                "--quality", quality, "--output", tmp.resolve()], capture=True, cwd=b)
    if not tmp.exists():
        tail = (proc.stdout or b"").decode(errors="replace").strip().splitlines()[-15:]
        raise VeditError("HyperFrames render produced no file:\n" + "\n".join(tail))
    tmp.replace(out)
    return out


def snapshot(project: Path, times: list[float], out_dir: Path, variables: dict | None = None,
             work: Path | None = None, size: tuple[int, int] | None = None, base: Path | None = None,
             duration: float | None = None) -> list[Path]:
    """PNG stills of the composition at the given times (for review sheets)."""
    _check()
    b = build(project, work or out_dir, variables, size, base, duration)
    run([HF_BIN, "snapshot", "--at", ",".join(f"{t:.3f}" for t in times)], capture=True, cwd=b)
    runs = [d for d in (b / ".hyperframes" / "artifacts" / "snapshots").iterdir() if d.is_dir()]
    latest = max(runs, key=lambda d: d.stat().st_mtime)
    frames = {}
    for f in latest.glob("frame-*-at-*.png"):
        m = re.search(r"-at-([\d.]+)s\.png$", f.name)
        if m:
            frames[float(m.group(1))] = f
    out_dir.mkdir(parents=True, exist_ok=True)
    res = []
    for i, t in enumerate(times):
        src = frames.get(min(frames, key=lambda x: abs(x - t))) if frames else None
        if src is None:
            raise VeditError(f"HyperFrames snapshot produced no frame for t={t}")
        dest = out_dir / f"{project.name}_{i:02d}_{t:.2f}.png"
        shutil.copy2(src, dest)
        res.append(dest)
    return res


def new_project(target: Path, *, width: int = 1920, height: int = 1080, duration: float = 4.0,
                overlay: bool = False) -> Path:
    """Scaffold a project with `hyperframes init`, then size it and add the vedit helpers."""
    _check()
    target = target.resolve()
    if (target / "index.html").exists():
        raise VeditError(f"{target} already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    run([HF_BIN, "init", target.name, "--json"], capture=True, cwd=target.parent)
    html = (target / "index.html").read_text()
    html = re.sub(r'data-duration="[\d.]+"', f'data-duration="{duration:g}"', html)
    html = re.sub(r'data-width="\d+"', f'data-width="{width}"', html)
    html = re.sub(r'data-height="\d+"', f'data-height="{height}"', html)
    html = html.replace("width: 1920px;", f"width: {width}px;").replace("height: 1080px;", f"height: {height}px;")
    html = html.replace('content="width=1920, height=1080"', f'content="width={width}, height={height}"')
    if overlay:
        html = html.replace("--ground: #6b6b6b;", "--ground: transparent;")
    (target / "index.html").write_text(html)
    (target / "assets" / "vedit").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SHIM, target / "assets" / "vedit" / "vm-shim.js")
    return target
