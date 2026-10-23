// file:// pages can't fetch(); read the GLB with XHR and hand the bytes to GLTFLoader.parse
function readBinary(url) {
  return new Promise((res, rej) => { const x = new XMLHttpRequest(); x.open('GET', url); x.responseType = 'arraybuffer';
    x.onload = () => res(x.response); x.onerror = () => rej(new Error('xhr ' + url)); x.send(); });
}
async function loadGLB(GLTFLoader, url) {
  const buf = await readBinary(url);
  return new Promise((res, rej) => new GLTFLoader().parse(buf, '', res, rej));
}

// VRoid / VRM (0.x and 1.0) characters: rename the humanoid bones to Mixamo names so the retarget treats them like any
// Mixamo rig, add a HeadTop_End marker, and expose the facial blendshape groups: expr('angry', 1), expr('a', 0.8) ...
const VRM_TO_MIXAMO = { hips: 'Hips', spine: 'Spine', chest: 'Spine1', upperChest: 'Spine2', neck: 'Neck', head: 'Head' };
for (const [s, S] of [['left', 'Left'], ['right', 'Right']]) {
  Object.assign(VRM_TO_MIXAMO, { [`${s}Shoulder`]: `${S}Shoulder`, [`${s}UpperArm`]: `${S}Arm`, [`${s}LowerArm`]: `${S}ForeArm`, [`${s}Hand`]: `${S}Hand`,
    [`${s}UpperLeg`]: `${S}UpLeg`, [`${s}LowerLeg`]: `${S}Leg`, [`${s}Foot`]: `${S}Foot`, [`${s}Toes`]: `${S}ToeBase` });
  for (const [f, F] of [['Thumb', 'Thumb'], ['Index', 'Index'], ['Middle', 'Middle'], ['Ring', 'Ring'], ['Little', 'Pinky']]) {
    const seg = f === 'Thumb' ? [['Metacarpal', null], ['Proximal', 1], ['Intermediate', 2], ['Distal', 3]] : [['Proximal', 1], ['Intermediate', 2], ['Distal', 3]];
    for (const [k, i] of seg) if (i) VRM_TO_MIXAMO[`${s}${f}${k}`] = `${S}Hand${F}${i}`;
  }
}
async function loadCharacter(THREE, GLTFLoader, url) {
  const g = await loadGLB(GLTFLoader, url), json = g.parser.json, ext = json.extensions || {};
  const vrm0 = ext.VRM, vrm1 = ext.VRMC_vrm;
  g.expr = () => {}; g.isVRM = !!(vrm0 || vrm1);
  if (!g.isVRM) return g;
  const nodeObj = new Map(); g.scene.traverse((o) => { const a = g.parser.associations.get(o); if (a && a.nodes !== undefined) nodeObj.set(a.nodes, o); });
  const bones = vrm0 ? vrm0.humanoid.humanBones.map((b) => [b.bone, b.node]) : Object.entries(vrm1.humanoid.humanBones).map(([k, v]) => [k, v.node]);
  // VRM 1.0 thumbs: metacarpal/proximal/distal -> shift so Thumb1..3 exist
  for (const [name, node] of bones) { let m = VRM_TO_MIXAMO[name];
    if (vrm1 && /Thumb/.test(name)) m = { Metacarpal: 1, Proximal: 2, Distal: 3 }[name.replace(/^(left|right)Thumb/, '')] && name.replace(/^(left|right)Thumb(\w+)$/, (_, s, k) => `${s[0].toUpperCase() + s.slice(1)}HandThumb${{ Metacarpal: 1, Proximal: 2, Distal: 3 }[k]}`);
    const o = nodeObj.get(node); if (m && o) o.name = m; }
  const head = g.scene.getObjectByName('Head');
  if (head && !g.scene.getObjectByName('HeadTop_End')) {
    head.updateMatrixWorld(true);
    let top = 0; g.scene.traverse((o) => { if (o.isMesh) { const b = new THREE.Box3().setFromObject(o); top = Math.max(top, b.max.y); } });
    const hp = new THREE.Vector3().setFromMatrixPosition(head.matrixWorld), e = new THREE.Bone(); e.name = 'HeadTop_End'; head.add(e);
    // scalp height above the head joint (head joints sit at the jaw in VRoid; hair is excluded later by the caller if needed)
    const local = head.worldToLocal(new THREE.Vector3(hp.x, hp.y + 0.2, hp.z)); e.position.copy(local); }
  // expressions: blendshape groups -> morph targets on the face meshes
  const groups = {};
  if (vrm0) for (const gr of vrm0.blendShapeMaster.blendShapeGroups) groups[(gr.presetName && gr.presetName !== 'unknown' ? gr.presetName : gr.name).toLowerCase()] = (gr.binds || []).map((b) => [b.mesh, b.index, b.weight / 100]);
  if (vrm1) for (const [k, ex] of Object.entries({ ...(vrm1.expressions.preset || {}), ...(vrm1.expressions.custom || {}) })) groups[k.toLowerCase()] = (ex.morphTargetBinds || []).map((b) => [json.nodes[b.node].mesh, b.index, b.weight]);
  const meshObjs = new Map(); g.scene.traverse((o) => { if (o.isMesh) { const a = g.parser.associations.get(o); if (a && a.meshes !== undefined) { if (!meshObjs.has(a.meshes)) meshObjs.set(a.meshes, []); meshObjs.get(a.meshes).push(o); } } });
  const state = {};
  g.expr = (name, w) => { state[name] = w;
    for (const list of meshObjs.values()) for (const o of list) if (o.morphTargetInfluences) o.morphTargetInfluences.fill(0);
    for (const [n, wt] of Object.entries(state)) for (const [mesh, idx, k] of groups[n] || []) for (const o of meshObjs.get(mesh) || []) if (o.morphTargetInfluences) o.morphTargetInfluences[idx] = Math.min(1, o.morphTargetInfluences[idx] + wt * k); };
  g.exprNames = Object.keys(groups);
  return g;
}
