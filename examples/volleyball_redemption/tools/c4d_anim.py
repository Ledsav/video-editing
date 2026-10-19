"""Extract joint animation (PSR keyframes) from a Cinema 4D .c4d file (QC4DC4D6, big-endian typed stream).

Reverse-engineered layout (enough for Motion Cast mocap files):
  * strings are UTF-16BE; a joint is "<name>" followed by the type label "Articulation"
  * each animated joint is PRECEDED by its 9 CTrack blocks, labelled "Position . X/Y/Z", "Echelle . X/Y/Z", "Rotation . H/P/B"
  * a CKey record (type id 0x14E8) holds:  01 00 01 af 50 00 00 00 04
        16 <f64 num> <f64 den>   key time  = num/den seconds
        16 <f64> <f64>           left tangent time
        16 <f64> <f64>           right tangent time
        13 <f64 value>           key value  (positions in cm, rotations in radians)
"""
import json, os, re, struct, sys

TRACKS = ['Position . X', 'Position . Y', 'Position . Z', 'Échelle . X', 'Échelle . Y', 'Échelle . Z', 'Rotation . H', 'Rotation . P', 'Rotation . B']
KEY = re.compile(rb'\x01\x00\x01\xaf[\x50-\x53]\x00\x00\x00\x04\x16(.{8})(.{8})\x16.{16}\x16.{16}\x13(.{8})', re.S)


def strings(d):
    return [(m.start(), m.group().decode('utf-16be', 'replace'))
            for m in re.finditer(rb'(?:\x00[ -~]|\x00[\xc0-\xff]){3,}', d)]


def parse(path):
    d = open(path, 'rb').read()
    S = strings(d)
    joints, order = {}, []
    names = [i - 1 for i, (o, s) in enumerate(S) if s == 'Articulation' and i > 0]
    prev_end = 0                                  # tracks are written BEFORE the joint name they belong to
    for ni in names:
        name_off = S[ni][0]
        labels = [(o, s) for (o, s) in S if prev_end <= o < name_off and s in TRACKS]
        tracks = {}
        for k, (toff, lab) in enumerate(labels):
            end = labels[k + 1][0] if k + 1 < len(labels) else name_off
            keys = []
            for m in KEY.finditer(d, toff, end):
                num, den, val = (struct.unpack('>d', g)[0] for g in m.groups())
                keys.append((num / den if den else 0.0, val))
            tracks[lab.replace('Échelle', 'Scale')] = keys
        name = S[ni][1].strip().lstrip('"').strip()
        joints[name] = tracks
        order.append(name)
        prev_end = S[ni + 1][0]                   # after this joint's "Articulation" label
    return order, joints


# ---------------------------------------------------------------------------------------------
# Conversion to glTF (.glb): skeleton + baked animation.
#   C4D local rotation = Ry(-H) * Rx(-P) * Rz(-B) in C4D's left-handed space (found by minimising
#   foot slide over all 96 order/sign/handedness combinations); converted to right-handed by
#   mirroring Z (R' = M R M, t' = M t, M = diag(1, 1, -1)); centimetres -> metres.
# ---------------------------------------------------------------------------------------------
import math

PARENTS_MC = {'Hip': None, 'LowerSpine': 'Hip', 'MiddleSpine': 'LowerSpine', 'Chest': 'MiddleSpine', 'Neck': 'Chest',
              'Head': 'Neck', 'Head_end': 'Head', 'LClavicle': 'Chest', 'LShoulder': 'LClavicle', 'LForearm': 'LShoulder',
              'LHand': 'LForearm', 'RClavicle': 'Chest', 'RShoulder': 'RClavicle', 'RForearm': 'RShoulder', 'RHand': 'RForearm',
              'RThigh': 'Hip', 'RShin': 'RThigh', 'RFoot': 'RShin', 'RToe': 'RFoot', 'RToe_end': 'RToe',
              'LThigh': 'Hip', 'LShin': 'LThigh', 'LFoot': 'LShin', 'LToe': 'LFoot', 'LToe_end': 'LToe'}
