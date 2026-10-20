// Mocap (Motion Cast skeleton, converted by tools/c4d_anim.py) -> Mixamo-rigged character, per frame.
// Limbs and fingers are aimed bone by bone (swing from the current pose, parents first); hips, chest and
// hands are solved from two directions so the body faces and the palm turns like the capture.

async function loadMocap(THREE, GLTFLoader, file) {
  const g = await loadGLB(GLTFLoader, file);
  const root = g.scene, clip = g.animations[0], mixer = new THREE.AnimationMixer(root);
  mixer.clipAction(clip).play();
  const nodes = {}; root.traverse((o) => { if (o.name) nodes[o.name] = o; });
  const dur = clip.duration - 1 / 60;                  // the last key loops back to the first: drop it
  function raw(t) {
    mixer.setTime(Math.min(Math.max(t, 0), dur)); root.updateMatrixWorld(true);
    const P = {}; for (const n in nodes) P[n] = new THREE.Vector3().setFromMatrixPosition(nodes[n].matrixWorld);
    // Head_end sits on the head joint in these captures: rebuild it 20 cm up the head's own axis so the head pitch survives
    if (nodes.Head && P.Head_end && P.Head_end.distanceTo(P.Head) < 1e-4) P.Head_end = new THREE.Vector3(0, 0.2, 0).applyMatrix4(nodes.Head.matrixWorld);
    return P;
  }
  // bake every captured frame, then low-pass it (zero phase): marker noise reads as jitter, worst in slow motion.
  // Fingers are smoothed as offsets from their hand, so the hand keeps its speed and the fingers stop trembling.
  const fps = 60, n = Math.floor(dur * fps), F = [];
  for (let i = 0; i <= n; i++) F.push(raw(i / fps));
  const names = Object.keys(F[0]);
  const handOf = (nm) => nm.startsWith('LeftFinger') ? 'LHand' : nm.startsWith('RightFinger') ? 'RHand' : null;
  const sigmaOf = (nm) => handOf(nm) ? 3 : /Hand/.test(nm) ? 2 : /Forearm/.test(nm) ? 1.5 : 1.2;
  const S = F.map(() => ({}));
  const blur = (get, sigma, put) => { const r = Math.ceil(sigma * 3), w = []; for (let k = -r; k <= r; k++) w.push(Math.exp(-k * k / (2 * sigma * sigma)));
    for (let i = 0; i <= n; i++) { const v = new THREE.Vector3(); let ws = 0;
      for (let k = -r; k <= r; k++) { const j = Math.min(n, Math.max(0, i + k)); v.addScaledVector(get(j), w[k + r]); ws += w[k + r]; }
      put(i, v.divideScalar(ws)); } };
  for (const nm of names) if (!handOf(nm)) blur((j) => F[j][nm], sigmaOf(nm), (i, v) => (S[i][nm] = v));
  for (const nm of names) { const h = handOf(nm); if (h && F[0][h]) blur((j) => F[j][nm].clone().sub(F[j][h]), sigmaOf(nm), (i, v) => (S[i][nm] = v.add(S[i][h]))); }
  // Catmull-Rom between baked frames: no velocity kinks when a shot stretches one captured frame over several video frames
  const cache = new Map();
  function sample(t) {
    const k = Math.round(Math.min(Math.max(t, 0), dur) * 600);   // 0.1 frame cache
    if (cache.has(k)) return cache.get(k);
    const x = Math.min(k / 600 * fps, n), i = Math.min(Math.floor(x), n - 1), u = x - i, u2 = u * u, u3 = u2 * u;
    const f0 = S[Math.max(0, i - 1)], f1 = S[i], f2 = S[i + 1], f3 = S[Math.min(n, i + 2)];
    const c0 = -0.5 * u3 + u2 - 0.5 * u, c1 = 1.5 * u3 - 2.5 * u2 + 1, c2 = -1.5 * u3 + 2 * u2 + 0.5 * u, c3 = 0.5 * u3 - 0.5 * u2;
    const P = {}; for (const nm of names) P[nm] = new THREE.Vector3().addScaledVector(f0[nm], c0).addScaledVector(f1[nm], c1).addScaledVector(f2[nm], c2).addScaledVector(f3[nm], c3);
    if (cache.size > 4000) cache.clear(); cache.set(k, P); return P;
  }
  // events: floor, takeoff, contact (highest right hand while airborne), landing
  const low = [];
  for (let i = 0; i <= n; i++) { const P = F[i]; low.push(Math.min(P.LToe.y, P.RToe.y, P.LFoot.y, P.RFoot.y)); }
  const floor = [...low].sort((a, b) => a - b)[Math.floor(low.length * 0.05)];
  let best = [0, 0], s = -1;
  for (let i = 0; i <= n + 1; i++) {
    const air = i <= n && low[i] > floor + 0.1;
    if (air && s < 0) s = i;
    if (!air && s >= 0) { if (i - s > best[1] - best[0]) best = [s, i]; s = -1; }
  }
  let contact = best[0], hy = -1e9;
  for (let i = best[0]; i < best[1]; i++) { const y = F[i].RHand.y; if (y > hy) { hy = y; contact = i; } }
  return { sample, dur, floor, takeoff: best[0] / fps, land: best[1] / fps, contact: contact / fps, airborne: best[1] > best[0] };
}

