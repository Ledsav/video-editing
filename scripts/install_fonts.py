#!/usr/bin/env python3
"""Convert the @fontsource packages installed in mograph/node_modules into TTF files.

libass (used by ffmpeg for text) needs TTF/OTF files, and Chromium (used for motion
graphics) resolves fonts through fontconfig, so we write them to assets/fonts and
register that directory with fontconfig (~/.local/share/fonts/vedit -> assets/fonts).
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "mograph" / "node_modules" / "@fontsource"
DST = ROOT / "assets" / "fonts"
WEIGHTS = {"300", "400", "500", "600", "700", "800", "900"}
WEIGHT_NAMES = {300: "Light", 400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold",
                800: "ExtraBold", 900: "Black"}


def fix_names(font, family: str, weight: int, italic: bool) -> None:
    """Fontsource files are instances of variable fonts and can carry the wrong family
    name (e.g. "Montserrat Thin" for every weight). Rewrite the name table so that
    fontconfig sees one family with proper weights."""
    wname = WEIGHT_NAMES.get(weight, "Regular")
    style = (wname if wname != "Regular" else "") + (" Italic" if italic else "")
    style = style.strip() or "Regular"
    ribbi = weight in (400, 700)
    legacy_family = family if ribbi else f"{family} {wname}"
    legacy_style = ("Bold " if weight == 700 else "") + ("Italic" if italic else "")
    legacy_style = legacy_style.strip() or "Regular"
    name = font["name"]
    for nid in (1, 2, 4, 6, 16, 17, 21, 22, 25):
        name.removeNames(nameID=nid)
    full = f"{family} {style}".replace(" Regular", "") if style != "Regular" else family
    ps = (family.replace(" ", "") + "-" + style.replace(" ", "")).replace("-Regular", "-Regular")
    for nid, val in ((1, legacy_family), (2, legacy_style), (4, full), (6, ps), (16, family), (17, style)):
        name.setName(val, nid, 3, 1, 0x409)
    os2 = font["OS/2"]
    os2.usWeightClass = weight
    sel = os2.fsSelection & ~0b1100001  # clear italic, bold, regular
    if italic:
        sel |= 0b1
    if weight == 700:
        sel |= 0b100000
    if not italic and weight != 700:
        sel |= 0b1000000
    os2.fsSelection = sel
    font["head"].macStyle = (1 if weight == 700 else 0) | (2 if italic else 0)


def main() -> int:
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        print("fonttools not installed; skipping font conversion", file=sys.stderr)
        return 1
    if not SRC.is_dir():
        print(f"{SRC} not found (run npm install in mograph/)", file=sys.stderr)
        return 1
    DST.mkdir(parents=True, exist_ok=True)
    count = 0
    for woff2 in sorted(SRC.glob("*/files/*-latin-*-*.woff2")):
        m = re.match(r"(.+)-latin-(\d+)-(normal|italic)\.woff2$", woff2.name)
        if not m or m.group(2) not in WEIGHTS:
            continue
        out = DST / f"{m.group(1)}-{m.group(2)}-{m.group(3)}.ttf"
        if out.exists():
            count += 1
            continue
        meta_file = woff2.parent.parent / "metadata.json"
        family = json.loads(meta_file.read_text())["family"] if meta_file.exists() else \
            m.group(1).replace("-", " ").title()
        font = TTFont(str(woff2))
        font.flavor = None
        fix_names(font, family, int(m.group(2)), m.group(3) == "italic")
        font.save(str(out))
        count += 1
    # Make the fonts visible to fontconfig (Chromium + libass lookups by family name).
    user_fonts = Path.home() / ".local" / "share" / "fonts"
    user_fonts.mkdir(parents=True, exist_ok=True)
    link = user_fonts / "vedit"
    if link.is_symlink() or link.exists():
        if link.is_symlink():
            link.unlink()
        else:
            shutil.rmtree(link)
    link.symlink_to(DST, target_is_directory=True)
    if shutil.which("fc-cache"):
        subprocess.run(["fc-cache", "-f", str(user_fonts)], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"{count} font files in {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
