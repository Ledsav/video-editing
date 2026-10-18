"""Animated typography: titles, lower thirds, kinetic words and captions as ASS subtitles.

libass (ffmpeg's `ass` filter) renders these with real kerning, outlines, blur and
per-character transforms, which is enough for clean kinetic typography. For fully
designed animated graphics use mograph templates instead (see mograph.py).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .timeline import Plan, resolve_path
from .util import VeditError, ass_color, pick_font

STYLES: dict[str, dict] = {
    "title": {"fonts": ["Bebas Neue", "Anton", "Oswald", "Inter Display Black", "Inter"],
              "size": 0.15, "bold": False, "uppercase": True, "spacing": 0.004, "position": "center",
              "outline": 0.0, "shadow": 0.004, "animation": "tracking_in"},
    "subtitle": {"fonts": ["Montserrat", "Inter"], "size": 0.042, "bold": False, "uppercase": True,
                 "spacing": 0.008, "position": "center", "nudge": [0, 0.11], "animation": "fade"},
    "lower_third": {"fonts": ["Montserrat", "Inter"], "size": 0.052, "bold": True, "position": "lower_left",
                    "outline": 0.0, "shadow": 0.003, "animation": "slide_right"},
    "caption": {"fonts": ["Inter", "Montserrat", "DejaVu Sans"], "size": 0.045, "bold": True,
                "position": "bottom", "outline": 0.0035, "shadow": 0.002, "animation": "none",
                "out": "none"},
    "social": {"fonts": ["Montserrat", "Archivo Black", "Inter"], "size": 0.072, "bold": True,
               "uppercase": True, "position": "bottom", "nudge": [0, -0.16], "outline": 0.006,
               "shadow": 0.0, "animation": "pop", "out": "none"},
    "kinetic": {"fonts": ["Anton", "Bebas Neue", "Archivo Black", "Inter Display Black"], "size": 0.2,
                "uppercase": True, "position": "center", "shadow": 0.005, "animation": "words"},
    "quote": {"fonts": ["Playfair Display", "DM Serif Display", "Cormorant Garamond", "DejaVu Serif"],
              "size": 0.06, "italic": True, "position": "center", "shadow": 0.003, "animation": "blur_in"},
    "chapter": {"fonts": ["Space Grotesk", "Montserrat", "Inter"], "size": 0.034, "uppercase": True,
                "spacing": 0.012, "position": "upper_left", "animation": "typewriter"},
    "credit": {"fonts": ["Montserrat", "Inter"], "size": 0.03, "uppercase": True, "spacing": 0.006,
               "position": "bottom", "animation": "fade"},
    "handwritten": {"fonts": ["Permanent Marker", "DejaVu Sans"], "size": 0.08, "position": "center",
                    "animation": "pop", "shadow": 0.003},
}

ALIGN = {"lower_left": 1, "bottom": 2, "lower_right": 3, "left": 4, "center": 5, "right": 6,
         "upper_left": 7, "top": 8, "upper_right": 9}

ANIMATIONS_IN = ["none", "fade", "slide_up", "slide_down", "slide_left", "slide_right", "pop",
                 "zoom_in", "tracking_in", "blur_in", "typewriter", "words", "flicker"]
ANIMATIONS_OUT = ["none", "fade", "blur", "zoom"]


def _ts(t: float) -> str:
    t = max(t, 0.0)
    cs = round(t * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def _rgba(spec: str | None, default: str) -> tuple[str, float]:
    s = spec or default
    color, _, alpha = s.partition("@")
    opacity = float(alpha) if alpha else 1.0
    return color, 1.0 - opacity


class AssBuilder:
    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        self.styles: dict[str, str] = {}
        self.events: list[str] = []

    def style(self, name: str, st: dict) -> str:
        key = f"s{len(self.styles)}_{name}"
        h = self.h
        font = st.get("font") or pick_font(st.get("fonts", ["Inter"]))
        color, a = _rgba(st.get("color"), "#ffffff")
        ocolor, oa = _rgba(st.get("outline_color"), "#000000")
        box = st.get("box")
        if box:
            bcolor, ba = _rgba(box, "#000000@0.6")
            border_style, outline_c, back_c = 3, ass_color(bcolor, ba), ass_color(bcolor, ba)
            outline = max(st.get("box_padding", 0.012) * h, 1)
        else:
            border_style, outline_c, back_c = 1, ass_color(ocolor, oa), ass_color("#000000", 0.45)
            outline = st.get("outline", 0.0) * h
        size = st.get("size", 0.05) * h
        self.styles[key] = (
            f"Style: {key},{font},{size:.1f},{ass_color(color, a)},{ass_color(color, a)},"
            f"{outline_c},{back_c},{-1 if st.get('bold') else 0},{-1 if st.get('italic') else 0},0,0,"
            f"100,100,{st.get('spacing', 0.0) * h:.2f},0,{border_style},{outline:.2f},"
            f"{st.get('shadow', 0.0) * h:.2f},5,0,0,0,1"
        )
        return key

    def add(self, start: float, end: float, style: str, text: str, layer: int = 0) -> None:
        self.events.append(f"Dialogue: {layer},{_ts(start)},{_ts(end)},{style},,0,0,0,,{text}")

    def render(self) -> str:
        head = [
            "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {self.w}", f"PlayResY: {self.h}",
            "WrapStyle: 0", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            *self.styles.values(), "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        return "\n".join(head + self.events) + "\n"


def _position(st: dict, w: int, h: int) -> tuple[int, float, float]:
    pos = st.get("position", "center")
    mx, my = 0.07 * w, 0.09 * h
    if isinstance(pos, (list, tuple)):
        an, x, y = 5, pos[0] * w, pos[1] * h
    else:
        if pos not in ALIGN:
            raise VeditError(f"unknown text position {pos!r}. Use {', '.join(ALIGN)} or [x, y].")
        an = ALIGN[pos]
        col, row = (an - 1) % 3, (an - 1) // 3   # row 0 = bottom
        x = [mx, w / 2, w - mx][col]
        y = [h - my, h / 2, my][row]
    off = st.get("nudge", [0, 0])
    return an, x + off[0] * w, y + off[1] * h


def _markup(text: str, accent: str | None, base: str) -> list[tuple[str, bool]]:
    """Split '*word*' accents. Returns [(chunk, is_accent)]."""
    parts = re.split(r"(\*[^*]+\*)", text)
    out = []
    for p in parts:
        if not p:
            continue
        if p.startswith("*") and p.endswith("*") and len(p) > 2:
            out.append((p[1:-1], True))
        else:
            out.append((p, False))
    return out


def text_event(builder: AssBuilder, item: dict, start: float, end: float) -> None:
    style_name = item.get("style", "title")
    if style_name not in STYLES:
        raise VeditError(f"unknown text style {style_name!r}. Styles: {', '.join(STYLES)}")
    st = {**STYLES[style_name], **{k: v for k, v in item.items() if k not in ("text", "style")}}
    w, h = builder.w, builder.h
    text = str(item.get("text", ""))
    if st.get("uppercase"):
        text = re.sub(r"(\*[^*]+\*)|([^*]+)", lambda m: m.group(0).upper(), text)
    key = builder.style(style_name, st)
    an, x, y = _position(st, w, h)
    dur_ms = max(1, round((end - start) * 1000))
    tin = round(float(st.get("in_duration", 0.5)) * 1000)
    tout = round(float(st.get("out_duration", 0.4)) * 1000)
    anim = st.get("animation", "fade")
    out_anim = st.get("out", "fade")
    if anim not in ANIMATIONS_IN:
        raise VeditError(f"unknown text animation {anim!r}. In: {', '.join(ANIMATIONS_IN)}")
    if out_anim not in ANIMATIONS_OUT:
        raise VeditError(f"unknown text out animation {out_anim!r}. Out: {', '.join(ANIMATIONS_OUT)}")
    base_color = (st.get("color") or "#ffffff").partition("@")[0]
    accent = st.get("accent_color") or "#ffcc00"

    tags = [f"\\an{an}"]
    d = 0.045 * h
    fade_in = tin if anim in ("fade", "slide_up", "slide_down", "slide_left", "slide_right",
                              "tracking_in", "blur_in", "zoom_in") else (round(tin * 0.4) if anim == "pop" else 0)
    fade_out = tout if out_anim != "none" else 0
    if fade_in or fade_out:
        tags.append(f"\\fad({fade_in},{fade_out})")
    moves = {"slide_up": (0, d), "slide_down": (0, -d), "slide_left": (d * 1.5, 0), "slide_right": (-d * 1.5, 0)}
    if anim in moves:
        dx, dy = moves[anim]
        tags.append(f"\\move({x + dx:.0f},{y + dy:.0f},{x:.0f},{y:.0f},0,{tin})")
    else:
        tags.append(f"\\pos({x:.0f},{y:.0f})")
    spacing = st.get("spacing", 0.0) * h
    if anim == "pop":
        a, b = round(tin * 0.6), tin
        tags.append(f"\\fscx40\\fscy40\\t(0,{a},\\fscx112\\fscy112)\\t({a},{b},\\fscx100\\fscy100)")
    elif anim == "zoom_in":
        tags.append(f"\\fscx135\\fscy135\\t(0,{tin},0.5,\\fscx100\\fscy100)")
    elif anim == "tracking_in":
        tags.append(f"\\fsp{spacing + 0.05 * h:.1f}\\blur6\\t(0,{round(tin * 2.4)},0.35,\\fsp{spacing:.1f}\\blur0)")
    elif anim == "blur_in":
        tags.append(f"\\blur24\\t(0,{tin},0.6,\\blur0)")
    elif anim == "flicker":
        steps, t = [], 0
        for i, gap in enumerate([60, 50, 90, 40, 120, 60]):
            steps.append(f"\\t({t},{t + 1},\\alpha&H{'FF' if i % 2 == 0 else '00'}&)")
            t += gap
        tags.append("\\alpha&HFF&" + "".join(steps) + f"\\t({t},{t + 1},\\alpha&H00&)")
    if out_anim == "blur":
        tags.append(f"\\t({dur_ms - tout},{dur_ms},\\blur20)")
    elif out_anim == "zoom":
        tags.append(f"\\t({dur_ms - tout},{dur_ms},\\fscx125\\fscy125)")

    chunks = _markup(text, accent, base_color)
    body = ""
    if anim in ("typewriter", "words"):
        units: list[tuple[str, bool]] = []
        for chunk, acc in chunks:
            if anim == "typewriter":
                units += [(ch, acc) for ch in chunk]
            else:
                units += [(tok, acc) for tok in re.split(r"(\s+)", chunk) if tok]
        visible = [u for u in units if u[0].strip()]
        span = float(st.get("reveal", 0.035 if anim == "typewriter" else 0.0))
        if anim == "words" and not span:
            span = min(0.35, max(0.12, (end - start) * 0.5 / max(len(visible), 1)))
        k = 0
        for unit, acc in units:
            if not unit.strip():
                body += _esc(unit)
                continue
            t0 = round(k * span * 1000)
            col = ass_color(accent if acc else base_color)
            if anim == "words":
                body += (f"{{\\c{col}\\alpha&HFF&\\fscx70\\fscy70\\t({t0},{t0 + 1},\\alpha&H00&)"
                         f"\\t({t0},{t0 + 140},\\fscx108\\fscy108)\\t({t0 + 140},{t0 + 240},\\fscx100\\fscy100)}}"
                         f"{_esc(unit)}")
            else:
                body += f"{{\\c{col}\\alpha&HFF&\\t({t0},{t0 + 1},\\alpha&H00&)}}{_esc(unit)}"
            k += 1
    else:
        for chunk, acc in chunks:
            body += f"{{\\c{ass_color(accent if acc else base_color)}}}{_esc(chunk)}"

    sub = item.get("subtext")
    if sub:
        sub_size = st.get("size", 0.05) * h * float(st.get("subtext_scale", 0.55))
        sub_color = ass_color(st.get("subtext_color", base_color))
        body += f"\\N{{\\fs{sub_size:.0f}\\b0\\c{sub_color}\\alpha&H30&\\fsp{0.004 * h:.1f}}}{_esc(str(sub))}"
    builder.add(start, end, key, "{" + "".join(tags) + "}" + body, layer=int(item.get("layer", 1)))


# ----------------------------------------------------------------------------
# Captions from transcripts
# ----------------------------------------------------------------------------

def caption_events(builder: AssBuilder, plan: Plan, cfg: dict) -> int:
    transcripts = {}
    for key, path in (cfg.get("transcripts") or {}).items():
        data = json.loads(resolve_path(plan.base_dir, path).read_text())
        transcripts[key] = data
    if not transcripts:
        return 0
    style_name = cfg.get("style", "caption")
    max_chars = int(cfg.get("max_chars", 32 if style_name == "social" else 42))
    max_words = int(cfg.get("max_words", 4 if style_name == "social" else 12))
    accent = cfg.get("accent_color", "#ffd400")
    count = 0
    for clip in plan.clips:
        ref = clip.raw.get("source")
        data = transcripts.get(ref) or (transcripts.get(str(clip.path)) if clip.path else None)
        if not data or clip.volume == 0 or clip.raw.get("captions") is False:
            continue
        lo, hi = clip.src_in, clip.src_in + clip.src_span
        visible_from = clip.start + clip.transition.overlap_frames / plan.fps
        words = []
        for seg in data.get("segments", []):
            ws = seg.get("words") or [{"start": seg["start"], "end": seg["end"], "word": seg["text"]}]
            for wd in ws:
                if wd["start"] >= lo and wd["end"] <= hi + 0.05:
                    t0 = clip.start + (wd["start"] - lo) / clip.speed
                    t1 = clip.start + (min(wd["end"], hi) - lo) / clip.speed
                    if t0 >= visible_from - 0.05:
                        words.append((t0, t1, wd["word"].strip()))
        chunks, cur = [], []
        for wd in words:
            text_len = sum(len(x[2]) + 1 for x in cur) + len(wd[2])
            gap = wd[0] - cur[-1][1] if cur else 0
            if cur and (text_len > max_chars or len(cur) >= max_words or gap > 0.6
                        or cur[-1][2].endswith((".", "?", "!"))):
                chunks.append(cur)
                cur = []
            cur.append(wd)
        if cur:
            chunks.append(cur)
        for ch in chunks:
            start, end = ch[0][0], min(ch[-1][1] + 0.15, clip.end)
            item = {**{k: v for k, v in cfg.items() if k in STYLES["caption"] or k in
                       ("font", "color", "size", "box", "position", "nudge", "uppercase")},
                    "style": style_name}
            st = {**STYLES[style_name], **item}
            key = builder.style(style_name, st)
            an, x, y = _position(st, builder.w, builder.h)
            base = st.get("color", "#ffffff")
            body = ""
            for t0, t1, word in ch:
                wtxt = word.upper() if st.get("uppercase") else word
                if style_name == "social":
                    a = round((t0 - start) * 1000)
                    b = round((t1 - start) * 1000)
                    body += (f"{{\\c{ass_color(base)}\\t({a},{a + 1},\\c{ass_color(accent)})"
                             f"\\t({b},{b + 1},\\c{ass_color(base)})}}{_esc(wtxt)} ")
                else:
                    body += _esc(wtxt) + " "
            pop = "\\fscx85\\fscy85\\t(0,90,\\fscx100\\fscy100)" if style_name == "social" else ""
            builder.add(start, end, key, f"{{\\an{an}\\pos({x:.0f},{y:.0f}){pop}}}" + body.strip(), layer=2)
            count += 1
    return count


def build_ass(plan: Plan, path: Path) -> Path | None:
    items = plan.spec.get("text") or []
    captions = plan.spec.get("captions")
    if not items and not captions:
        return None
    b = AssBuilder(plan.output["width"], plan.output["height"])
    for item in items:
        start, end = plan.resolve_span(item, default_duration=3.0)
        if end > start:
            text_event(b, item, start, end)
    if captions:
        caption_events(b, plan, captions)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(b.render())
    return path
