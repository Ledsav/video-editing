"""Bridge to HyperFrames (https://github.com/heygen-com/hyperframes), the HTML-to-video renderer
used for every designed element of an edit: full-screen scenes, graphics overlays and designed
transitions. vedit keeps the footage side (cutting, grading, beat sync, audio mix).

A composition is a HyperFrames project directory (with index.html), or a single vedit page (an .html
file written against the vedit runtime: VM.onFrame, vedit:* meta tags, VEDIT.libs; see
hf/lib/vedit-runtime.js). Rendering never touches the source: it is copied to a build directory where
  - libraries loaded from CDNs (gsap, lottie-web, three, ...) are replaced by local copies, so
    renders work offline and are reproducible;
  - assets/vedit/vm-shim.js is refreshed from hf/lib;
  - the variables passed by the edit spec become the declared defaults of the composition, so
    `render` and `snapshot` both show exactly what the edit asked for.
A page's build mirrors the folder tree around it with symlinks (so `../lib/shared.js` and relative
asset paths keep working) and gets a generated index.html that loads the vedit runtime.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from functools import lru_cache
from pathlib import Path

from .util import ROOT, VeditError, log, run, stable_hash

HF_BIN = ROOT / "bin" / "hyperframes"
NODE_MODULES = ROOT / "mograph" / "node_modules"
SHIM = ROOT / "hf" / "lib" / "vm-shim.js"
PAGE_RUNTIME = ROOT / "hf" / "lib" / "vedit-runtime.js"
PAGE_CONSOLE = ROOT / "hf" / "lib" / "page-console.mjs"
READY_TIMEOUT_MS = 180000      # heavy pages (three.js characters, mocap) take a while in software WebGL
PAGE_ID = "vedit-page"
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


def is_page(path: Path) -> bool:
    """A single vedit page (an .html file) rather than a HyperFrames project directory."""
    return path.suffix.lower() in (".html", ".htm") and path.is_file()


def resolve(ref: str, base: Path | None = None) -> Path:
    """A project directory or a vedit page: relative to the edit, or the name of a built-in."""
    p = Path(ref).expanduser()
    cands = [p] if p.is_absolute() else [(base or Path.cwd()) / p, BUILTIN / ref, BUILTIN / ref.replace("_", "-")]
    for c in cands:
        if (c / "index.html").exists() or is_page(c):
            return c.resolve()
    avail = ", ".join(sorted(d.name for d in BUILTIN.iterdir() if (d / "index.html").exists())) if BUILTIN.is_dir() else ""
    raise VeditError(f"HyperFrames composition not found: {ref} (a folder with index.html, or a vedit page .html). "
                     f"Built-ins: {avail}")


def page_meta(page: Path) -> dict:
    """A vedit page's <meta name="vedit:*"> tags (kind, duration, cover-at, blend, libs, deps, ...)."""
    return dict(re.findall(r'<meta\s+name="vedit:([\w-]+)"\s+content="([^"]*)"', page.read_text()))


def meta(project: Path) -> dict:
    """Root composition facts from index.html (or a vedit page's meta tags): duration, size, vedit hints."""
    if is_page(project):
        m = page_meta(project)
        out = {"path": project, "duration": float(m.get("duration", 2.0)), "width": 1920, "height": 1080}
        if "cover-at" in m:
            out["cover_at"] = float(m["cover-at"])
        out.update({k: m[k] for k in ("blend", "kind") if k in m})
        return out
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


def deps(page: Path) -> list:
    """Files a page declares it depends on (<meta name="vedit:deps" content="lib.js,data/x.json">, relative to the
    page): part of the build key, so editing a shared script re-renders the pages that use it. Text files count
    by content, others by size and modification time; missing files are ignored."""
    out = []
    for name in page_meta(page).get("deps", "").split(","):
        f = page.parent / name.strip()
        if name.strip() and f.is_file():
            out.append(f.read_text() if f.suffix in (".js", ".mjs", ".css", ".html", ".json") else f)
    return out


# Asset values a page's params were resolved against the edit for (the vedit renderer turned them into file
# URLs); anything else is passed through and the page resolves it against itself.
PAGE_ASSET_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".json", ".mp3", ".wav")
PAGE_SKIP = SKIP_DIRS | {"index.html", "_vedit", "work", "out"}
PARENT_REF_RE = re.compile(r"""["'`]((?:\.\./)+)""")