function makeRetarget(THREE, model, bone) {
  const V = () => new THREE.Vector3(), Q = () => new THREE.Quaternion();
  const wpos = (b) => V().setFromMatrixPosition(b.matrixWorld);
  const bones = []; model.traverse((o) => { if (o.isBone) bones.push(o); });
  const rest = new Map(bones.map((b) => [b, b.quaternion.clone()]));
  const restHipLocal = bone('Hips').position.clone();
  model.updateMatrixWorld(true);
  const ARM = {}; for (const s of ['Left', 'Right']) ARM[s] = wpos(bone(`${s}Arm`)).distanceTo(wpos(bone(`${s}ForeArm`))) + wpos(bone(`${s}ForeArm`)).distanceTo(wpos(bone(`${s}Hand`)));
  const FING = { Thumb: 0, Index: 1, Middle: 2, Ring: 3, Pinky: 4 };
  // [anime bone, anime child, mocap from, mocap to]
  const chain = [['Spine', 'Spine1', 'LowerSpine', 'MiddleSpine'], ['Spine1', 'Spine2', 'MiddleSpine', 'Chest']];
  const neck = [['Neck', 'Head', 'Neck', 'Head'], ['Head', 'HeadTop_End', 'Head', 'Head_end']];
  const limbs = [];
  for (const [s, m, F] of [['Left', 'L', 'Left'], ['Right', 'R', 'Right']]) {
    limbs.push([`${s}Shoulder`, `${s}Arm`, `${m}Clavicle`, `${m}Shoulder`], [`${s}Arm`, `${s}ForeArm`, `${m}Shoulder`, `${m}Forearm`],
      [`${s}ForeArm`, `${s}Hand`, `${m}Forearm`, `${m}Hand`]);
    limbs.push([`${s}UpLeg`, `${s}Leg`, `${m}Thigh`, `${m}Shin`], [`${s}Leg`, `${s}Foot`, `${m}Shin`, `${m}Foot`], [`${s}Foot`, `${s}ToeBase`, `${m}Foot`, `${m}Toe`]);
  }
  const fingers = [];
  for (const [s, F] of [['Left', 'Left'], ['Right', 'Right']])
    for (const f in FING) { const i = FING[f];
      fingers.push([`${s}Hand${f}1`, `${s}Hand${f}2`, `${F}Finger${i}`, `${F}Finger${i}1`], [`${s}Hand${f}2`, `${s}Hand${f}3`, `${F}Finger${i}1`, `${F}Finger${i}2`]); }
  const ok = (r) => bone(r[0]) && bone(r[1]);
  const LIM = limbs.filter(ok), FIN = fingers.filter(ok), CH = chain.filter(ok), NK = neck.filter(ok);

  const setWorldQ = (b, qw) => { const pq = Q(); b.parent.getWorldQuaternion(pq); b.quaternion.copy(pq.invert().multiply(qw)); b.updateMatrixWorld(true); };
  function swing(b, c, dir) {
    if (dir.lengthSq() < 1e-8) return;
    b.updateMatrixWorld(true); const cur = wpos(c).sub(wpos(b)); if (cur.lengthSq() < 1e-10) return;
    const q = Q().setFromUnitVectors(cur.normalize(), dir.clone().normalize());
    const bq = Q(); b.getWorldQuaternion(bq); setWorldQ(b, q.multiply(bq));
  }
  const basis = (p, s) => { const y = p.clone().normalize(), z = V().crossVectors(s, y).normalize(), x = V().crossVectors(y, z); return Q().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, z)); };
  function twoVec(b, curP, curS, tgtP, tgtS) {     // rotate b so (curP, curS) -> (tgtP, tgtS)
    const d = basis(tgtP, tgtS).multiply(basis(curP, curS).invert());
    const bq = Q(); b.getWorldQuaternion(bq); setWorldQ(b, d.multiply(bq));
  }
  const D = (M, a, b) => M[b].clone().sub(M[a]);
  // two-bone IK: a (root) -> b (mid) -> c (end) reaches target, bending towards pole
  function twoBone(a, b, c, target, pole) {
    if (!a || !b || !c) return;
    a.updateMatrixWorld(true);
    const A = wpos(a), B = wpos(b), C = wpos(c), la = A.distanceTo(B), lb = B.distanceTo(C);
    const toT = target.clone().sub(A), d = Math.min(Math.max(toT.length(), Math.abs(la - lb) + 1e-4), la + lb - 1e-4);
    const dir = toT.normalize();
    let pv = pole.clone().sub(A); pv.sub(dir.clone().multiplyScalar(pv.dot(dir)));
    if (pv.lengthSq() < 1e-8) { pv = B.clone().sub(A); pv.sub(dir.clone().multiplyScalar(pv.dot(dir))); }
    pv.normalize();
    const cosA = (la * la + d * d - lb * lb) / (2 * la * d), sinA = Math.sqrt(Math.max(0, 1 - cosA * cosA));
    const E = A.clone().add(dir.clone().multiplyScalar(cosA * la)).add(pv.multiplyScalar(sinA * la));
    swing(a, b, E.clone().sub(A));
    b.updateMatrixWorld(true);
    swing(b, c, A.clone().add(dir.clone().multiplyScalar(d)).sub(wpos(b)));
  }
  // the rig has no forearm twist bones: a wrist turned far from its rest roll collapses the skin ("candy wrapper").
  // Keep the hand's roll about its own long axis (towards the middle finger) within +-limit of rest.
  const MAX_WRIST_TWIST = 1.0, MAX_WRIST_BEND = 0.8;
  // and keep the hand within MAX_WRIST_BEND of the forearm's line: past that the wrist reads as broken
  function limitBend(h, child, fore, limit) {
    h.updateMatrixWorld(true);
    const f = wpos(h).sub(wpos(fore)).normalize(), d = wpos(child).sub(wpos(h)).normalize(), a = f.angleTo(d);
    if (a <= limit) return;
    const axis = V().crossVectors(d, f); if (axis.lengthSq() < 1e-10) return;
    const q = Q().setFromAxisAngle(axis.normalize(), a - limit), bq = Q(); h.getWorldQuaternion(bq); setWorldQ(h, q.multiply(bq));
  }
  function limitTwist(b, child, limit) {
    const r = rest.get(b), q = b.quaternion, d = r.clone().invert().multiply(q);           // rotation since rest, in rest space
    const axis = child.position.clone().normalize();                                         // long axis, in the bone's own space
    let th = 2 * Math.atan2(V().set(d.x, d.y, d.z).dot(axis), d.w); if (th > Math.PI) th -= 2 * Math.PI; if (th < -Math.PI) th += 2 * Math.PI;
    if (Math.abs(th) <= limit) return;
    const swingQ = d.clone().multiply(Q().setFromAxisAngle(axis, th).invert());                // d = swing * twist
    const keep = Q().setFromAxisAngle(axis, Math.sign(th) * limit);
    b.quaternion.copy(r.clone().multiply(swingQ).multiply(keep)); b.updateMatrixWorld(true);
  }

  // M: mocap world positions; xf(v) maps a mocap point into the scene (scale + offset)
  return function apply(M, xf) {
    bones.forEach((b) => b.quaternion.copy(rest.get(b)));
    const hips = bone('Hips'); hips.position.copy(restHipLocal); model.updateMatrixWorld(true);
    // root position
    const hw = xf(M.Hip), inv = new THREE.Matrix4().copy(hips.parent.matrixWorld).invert();
    hips.position.copy(hw.applyMatrix4(inv)); model.updateMatrixWorld(true);
    // hips: up the spine, across the thighs
    twoVec(hips, wpos(bone('Spine')).sub(wpos(hips)), wpos(bone('LeftUpLeg')).sub(wpos(bone('RightUpLeg'))),
      D(M, 'Hip', 'LowerSpine'), D(M, 'RThigh', 'LThigh'));
    for (const [b, c, f, t] of CH) swing(bone(b), bone(c), D(M, f, t));
    // chest: up to the neck, across the shoulders
    const chest = bone('Spine2');
    if (chest) { chest.updateMatrixWorld(true);
      twoVec(chest, wpos(bone('Neck')).sub(wpos(chest)), wpos(bone('LeftArm')).sub(wpos(bone('RightArm'))),
        D(M, 'Chest', 'Neck'), D(M, 'RShoulder', 'LShoulder')); }
    for (const [b, c, f, t] of NK) swing(bone(b), bone(c), D(M, f, t));
    for (const [b, c, f, t] of LIM) swing(bone(b), bone(c), D(M, f, t));
    // directions alone lose contacts on a differently proportioned body (hands that should join, feet that should stay
    // planted): two-bone IK puts the ankles where the capture's are and the hands where the capture's are relative to the chest
    // (scaled to this arm length), with the capture's knee / elbow direction as the pole
    model.updateMatrixWorld(true);
    const X = (n) => xf(M[n]);
    if (xf.ik !== false) {
      const fdy = xf.footDy || 0;
      for (const s of ['Left', 'Right']) {
        const m = s[0];
        twoBone(bone(`${s}UpLeg`), bone(`${s}Leg`), bone(`${s}Foot`), X(`${m}Foot`).add(new THREE.Vector3(0, fdy, 0)), X(`${m}Shin`).add(new THREE.Vector3(0, fdy * 0.5, 0)));
        swing(bone(`${s}Foot`), bone(`${s}ToeBase`), D(M, `${m}Foot`, `${m}Toe`));
      }
      const chestA = wpos(bone('LeftArm')).add(wpos(bone('RightArm'))).multiplyScalar(0.5);
      const chestC = X('LShoulder').add(X('RShoulder')).multiplyScalar(0.5);
      for (const s of ['Left', 'Right']) {
        const m = s[0], capLen = X(`${m}Shoulder`).distanceTo(X(`${m}Forearm`)) + X(`${m}Forearm`).distanceTo(X(`${m}Hand`));
        const ra = ARM[s] / Math.max(capLen, 1e-6);
        const tgt = chestA.clone().add(X(`${m}Hand`).sub(chestC).multiplyScalar(ra));
        const pole = chestA.clone().add(X(`${m}Forearm`).sub(chestC).multiplyScalar(ra));
        twoBone(bone(`${s}Arm`), bone(`${s}ForeArm`), bone(`${s}Hand`), tgt, pole);
      }
    }
    for (const s of ['Left', 'Right']) {                // hand: towards the middle finger, palm across index -> pinky
      const h = bone(`${s}Hand`), mid = bone(`${s}HandMiddle1`), idx = bone(`${s}HandIndex1`), pk = bone(`${s}HandPinky1`);
      if (h && mid && idx && pk) { h.updateMatrixWorld(true);
        twoVec(h, wpos(mid).sub(wpos(h)), wpos(idx).sub(wpos(pk)), D(M, `${s[0]}Hand`, `${s}Finger2`), D(M, `${s}Finger4`, `${s}Finger1`));
        limitTwist(h, mid, MAX_WRIST_TWIST); limitBend(h, mid, bone(`${s}ForeArm`), MAX_WRIST_BEND); }
    }
    for (const [b, c, f, t] of FIN) swing(bone(b), bone(c), D(M, f, t));
    model.updateMatrixWorld(true);
  };
}

// blend two mocap samples (positions): B is re-based onto A's hip (ground plane) and yaw before mixing
function blendMocap(THREE, A, B, w, align) {
  if (w <= 0) return A; const out = {};
  for (const n in A) {
    if (!B[n]) { out[n] = A[n]; continue; }
    const b = B[n].clone().sub(align.from).applyAxisAngle(new THREE.Vector3(0, 1, 0), align.yaw).add(align.to);
    out[n] = A[n].clone().lerp(b, w);
  }
  return out;
}

// additive pose layers on capture points: turn the segment a -> b towards dir (weight w) about a, carrying b and its
// children rigidly with it, so the wrist and fingers keep their pose relative to the arm (no broken wrists)
function swingChain(THREE, out, a, b, dir, w, kids) {
  if (w <= 0) return;
  const cur = out[b].clone().sub(out[a]).normalize(), tgt = cur.clone().lerp(dir, w).normalize();
  const q = new THREE.Quaternion().setFromUnitVectors(cur, tgt), p = out[a];
  for (const k of [b, ...kids]) if (out[k]) out[k] = out[k].clone().sub(p).applyQuaternion(q).add(p);
}
