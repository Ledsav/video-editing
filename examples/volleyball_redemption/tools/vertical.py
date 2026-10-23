"""Vertical (9:16, 1080x1920) version of the film for TikTok / Shorts / Reels.

The 16:9 film sits in the middle (1080x608) over a blurred, darkened, zoomed copy of itself; above it, the title (from the
end of the opening page on), replaced by the credits card on the ending page. Both stay inside the area TikTok leaves free
(its tabs cover the top ~150 px, its caption the bottom ~380 px, its buttons the right ~140 px from 900 px down).

  python3 tools/vertical.py [in.mp4] [out.mp4]
  (defaults: out/preview_anime_episode.mp4 -> out/volleyball_redemption_vertical.mp4)
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent.parent
src = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'out' / 'preview_anime_episode.mp4'
dst = Path(sys.argv[2]) if len(sys.argv) > 2 else root / 'out' / 'volleyball_redemption_vertical.mp4'
work = root / 'work' / 'vertical'
work.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1920
VH = 608                                   # the film's height at full width
VY = (H - VH) // 2                         # its top
OP_END, ED_START = 3.5, 26.2               # the opening page ends / the ending page begins (film time)
YELLOW, BLUE, INK, CREAM = (246, 195, 0), (31, 63, 168), (5, 7, 13), (241, 236, 224)

fonts = root / 'impact' / 'fonts'
JP = str(fonts / 'DelaGothicOne-Regular.ttf')
BRUSH = str(fonts / 'YujiBoku-Regular.ttf')
vfonts = Path.home() / '.local' / 'share' / 'fonts' / 'vedit'
TEXT_B = str(vfonts / 'montserrat-700-normal.ttf')
TEXT = str(vfonts / 'montserrat-500-normal.ttf')
DISPLAY = str(vfonts / 'anton-400-normal.ttf')


def text(d, xy, s, font, fill, stroke=0, stroke_fill=INK, anchor='ma', shadow=None):
    if shadow:
        for off, col in shadow:
            d.text((xy[0] + off, xy[1] + off), s, font=font, fill=col, stroke_width=stroke, stroke_fill=col, anchor=anchor)
    d.text(xy, s, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill, anchor=anchor)


# the title above the film: the logo, the romaji, the episode
top = Image.new('RGBA', (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(top)
cx = 470                                   # centred left of TikTok's button column
text(d, (cx, 250), '打ち返せ！', ImageFont.truetype(JP, 128), YELLOW, stroke=10, shadow=[(14, INK), (7, BLUE)])
text(d, (cx, 430), 'UCHIKAESE!', ImageFont.truetype(DISPLAY, 52), (255, 255, 255), stroke=4)
fj, fb_ = ImageFont.truetype(JP, 40), ImageFont.truetype(BRUSH, 48)                 # 第1話 in the logo face (the brush 1 reads as a 7)
a, b = '第1話', '「最後の一点」'
wa, wb = d.textlength(a, font=fj), d.textlength(b, font=fb_)
x = cx - (wa + 16 + wb) / 2
text(d, (x, 516), a, fj, YELLOW, stroke=5, anchor='la')
text(d, (x + wa + 16, 510), b, fb_, (255, 255, 255), stroke=5, anchor='la')
top.save(work / 'top.png')

# the credits card below the film (TASL attribution for the CC BY-NC material: title, author, source, licence, changes)
cr = Image.new('RGBA', (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(cr)
x0, y0, x1 = 50, 165, 900
d.rounded_rectangle((x0, y0, x1, VY - 18), 18, fill=(5, 7, 13, 225))
fh, fb, fs = ImageFont.truetype(TEXT_B, 28), ImageFont.truetype(TEXT_B, 24), ImageFont.truetype(TEXT, 22)
y = y0 + 22
text(d, ((x0 + x1) // 2, y), 'CREDITS', fh, YELLOW, anchor='ma')
y += 46
for head, lines in [('CHARACTER', ['VRoid "HairSample_Male" by pixiv (CC0)', 'volleyball kit by the author']),
                    ('MOTION CAPTURE', ['Motion Cast "Volley-ball" pack']),
                    ('CHEER MOTION', ['Bandai Namco Research Motiondataset-2,', 'Bandai Namco Research Inc. (CC BY-NC 4.0),', 'retargeted to the character']),
                    ('SONG', ['made with Suno'])]:
    d.text((x0 + 34, y), head, font=fb, fill=YELLOW)
    y += 31
    for ln in lines:
        d.text((x0 + 34, y), ln, font=fs, fill=CREAM)
        y += 28
    y += 9
assert y < VY - 18, f'credits overflow: {y}'
cr.save(work / 'credits.png')

fc = (
    f'[0:v]split[a][b];'
    f'[a]scale=-2:{H},crop={W}:{H},boxblur=28:2,eq=brightness=-0.22:saturation=1.2[bg];'
    f'[b]scale={W}:{VH}[fg];'
    f'[bg][fg]overlay=0:{VY}[v1];'
    f"[1:v]format=rgba,fade=t=in:st={OP_END}:d=0.3:alpha=1[t];"
    f"[2:v]format=rgba,fade=t=in:st={ED_START + 0.4}:d=0.4:alpha=1[c];"
    f"[v1][t]overlay=0:0:enable='between(t,{OP_END},{ED_START + 0.4})'[v2];"
    f"[v2][c]overlay=0:0:enable='gte(t,{ED_START + 0.4})',format=yuv420p[v]"
)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-loop', '1', '-i', str(work / 'top.png'), '-loop', '1', '-i', str(work / 'credits.png'),
                '-filter_complex', fc, '-map', '[v]', '-map', '0:a', '-shortest', '-c:v', 'libx264', '-crf', '20', '-preset', 'slow',
                '-r', '30', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(dst)], check=True)
print('wrote', dst)
