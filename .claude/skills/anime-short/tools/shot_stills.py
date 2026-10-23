"""Screenshots of one timeline clip of an edit (any html scene), with its params, as a labelled contact sheet.

  python3 shot_stills.py <project> <clip id> [t1,t2,...] [--size 960x540] [--set key=json ...] [--every 0.5]

Times are seconds inside the clip (default: 6 evenly spaced). --set overrides params for this look only
(e.g. --set debug=1 --set 'art=1'). Prints the sheet path and the scene's ANIME_TIMES (shot starts, impact times):
read the sheet before changing anything else, and before any render.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# the vedit toolkit: $VEDIT_REPO, else the current directory, else the repo this skill sits in (.claude/skills/<skill>)
REPO = Path(os.environ['VEDIT_REPO']) if os.environ.get('VEDIT_REPO') else \
    Path.cwd() if (Path.cwd() / 'mograph' / 'render.mjs').exists() else Path(__file__).resolve().parents[4]


def main(argv):
    ap = argparse.ArgumentParser(description='screenshots of one clip of an edit')
    ap.add_argument('project')
    ap.add_argument('clip')
    ap.add_argument('times', nargs='?', help='comma-separated seconds inside the clip')
    ap.add_argument('--size', default='960x540')
    ap.add_argument('--every', type=float, help='one still every N seconds')
    ap.add_argument('--set', action='append', default=[], help='param override key=json')
    ap.add_argument('--mocap', help='browse a mocap take instead of the clip\'s shots: the character plays it at real speed, '
                    'front three-quarter, labelled with take times (use --from / --to / --every)')
    ap.add_argument('--from', dest='t0', type=float, default=0)
    ap.add_argument('--to', dest='t1', type=float)
    ap.add_argument('--orbit', type=float, default=30, help='--mocap camera: degrees around the character (0 = front)')
    a = ap.parse_args(argv)
    proj, cid = Path(a.project).resolve(), a.clip
    spec = json.loads((proj / 'edit.json').read_text())
    clip = next((c for c in spec['timeline'] if c.get('id') == cid), None)
    if not clip:
        print(f"no clip '{cid}' in {proj / 'edit.json'} (ids: {[c.get('id') for c in spec['timeline']]})")
        return 1
    html = proj / clip['html']
    params = dict(clip.get('params', {}))
    for kv in a.set:
        k, v = kv.split('=', 1)
        try:
            params[k] = json.loads(v)
        except json.JSONDecodeError:
            params[k] = v
    dur = float(clip.get('duration') or re.search(r'vedit:duration" content="([\d.]+)', html.read_text()).group(1))
    offset = 0
    if a.mocap:   # one shot playing the take from --from to --to at real speed
        t1 = a.t1 if a.t1 is not None else a.t0 + 8
        dur, offset = t1 - a.t0, a.t0
        params.update(clips={'take': a.mocap}, debug=1, shots=[{'name': 'take', 'dur': dur, 'clip': 'take', 'from': a.t0, 'to': t1, 'place': {'anchor': True},
                      'cam': {'target': 'Hips', 'orbit': a.orbit, 'dist': 4.2, 'height': 0.35, 'lookY': 0.1, 'fov': 40}}])
        params['subframes'] = 1
    if a.times:
        times = [float(t) for t in a.times.split(',')]
    else:
        step = a.every or dur / 6
        times = [round(min(dur - 0.04, step * (i + 0.5)), 3) for i in range(max(1, round(dur / step)))]
    w, h = (int(x) for x in a.size.split('x'))
    out = proj / 'work' / 'stills'
    out.mkdir(parents=True, exist_ok=True)
    prefix = out / (f'take_{Path(a.mocap).stem}' if a.mocap else cid)
    r = subprocess.run(['node', str(REPO / 'mograph' / 'render.mjs'), '--html', str(html), '--out', str(prefix),
                        '--width', str(w), '--height', str(h), '--duration', f'{dur:.4f}', '--stills', ','.join(f'{t:.4f}' for t in times),
                        '--params', json.dumps(params)], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if 'ANIME_TIMES ' in line and not a.mocap and not a.set:   # the clip's real timing (not a --set look), for the sound plans
            (proj / 'work' / 'anime_times').mkdir(parents=True, exist_ok=True)
            (proj / 'work' / 'anime_times' / f'{cid}.json').write_text(line.split('ANIME_TIMES ', 1)[1].strip() + '\n')
        if 'ANIME_TIMES' in line or 'ERR' in line or 'error' in line.lower() or 'CLIP ' in line or 'note' in line or 'MATERIAL ' in line:
            print(line.replace('[page console] ', ''))
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:])
        return r.returncode
    if any('[page error]' in ln or ' ERR ' in f' {ln}' for ln in r.stderr.splitlines()):
        print('SCENE ERROR: the page failed (see above); these stills are not valid')
        return 1
    files = json.loads(r.stdout.strip().splitlines()[-1])
    cols = 3 if len(files) > 4 else len(files)
    rows = (len(files) + cols - 1) // cols
    tw, th = 640, int(640 * h / w)
    sheet = Image.new('RGB', (cols * tw, rows * (th + 34)), (16, 16, 20))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 20)
    except OSError:
        font = ImageFont.load_default()
    for i, (f, t) in enumerate(zip(files, times)):
        x, y = (i % cols) * tw, (i // cols) * (th + 34)
        sheet.paste(Image.open(f).convert('RGB').resize((tw, th)), (x, y + 34))
        d.text((x + 10, y + 6), f'take t = {t + offset:.2f} s' if a.mocap else f'{cid}  t = {t:.2f} s', fill=(240, 220, 120), font=font)
    path = out / (f'take_{Path(a.mocap).stem}_{a.t0:g}.png' if a.mocap else f'{cid}_sheet.png')
    sheet.save(path)
    print(path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