for side, hand in (('Left', 'LHand'), ('Right', 'RHand')):          # fingers: Finger{i} -> {i}1 -> {i}2 -> {i}2_end
    for i in range(5):
        PARENTS_MC[f'{side}Finger{i}'] = hand
        PARENTS_MC[f'{side}Finger{i}1'] = f'{side}Finger{i}'
        PARENTS_MC[f'{side}Finger{i}2'] = f'{side}Finger{i}1'
        PARENTS_MC[f'{side}Finger{i}2_end'] = f'{side}Finger{i}2'


def _mat(h, p, b):
    def rx(a): c, s = math.cos(a), math.sin(a); return [[1, 0, 0], [0, c, -s], [0, s, c]]
    def ry(a): c, s = math.cos(a), math.sin(a); return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    def rz(a): c, s = math.cos(a), math.sin(a); return [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    mm = lambda A, B: [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mm(mm(ry(-h), rx(-p)), rz(-b))


def _quat(R):  # rotation matrix -> (x, y, z, w)
    t = R[0][0] + R[1][1] + R[2][2]
    if t > 0:
        s = math.sqrt(t + 1) * 2; return ((R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s, s / 4)
    if R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = math.sqrt(1 + R[0][0] - R[1][1] - R[2][2]) * 2; return (s / 4, (R[0][1] + R[1][0]) / s, (R[0][2] + R[2][0]) / s, (R[2][1] - R[1][2]) / s)
    if R[1][1] > R[2][2]:
        s = math.sqrt(1 + R[1][1] - R[0][0] - R[2][2]) * 2; return ((R[0][1] + R[1][0]) / s, s / 4, (R[1][2] + R[2][1]) / s, (R[0][2] - R[2][0]) / s)
    s = math.sqrt(1 + R[2][2] - R[0][0] - R[1][1]) * 2; return ((R[0][2] + R[2][0]) / s, (R[1][2] + R[2][1]) / s, s / 4, (R[1][0] - R[0][1]) / s)


def to_glb(order, joints, out_path, clip_name='take', parents=PARENTS_MC):
    names = [n for n in order if n in parents]
    idx = {n: i for i, n in enumerate(names)}
    ref = joints['Hip']['Rotation . H']
    times = [t for t, _ in ref]
    nf = len(times)
    def v(n, k, f, d=0.0):
        t = joints.get(n, {}).get(k); return t[f][1] if t else d
    trs = {n: [] for n in names}
    for n in names:
        for f in range(nf):
            R = _mat(v(n, 'Rotation . H', f), v(n, 'Rotation . P', f), v(n, 'Rotation . B', f))
            Rr = [[R[0][0], R[0][1], -R[0][2]], [R[1][0], R[1][1], -R[1][2]], [-R[2][0], -R[2][1], R[2][2]]]   # M R M
            q = _quat(Rr)
            p = (v(n, 'Position . X', f) * 0.01, v(n, 'Position . Y', f) * 0.01, -v(n, 'Position . Z', f) * 0.01)
            trs[n].append((p, q))
    # keep quaternions continuous (no sign flips between frames)
    for n in names:
        for f in range(1, nf):
            (p, q), (_, q0) = trs[n][f], trs[n][f - 1]
            if sum(a * b for a, b in zip(q, q0)) < 0: trs[n][f] = (p, tuple(-c for c in q))
    nodes = []
    for n in names:
        p, q = trs[n][0]
        kids = [idx[c] for c in names if parents.get(c) == n]
        node = {'name': n, 'translation': list(p), 'rotation': list(q)}
        if kids: node['children'] = kids
        nodes.append(node)
    blob = bytearray(); views = []; accs = []
    def add(arr, comp, typ, mn=None, mx=None):
        off = len(blob); blob.extend(struct.pack('<%df' % len(arr), *arr))
        while len(blob) % 4: blob.append(0)
        views.append({'buffer': 0, 'byteOffset': off, 'byteLength': len(arr) * 4})
        a = {'bufferView': len(views) - 1, 'componentType': 5126, 'count': len(arr) // comp, 'type': typ}
        if mn is not None: a['min'], a['max'] = mn, mx
        accs.append(a); return len(accs) - 1
    t0 = times[0]
    ta = add([t - t0 for t in times], 1, 'SCALAR', [0.0], [times[-1] - t0])
    samplers, channels = [], []
    for n in names:
        pa = add([c for p, _ in trs[n] for c in p], 3, 'VEC3')
        qa = add([c for _, q in trs[n] for c in q], 4, 'VEC4')
        for path, acc in (('translation', pa), ('rotation', qa)):
            samplers.append({'input': ta, 'output': acc, 'interpolation': 'LINEAR'})
            channels.append({'sampler': len(samplers) - 1, 'target': {'node': idx[n], 'path': path}})
    # --- stand the skeleton up: the C4D parent object is rotated, so find "up" from the body itself ---
    def fk(f):
        W = {}
        for n in names:
            (p, q) = trs[n][f]; x, y, z, w = q
            R = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                 [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                 [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
            par = parents.get(n)
            if par is None or par not in W: W[n] = (R, list(p))
            else:
                Rp, pp = W[par]
                W[n] = ([[sum(Rp[i][k] * R[k][j] for k in range(3)) for j in range(3)] for i in range(3)],
                        [pp[i] + sum(Rp[i][k] * p[k] for k in range(3)) for i in range(3)])
        return {n: w[1] for n, w in W.items()}
    sub = lambda a, b: [a[i] - b[i] for i in range(3)]
    norm = lambda a: (lambda l: [c / l for c in a])(math.sqrt(sum(c * c for c in a)) or 1)
    cross = lambda a, b: [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    ups = []
    for f in range(0, nf, max(1, nf // 12)):
        W = fk(f); feet = [(W['LFoot'][i] + W['RFoot'][i]) / 2 for i in range(3)]; ups.append(norm(sub(W['Head'], feet)))
    up = norm([sum(u[i] for u in ups) for i in range(3)])
    W0, W1 = fk(0), fk(nf // 2)
    fwd = sub(W1['Hip'], W0['Hip']); d = sum(fwd[i] * up[i] for i in range(3)); fwd = [fwd[i] - d * up[i] for i in range(3)]
    if math.sqrt(sum(c * c for c in fwd)) < 1e-3:                           # standing clip: face the toes
        fwd = sub(W0['LToe'], W0['LFoot']); d = sum(fwd[i] * up[i] for i in range(3)); fwd = [fwd[i] - d * up[i] for i in range(3)]
    fwd = norm(fwd); left = cross(up, fwd)       # facing +Z with +Y up, the athlete's left is +X (glTF/three.js convention)
    Rw = [left, up, fwd]                         # rows: world -> upright (a proper rotation, det = +1)
    root_q = _quat(Rw)
    nodes.append({'name': 'mocap_root', 'rotation': list(root_q), 'children': [idx[n] for n in names if parents.get(n) is None]})
    roots = [len(nodes) - 1]
    gl = {'asset': {'version': '2.0', 'generator': 'c4d_anim.py (reverse-engineered C4D reader)'},
          'scene': 0, 'scenes': [{'nodes': roots}], 'nodes': nodes,
          'animations': [{'name': clip_name, 'samplers': samplers, 'channels': channels}],
          'buffers': [{'byteLength': len(blob)}], 'bufferViews': views, 'accessors': accs}
    js = json.dumps(gl, separators=(',', ':')).encode()
    while len(js) % 4: js += b' '
    out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob))
    out += struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(blob), 0x004E4942) + bytes(blob)
    open(out_path, 'wb').write(out)
    return len(names), nf, times[-1] - t0


if __name__ == '__main__':
    # usage: c4d_anim.py in.c4d [out.glb]
    order, joints = parse(sys.argv[1])
    print(len(order), 'joints,', sum(1 for n in order if joints[n]), 'animated')
    if len(sys.argv) > 2:
        n, nf, dur = to_glb(order, joints, sys.argv[2], clip_name=os.path.splitext(os.path.basename(sys.argv[1]))[0])
        print(f'wrote {sys.argv[2]}: {n} joints, {nf} frames, {dur:.2f} s')