def _page_site(page: Path) -> Path:
    """The folder to mirror for a page: its own, or the ancestor its `../` references reach."""
    up = max((m.count("../") for m in PARENT_REF_RE.findall(page.read_text())), default=0)
    site = page.parent
    for _ in range(up):
        site = site.parent
    return site


def _build_page(page: Path, work: Path, variables: dict, size: tuple[int, int] | None, base: Path | None,
                duration: float | None, fps: float) -> Path:
    m = page_meta(page)
    W, H = size or (1920, 1080)
    D = float(duration or m.get("duration", 2.0))
    variables = dict(variables)
    beats = variables.pop("vedit_beats", [])
    site = _page_site(page)
    page_dir = page.parent.relative_to(site)
    up = "../" * len(page_dir.parts)
    media: dict = {}
    _page_media(variables, base or page.parent, media)
    key = stable_hash(page.read_text(), PAGE_RUNTIME, Path(__file__), str(site), variables, beats, W, H, D, fps,
                      *deps(page), *media.values())
    out = work / "hf_build" / f"{page.stem}_{key}"
    if (out / ".ready").exists():
        return out
    tmp = out.with_name(out.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    work_abs = work.resolve()
    for entry in sorted(site.iterdir()):
        r = entry.resolve()
        if entry.name in PAGE_SKIP or r == work_abs or r in work_abs.parents:
            continue
        os.symlink(r, tmp / entry.name, target_is_directory=r.is_dir())
    vend = tmp / "_vedit" / "vendor"
    vend.mkdir(parents=True)
    for pkg in ("gsap", "lottie-web", "three"):
        if (NODE_MODULES / pkg).is_dir():
            os.symlink((NODE_MODULES / pkg).resolve(), vend / pkg, target_is_directory=True)
    shutil.copy2(PAGE_RUNTIME, tmp / "_vedit" / "runtime.js")
    mapping = {}
    for ref, src in media.items():
        try:          # inside the mirror: the same file, addressed from the page
            mapping[ref] = os.path.relpath(src, site / page_dir) if src.is_relative_to(site.resolve()) else None
        except ValueError:
            mapping[ref] = None
        if mapping[ref] is None:
            dest = tmp / "_vedit" / "media" / f"{stable_hash(src)}{src.suffix.lower()}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            mapping[ref] = f"{up}_vedit/media/{dest.name}"
    variables = _rewrite(variables, mapping)
    libs = {x.strip() for x in m.get("libs", "").split(",") if x.strip()}
    wait_ready = "VM_READY" in _page_scripts_text(page)
    js = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    head = [f'<base href="{page_dir.as_posix()}/">' if page_dir.parts else ""]
    head.append("<script>window.__VEDIT_RENDERER__ = true; window.PARAMS = " + js(variables) + ";\n"
                f"  window.VEDIT = {js({'width': W, 'height': H, 'fps': fps, 'duration': D, 'beats': beats, 'waitReady': wait_ready})};\n"
                f"  const __v = (p) => new URL('{up}_vedit/vendor/' + p, document.baseURI).href;\n"
                "  window.VEDIT.libs = { three: __v('three/build/three.module.js'), three_addons: __v('three/examples/jsm/') };"
                "</script>")
    if "gsap" in libs:
        head.append(f'<script src="{up}_vedit/vendor/gsap/dist/gsap.min.js"></script>')
    if "lottie" in libs:
        head.append(f'<script src="{up}_vedit/vendor/lottie-web/build/player/lottie.min.js"></script>')
    head.append(f'<script src="{up}_vedit/runtime.js"></script>')
    html = page.read_text()
    inject = "\n".join(h for h in head if h) + "\n"
    hm = re.search(r"<head\b[^>]*>", html, re.I)
    if hm:
        html = html[:hm.end()] + "\n" + inject + html[hm.end():]
    else:
        hm = re.search(r"<html\b[^>]*>", html, re.I)
        at = hm.end() if hm else 0
        html = html[:at] + "<head>" + inject + "</head>" + html[at:]
    root = (f'data-composition-id="{PAGE_ID}" data-start="0" data-duration="{D:.4f}" data-width="{W}" '
            f'data-height="{H}" data-no-timeline')
    bm = re.search(r"<body\b", html, re.I)
    if bm:
        html = html[:bm.end()] + " " + root + html[bm.end():]
    else:
        hm = re.search(r"</head>", html, re.I)
        html = html[:hm.end()] + f"<body {root}>" + html[hm.end():]
    tail = "<script>window.VM.__register();</script>\n"
    em = re.search(r"</body>", html, re.I)
    html = html[:em.start()] + tail + html[em.start():] if em else html + tail
    (tmp / "index.html").write_text(html)
    (tmp / ".ready").write_text("ok")
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    tmp.replace(out)
    return out


def _page_scripts_text(page: Path) -> str:
    """The page plus the local scripts it loads (to see what it relies on, e.g. VM_READY)."""
    html = page.read_text()
    parts = [html]
    for src in re.findall(r"""<script[^>]+src=["']([^"'#?]+)""", html, re.I):
        f = page.parent / src
        if "://" not in src and f.is_file():
            parts.append(f.read_text(errors="replace"))
    return "\n".join(parts)


def _page_media(value, base: Path, found: dict):
    if isinstance(value, dict):
        for v in value.values():
            _page_media(v, base, found)
    elif isinstance(value, list):
        for v in value:
            _page_media(v, base, found)
    elif isinstance(value, str) and value.lower().endswith(PAGE_ASSET_EXTS) and "://" not in value:
        p = Path(value).expanduser()
        p = p if p.is_absolute() else base / p
        if p.is_file():
            found[value] = p.resolve()


def build(project: Path, work: Path, variables: dict | None = None, size: tuple[int, int] | None = None,
          base: Path | None = None, duration: float | None = None, fps: float = 30) -> Path:
    """Copy the project into a build dir with vendored libraries, the given variables and size.

    Files referenced by variables (images, Lottie JSON, clips) are copied into assets/media/ and
    the values rewritten to those root-relative paths, as HyperFrames requires. `duration` overrides
    the root composition's data-duration (compositions timed off VM.duration stretch to fit)."""
    variables = variables or {}
    if is_page(project):
        return _build_page(project, work, variables, size, base, duration, fps)
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
    b = build(project, work, variables, size, base, duration, fps)
    ext = ".mov" if alpha else ".mp4"
    out = out_dir / f"{project.stem}_{b.name.rsplit('_', 1)[-1]}_{int(fps)}_{quality}{ext}"
    if out.exists():
        return out
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f"{out.stem}.{os.getpid()}.{threading.get_ident()}.tmp{ext}")
    m = meta(b)
    log(f"HyperFrames: rendering {project.stem} ({m['duration']:.2f}s @ {m['width']}x{m['height']}"
        f"{', alpha' if alpha else ''})")
    proc = run([HF_BIN, "render", "--format", "mov" if alpha else "mp4", "--fps", str(int(round(fps))),
                "--quality", quality, "--player-ready-timeout", READY_TIMEOUT_MS, "--output", tmp.resolve()],
               capture=True, cwd=b)
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
    run([HF_BIN, "snapshot", "--at", ",".join(f"{t:.3f}" for t in times), "--timeout", READY_TIMEOUT_MS,
         "--no-end", "--describe", "false"], capture=True, cwd=b)
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
        dest = out_dir / f"{project.stem}_{i:02d}_{t:.2f}.png"
        shutil.copy2(src, dest)
        res.append(dest)
    return res


@lru_cache(maxsize=1)
def _chrome() -> str:
    out = run([HF_BIN, "browser", "path"], capture=True).stdout.decode().strip().splitlines()
    return out[-1].strip() if out else ""


def page_console(page: Path, work: Path, variables: dict | None = None, size: tuple[int, int] | None = None,
                 base: Path | None = None, duration: float | None = None, fps: float = 30,
                 times: list[float] | None = None) -> list[str]:
    """What a vedit page logs with console.error (and uncaught errors) until it is ready, then at `times`.

    HyperFrames' snapshot does not relay the page console; the kit pages report timing and load problems
    there (e.g. ANIME_TIMES). Lines start with "[page console] " or "[page error] "."""
    _check()
    b = build(page, work, variables, size, base, duration, fps)
    proc = subprocess.run(["node", str(PAGE_CONSOLE), str(b), str(NODE_MODULES), _chrome(), str(READY_TIMEOUT_MS),
                           ",".join(f"{t:.4f}" for t in times or [])], capture_output=True, text=True)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith(("[page console] ", "[page error] "))]
    if proc.returncode and not lines:
        lines.append("[page error] " + (proc.stderr.strip().splitlines() or ["page-console failed"])[-1])
    return lines


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
