"""9:16 (1080x1920) version of a 16:9 film for TikTok / Shorts / Reels.

The film sits in the middle (1080x608) over a blurred, darkened, zoomed copy of itself; above it the title (from the end of
the opening page on), replaced by a credits card on the ending page. Both stay inside the area TikTok leaves free: its tabs
cover the top ~150 px, its caption the bottom ~380 px, its buttons the right ~140 px from 900 px down.

  python3 vertical.py <project>/vertical.json

vertical.json (times: seconds or references, see audio.py):
  {
    "src": "out/anime_short.mp4", "dst": "out/anime_short_vertical.mp4",
    "title": {"jp": "打ち返せ！", "romaji": "UCHIKAESE!", "ep": "第1話", "epTitle": "「最後の一点」"},
    "title_from": "op:end",                 // default: the end of the first clip
    "credits_from": "ed+0.4",               // default: 0.4 s into the last clip
    "credits": [["CHARACTER", ["VRoid \\"HairSample_Male\\" by pixiv (CC0)"]], ["MOTION CAPTURE", ["CMU Graphics Lab (mocap.cs.cmu.edu)"]]],
    "colors": {"accent": "#f6c300", "band": "#1f3fa8"}
  }
Re-render a true 9:16 edit instead (output 1080x1920) when the action needs the full height: scenes use vw/vh units.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

from audio import Project

W, H = 1080, 1920
VH = 608
VY = (H - VH) // 2
INK, CREAM = (5, 7, 13), (241, 236, 224)


def font(paths, size):
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def text(d, xy, s, f, fill, stroke=0, anchor='ma', shadow=None):
    for off, col in shadow or []:
        d.text((xy[0] + off, xy[1] + off), s, font=f, fill=col, stroke_width=stroke, stroke_fill=col, anchor=anchor)
    d.text(xy, s, font=f, fill=fill, stroke_width=stroke, stroke_fill=INK, anchor=anchor)


def main(path):
    plan_path = Path(path).resolve()
    plan = json.loads(plan_path.read_text())
    proj = Project(plan_path.parent)
    src, dst = proj.path(plan.get('src', 'out/anime_short.mp4')), proj.path(plan.get('dst', 'out/anime_short_vertical.mp4'))
    work = proj.path('work/vertical')
    work.mkdir(parents=True, exist_ok=True)
    ids = list(proj.starts)
    t_title = proj.t(plan.get('title_from', f'{ids[0]}:end'))
    t_cred = proj.t(plan.get('credits_from', f'{ids[-1]}+0.4'))
    col = {k: ImageColor.getrgb(v) for k, v in {'accent': '#f6c300', 'band': '#1f3fa8', **plan.get('colors', {})}.items()}
    fonts = proj.path('assets/fonts')
    vf = Path.home() / '.local' / 'share' / 'fonts' / 'vedit'
    JP = [fonts / 'DelaGothicOne-Regular.ttf']
    BRUSH = [fonts / 'YujiBoku-Regular.ttf']
    BOLD, REG, DISPLAY = [vf / 'montserrat-700-normal.ttf'], [vf / 'montserrat-500-normal.ttf'], [vf / 'anton-400-normal.ttf']

    T = plan.get('title', {})
    top = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(top)
    cx = 470                                                        # centred left of TikTok's button column
    if T.get('jp'):
        fj = font(JP, 128)
        while d.textlength(T['jp'], font=fj) > 820 and fj.size > 60:
            fj = font(JP, fj.size - 8)
        text(d, (cx, 250), T['jp'], fj, col['accent'], stroke=10, shadow=[(14, INK), (7, col['band'])])
    if T.get('romaji'):
        text(d, (cx, 430), T['romaji'], font(DISPLAY, 52), (255, 255, 255), stroke=4)
    if T.get('ep') or T.get('epTitle'):
        fe, fb = font(JP, 40), font(BRUSH, 48)                     # the episode number in the logo face (brush digits misread)
        a, b = T.get('ep', ''), T.get('epTitle', '')
        wa, wb = d.textlength(a, font=fe), d.textlength(b, font=fb)
        x = cx - (wa + 16 + wb) / 2
        text(d, (x, 516), a, fe, col['accent'], stroke=5, anchor='la')
        text(d, (x + wa + 16, 510), b, fb, (255, 255, 255), stroke=5, anchor='la')
    top.save(work / 'top.png')

    # the credits card (TASL attribution: title, author, source, licence, changes)
    cr = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(cr)
    x0, y0, x1 = 50, 165, 900
    d.rounded_rectangle((x0, y0, x1, VY - 18), 18, fill=(5, 7, 13, 225))
    fh, fb, fs = font(BOLD, 28), font(BOLD, 24), font(REG, 22)
    rows = sum(1 + len(lines) for _, lines in plan.get('credits', []))
    if rows > 14:                                                   # long credits: smaller type
        fb, fs = font(BOLD, 20), font(REG, 18)
    lh = fs.size + 6
    y = y0 + 22
    text(d, ((x0 + x1) // 2, y), 'CREDITS', fh, col['accent'])
    y += 46
    for head, lines in plan.get('credits', []):
        d.text((x0 + 34, y), head, font=fb, fill=col['accent'])
        y += fb.size + 7
        for ln in lines:
            d.text((x0 + 34, y), ln, font=fs, fill=CREAM)
            y += lh
        y += 9
    if y > VY - 18:
        sys.exit(f'credits overflow ({y} > {VY - 18} px): shorten them')
    cr.save(work / 'credits.png')

    fc = (f'[0:v]split[a][b];[a]scale=-2:{H},crop={W}:{H},boxblur=28:2,eq=brightness=-0.22:saturation=1.2[bg];[b]scale={W}:{VH}[fg];'
          f'[bg][fg]overlay=0:{VY}[v1];[1:v]format=rgba,fade=t=in:st={t_title}:d=0.3:alpha=1[t];[2:v]format=rgba,fade=t=in:st={t_cred}:d=0.4:alpha=1[c];'
          f"[v1][t]overlay=0:0:enable='between(t,{t_title},{t_cred})'[v2];[v2][c]overlay=0:0:enable='gte(t,{t_cred})',format=yuv420p[v]")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-loop', '1', '-i', str(work / 'top.png'), '-loop', '1', '-i', str(work / 'credits.png'),
                    '-filter_complex', fc, '-map', '[v]', '-map', '0:a?', '-shortest', '-c:v', 'libx264', '-crf', '20', '-preset', 'slow',
                    '-r', '30', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(dst)], check=True)
    print('wrote', dst)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])
