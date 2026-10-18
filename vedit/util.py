"""Shared helpers: running ffmpeg, probing media, colors, hashing."""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS_DIR = ASSETS / "fonts"
SFX_DIR = ASSETS / "sfx"
MOGRAPH_DIR = ROOT / "mograph"
TEMPLATES_DIR = MOGRAPH_DIR / "templates"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

VERBOSE = bool(os.environ.get("VEDIT_VERBOSE"))


class VeditError(RuntimeError):
    """A user-facing error (bad spec, missing file, failed ffmpeg run)."""


def log(msg: str) -> None:
    print(f"[vedit] {msg}", file=sys.stderr, flush=True)


def require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise VeditError(f"'{binary}' not found on PATH. Run scripts/setup.sh first.")
    return path


def run(cmd: list[str], *, capture: bool = False, cwd: Path | None = None,
        input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    """Run a command, raising VeditError with the tail of stderr on failure."""
    if VERBOSE:
        log("$ " + " ".join(shlex.quote(str(c)) for c in cmd))
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        tail = proc.stderr.decode(errors="replace").strip().splitlines()[-25:]
        raise VeditError(f"command failed ({cmd[0]}):\n" + "\n".join(tail))
    return proc


def ffmpeg(args: list, *, capture: bool = False) -> subprocess.CompletedProcess:
    return run([require("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *args],
               capture=capture)


@lru_cache(maxsize=256)
def _probe_cached(path: str, mtime: float) -> dict:
    proc = run([require("ffprobe"), "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", path], capture=True)
    return json.loads(proc.stdout)


def probe(path: str | Path) -> dict:
    """Return a compact description of a media file."""
    p = Path(path)
    if not p.exists():
        raise VeditError(f"media not found: {p}")
    data = _probe_cached(str(p), p.stat().st_mtime)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"
              and s.get("disposition", {}).get("attached_pic", 0) == 0), None)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})
    info: dict = {
        "path": str(p),
        "duration": float(fmt.get("duration") or (v or {}).get("duration") or 0.0),
        "has_video": v is not None,
        "has_audio": a is not None,
        "is_image": p.suffix.lower() in IMAGE_EXTS,
    }
    if v:
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(float(sd["rotation"]))
        rot = int(v.get("tags", {}).get("rotate", rot))
        if abs(rot) % 180 == 90:
            w, h = h, w
        info.update(width=w, height=h, fps=parse_rate(v.get("avg_frame_rate") or v.get("r_frame_rate")),
                    vcodec=v.get("codec_name"), pix_fmt=v.get("pix_fmt"), rotation=rot)
    if a:
        info.update(sample_rate=int(a.get("sample_rate", 0)), channels=int(a.get("channels", 0)),
                    acodec=a.get("codec_name"))
    return info


def parse_rate(rate: str | None) -> float:
    if not rate or rate in ("0/0", "N/A"):
        return 0.0
    if "/" in rate:
        n, d = rate.split("/")
        return float(n) / float(d) if float(d) else 0.0
    return float(rate)


def hex_to_rgb(color: str) -> tuple[float, float, float]:
    """'#ff8800' / 'ff8800' / '#f80' -> (1.0, 0.53, 0.0)."""
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) not in (6, 8):
        raise VeditError(f"bad color: {color!r}")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def ass_color(color: str, alpha: float = 0.0) -> str:
    """CSS hex color -> ASS &HAABBGGRR (alpha 0 = opaque)."""
    r, g, b = (round(x * 255) for x in hex_to_rgb(color))
    return f"&H{round(alpha * 255):02X}{b:02X}{g:02X}{r:02X}"


def stable_hash(*parts) -> str:
    h = hashlib.sha1()
    for part in parts:
        if isinstance(part, Path) and part.exists() and part.is_file():
            st = part.stat()
            h.update(f"{part}:{st.st_size}:{st.st_mtime_ns}".encode())
        elif isinstance(part, (dict, list)):
            h.update(json.dumps(part, sort_keys=True, default=str).encode())
        else:
            h.update(str(part).encode())
        h.update(b"\x00")
    return h.hexdigest()[:16]


def parse_time(value, total: float | None = None) -> float:
    """Accept 12.5, "12.5", "1:02.5", "00:01:02.5" or "40%" (needs total)."""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s.endswith("%"):
        if total is None:
            raise VeditError(f"percentage time {s!r} needs a known total duration")
        return float(s[:-1]) / 100.0 * total
    if ":" in s:
        secs = 0.0
        for part in s.split(":"):
            secs = secs * 60 + float(part)
        return secs
    return float(s)


def fmt_time(t: float) -> str:
    m, s = divmod(max(t, 0.0), 60)
    return f"{int(m):d}:{s:05.2f}"


def ff_escape(path: str | Path) -> str:
    """Escape a path for use inside an ffmpeg filter argument."""
    s = str(path)
    for ch in ("\\", ":", "'", ",", "[", "]", ";"):
        s = s.replace(ch, "\\" + ch)
    return s


@lru_cache(maxsize=1)
def installed_font_families() -> frozenset[str]:
    families: set[str] = set()
    if shutil.which("fc-list"):
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            for fam in line.split(","):
                families.add(fam.strip().replace("\\-", "-"))
    if FONTS_DIR.is_dir() and any(FONTS_DIR.glob("*.ttf")):
        try:
            from fontTools.ttLib import TTFont
            for f in FONTS_DIR.glob("*.ttf"):
                name = TTFont(str(f))["name"].getDebugName(1)
                if name:
                    families.add(name)
        except Exception:
            pass
    return frozenset(families)


def pick_font(preferences: list[str]) -> str:
    fams = installed_font_families()
    for fam in preferences:
        if fam in fams:
            return fam
    for fallback in ("Inter", "DejaVu Sans", "Liberation Sans", "FreeSans"):
        if fallback in fams:
            return fallback
    return preferences[0] if preferences else "Sans"
