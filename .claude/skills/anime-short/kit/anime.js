// Anime short kit: loaders, cel/ink materials, the anime post pass, the ink impact-frame pass, the backdrop, grain.
// Used by anime_shot.html (with mocap.js) and anime_pages.html. Everything is a pure function of time.

// ---------------- DOM helpers ----------------
function el(tag, css = {}, parent = document.getElementById('stage') || document.body, html = '') {
  const e = document.createElement(tag); Object.assign(e.style, css); if (html) e.innerHTML = html; parent.appendChild(e); return e;
}
// film grain + vignette (deterministic: the grain tile is chosen per frame)
function addFinish({ grain = 0.07, vignette = 0.5 } = {}) {
  const tiles = [], rnd = VM.rand(42);
  for (let k = 0; k < 6; k++) {
    const c = document.createElement('canvas'); c.width = c.height = 220;
    const g = c.getContext('2d'), d = g.createImageData(220, 220);
    for (let i = 0; i < d.data.length; i += 4) { const v = rnd() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
    g.putImageData(d, 0, 0); tiles.push(c.toDataURL());
  }
  const vig = el('div', { position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 50,
    background: `radial-gradient(ellipse 75% 70% at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,${vignette}) 100%)` }, document.body);
  const gr = el('div', { position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 51, opacity: grain, mixBlendMode: 'overlay', backgroundSize: '220px 220px' }, document.body);
  VM.onFrame((t) => { gr.style.backgroundImage = `url(${tiles[Math.floor(t * 24) % tiles.length]})`; });
  return { vig, gr };
}

// ---------------- loading ----------------
// file:// pages can't fetch(): read bytes with XHR
function readBinary(url) {
  return new Promise((res, rej) => { const x = new XMLHttpRequest(); x.open('GET', url); x.responseType = 'arraybuffer';
    x.onload = () => (x.status && x.status !== 200 ? rej(new Error('xhr ' + x.status + ' ' + url)) : x.response ? res(x.response) : rej(new Error('missing ' + url)));
    x.onerror = () => rej(new Error('xhr ' + url)); x.send(); });
}
async function loadGLB(GLTFLoader, url) {
  const buf = await readBinary(url);
  return new Promise((res, rej) => new GLTFLoader().parse(buf, '', res, rej));
}
// fonts for file:// pages: FontFace API with the bytes ([[family, file], ...]); a missing file is skipped
async function loadFonts(list) {
  for (const [fam, file] of list) { try { const f = new FontFace(fam, await readBinary(file)); await f.load(); document.fonts.add(f); } catch (e) { console.error('font ' + file + ': ' + e.message); } }
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
  g.expr = () => {}; g.exprNames = []; g.isVRM = !!(vrm0 || vrm1);
  if (!g.isVRM) return g;
  const nodeObj = new Map(); g.scene.traverse((o) => { const a = g.parser.associations.get(o); if (a && a.nodes !== undefined) nodeObj.set(a.nodes, o); });
  const bones = vrm0 ? vrm0.humanoid.humanBones.map((b) => [b.bone, b.node]) : Object.entries(vrm1.humanoid.humanBones).map(([k, v]) => [k, v.node]);
  for (const [name, node] of bones) { let m = VRM_TO_MIXAMO[name];
    // VRM 1.0 thumbs: metacarpal / proximal / distal -> Thumb1..3
    if (vrm1 && /Thumb/.test(name)) m = name.replace(/^(left|right)Thumb(\w+)$/, (_, s, k) => `${s[0].toUpperCase() + s.slice(1)}HandThumb${{ Metacarpal: 1, Proximal: 2, Distal: 3 }[k]}`);
    const o = nodeObj.get(node); if (m && o) o.name = m; }
  const head = g.scene.getObjectByName('Head');
  if (head && !g.scene.getObjectByName('HeadTop_End')) {
    head.updateMatrixWorld(true);
    const hp = new THREE.Vector3().setFromMatrixPosition(head.matrixWorld), e = new THREE.Bone(); e.name = 'HeadTop_End'; head.add(e);
    e.position.copy(head.worldToLocal(new THREE.Vector3(hp.x, hp.y + 0.2, hp.z)));   // scalp, ~20 cm above the head joint (VRoid head joints sit at the jaw)
  }
  const groups = {};
  if (vrm0) for (const gr of vrm0.blendShapeMaster.blendShapeGroups) groups[(gr.presetName && gr.presetName !== 'unknown' ? gr.presetName : gr.name).toLowerCase()] = (gr.binds || []).map((b) => [b.mesh, b.index, b.weight / 100]);
  if (vrm1) for (const [k, ex] of Object.entries({ ...(vrm1.expressions.preset || {}), ...(vrm1.expressions.custom || {}) })) groups[k.toLowerCase()] = (ex.morphTargetBinds || []).map((b) => [json.nodes[b.node].mesh, b.index, b.weight]);
  // VRM 1.0 preset names -> the 0.x ones the docs use (angry, sorrow, joy, fun, a, i, u, e, o, blink)
  for (const [a, b] of [['sad', 'sorrow'], ['happy', 'joy'], ['relaxed', 'fun'], ['aa', 'a'], ['ih', 'i'], ['ou', 'u'], ['ee', 'e'], ['oh', 'o']]) if (groups[a] && !groups[b]) groups[b] = groups[a];
  const meshObjs = new Map(); g.scene.traverse((o) => { if (o.isMesh) { const a = g.parser.associations.get(o); if (a && a.meshes !== undefined) { if (!meshObjs.has(a.meshes)) meshObjs.set(a.meshes, []); meshObjs.get(a.meshes).push(o); } } });
  const state = {};
  g.expr = (name, w) => { state[name] = w;
    for (const list of meshObjs.values()) for (const o of list) if (o.morphTargetInfluences) o.morphTargetInfluences.fill(0);
    for (const [n, wt] of Object.entries(state)) for (const [mesh, idx, k] of groups[n] || []) for (const o of meshObjs.get(mesh) || []) if (o.morphTargetInfluences) o.morphTargetInfluences[idx] = Math.min(1, o.morphTargetInfluences[idx] + wt * k); };
  g.exprNames = Object.keys(groups);
  return g;
}

// stand the character on y = 0 facing +z, scaled to `height` metres (top of the head); returns bone(name) (Mixamo names,
// with or without the mixamorig: prefix)
function standCharacter(THREE, model, height) {
  model.updateMatrixWorld(true);
  const find = (re) => { let f = null; model.traverse((o) => { if (!f && o.isBone && re.test(o.name)) f = o; }); return f; };
  const Pw = (b) => new THREE.Vector3().setFromMatrixPosition(b.matrixWorld);
  const top = find(/HeadTop_End$/) || find(/Head$/), toe = find(/LeftToe_End$/) || find(/LeftToeBase$/), foot = find(/LeftFoot(_\d+)?$/);
  if (foot && toe && Pw(toe).z < Pw(foot).z) model.rotation.y += Math.PI;
  model.updateMatrixWorld(true);
  if (top && toe) model.scale.multiplyScalar(height / (Pw(top).y - Pw(toe).y));
  model.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(model); model.position.y -= box.min.y; model.updateMatrixWorld(true);
  const cache = new Map();
  return (n) => { if (!cache.has(n)) { let f = null; const re = new RegExp('^(mixamorig:?)?' + n + '(_\\d+)?$'); model.traverse((o) => { if (!f && o.isBone && re.test(o.name)) f = o; }); cache.set(n, f); } return cache.get(n); };
}

// three flat tones (the cel ramp)
function celRamp(THREE) {
  const d = new Uint8Array([125, 190, 255]); const t = new THREE.DataTexture(d, 3, 1, THREE.RedFormat);
  t.minFilter = t.magFilter = THREE.NearestFilter; t.needsUpdate = true; return t;
}
// per mesh: userData.toon (cel), userData.ink (impact frames: white, lit by the impact alone), applied as toon.
// opt: skin (multiply on skin textures: deep enough that lit skin never posterises into the white top band, the
// "white face"), hair (multiply), materials: { "<regex on material or mesh name>": "#hex" | "hide" }, inkEyes
function toonify(THREE, gltf, opt = {}) {
  const ramp = celRamp(THREE), meshes = [];
  const rules = Object.entries(opt.materials || {}).map(([re, v]) => [new RegExp(re, 'i'), v]);
  gltf.scene.traverse((o) => { if (!o.isMesh) return; o.castShadow = true; o.frustumCulled = false;
    const m = o.material, name = m.name || '', rule = rules.find(([re]) => re.test(name) || re.test(o.name));
    if (rule && rule[1] === 'hide') { o.visible = false; return; }
    meshes.push(o);
    const col = rule ? new THREE.Color(rule[1]) : null;
    const skin = /_(SKIN|FACE)$|Body_00|Face_00_SKIN|skin/i.test(name) && !/Face(Brow|Eyelash|Eyeline|Mouth)|_EYE$/i.test(name);
    const hair = /_HAIR$|hair/i.test(name);
    const flat = /_EYE$|Face(Brow|Eyelash|Eyeline|Mouth)|EyeHighlight|EyeIris|EyeWhite/.test(name);   // painted face details stay unlit (lit, rim lights turn brows orange)
    o.userData.src = name;
    o.userData.toon = flat
      ? new THREE.MeshBasicMaterial({ map: m.map, transparent: m.transparent, alphaTest: m.alphaTest, side: /_EYE$/.test(name) ? THREE.DoubleSide : m.side, depthWrite: m.depthWrite })
      : new THREE.MeshToonMaterial({ normalMap: m.normalMap, normalScale: m.normalScale, map: col ? null : m.map, transparent: m.transparent, alphaTest: m.alphaTest, side: m.side, depthWrite: m.depthWrite, gradientMap: ramp,
          color: col || new THREE.Color(skin && opt.skin ? opt.skin : hair && opt.hair ? opt.hair : (m.color ? m.color.getHex() : 0xffffff)) });
    if (/Face(Brow|Eyelash|Eyeline|Mouth)/.test(name)) o.userData.ink = o.userData.toon;
    else if (/_EYE$|EyeHighlight|EyeIris|EyeWhite/.test(name) && !opt.inkEyes) o.userData.ink = new THREE.MeshBasicMaterial({ visible: false });
    else { const im = new THREE.MeshLambertMaterial({ color: 0xffffff, map: col ? null : m.map, transparent: m.transparent, alphaTest: m.alphaTest, side: m.side, depthWrite: m.depthWrite });
      im.onBeforeCompile = (sh) => { sh.fragmentShader = sh.fragmentShader.replace('#include <map_fragment>', '#ifdef USE_MAP\n diffuseColor.a *= texture2D( map, vMapUv ).a;\n#endif'); };   // the map's alpha only: the light alone draws
      o.userData.ink = im; }
    if (opt.debug) console.error(`MATERIAL ${name} mesh=${o.name} ${flat ? 'unlit' : 'toon'} colour=#${o.userData.toon.color.getHexString()}${skin ? ' skin' : ''}${hair ? ' hair' : ''}`);
    o.material = o.userData.toon; });
  return { meshes, ramp };
}

// ---------------- backdrop ----------------
// screen-space sky (gradient + out-of-focus lights, or an image) and a floor that takes the shadows. Meshes go in env
// (hidden in impact frames). set: { sky: [top, mid, bottom], bokeh: n, warm, cool, image, floor: '#hex' | null, floorSize, seed }
function makeBackdrop(THREE, scene, set = {}) {
  const env = [], out = { env, bgTex: null };
  if (set.image) { const t = new THREE.TextureLoader().load(set.image); t.colorSpace = THREE.SRGBColorSpace; out.bgTex = t; }
  else {
    const c = document.createElement('canvas'); c.width = 960; c.height = 540; const g = c.getContext('2d');
    const sky = set.sky || ['#060a16', '#0d1630', '#070a12'], gr = g.createLinearGradient(0, 0, 0, 540);
    gr.addColorStop(0, sky[0]); gr.addColorStop(0.55, sky[1] || sky[0]); gr.addColorStop(1, sky[2] || sky[1] || sky[0]);
    g.fillStyle = gr; g.fillRect(0, 0, 960, 540);
    const R = VM.rand(set.seed ?? 31), warm = set.warm || 'rgba(255,214,140,0.55)', cool = set.cool || 'rgba(140,170,255,0.4)';
    for (let i = 0; i < (set.bokeh ?? 46); i++) { const x = R() * 960, y = 60 + R() * 260, r = 4 + R() * 22, w = R() > 0.3;
      const rg = g.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, w ? warm : cool); rg.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = rg; g.fillRect(x - r, y - r, r * 2, r * 2); }
    if (set.lamps ?? true) for (let i = 0; i < 9; i++) { const x = 40 + i * 110 + R() * 30, rg = g.createRadialGradient(x, 30, 0, x, 30, 60);
      rg.addColorStop(0, 'rgba(255,245,220,0.9)'); rg.addColorStop(0.2, 'rgba(255,230,180,0.25)'); rg.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = rg; g.fillRect(x - 60, 0, 120, 90); }
    out.bgTex = new THREE.CanvasTexture(c); out.bgTex.colorSpace = THREE.SRGBColorSpace;
  }
  scene.background = out.bgTex;
  if (set.floor !== null) {
    // the floor is unlit (it keeps exactly its colour: the rims would skim it orange), a pool of light painted under the
    // action, its rim fading into the sky (no hard horizon); the character's shadow falls on a shadow catcher above it
    const S = set.floorSize || 40, c = document.createElement('canvas'); c.width = c.height = 1024; const g = c.getContext('2d');
    g.fillStyle = set.floor || '#151a28'; g.fillRect(0, 0, 1024, 1024);
    const pool = g.createRadialGradient(512, 512, 0, 512, 512, 512 * (set.poolSize ?? 0.18));
    pool.addColorStop(0, set.poolColor || `rgba(255,236,200,${set.pool ?? 0.22})`); pool.addColorStop(1, 'rgba(255,236,200,0)');
    g.fillStyle = pool; g.fillRect(0, 0, 1024, 1024);
    const R = VM.rand(5); g.globalAlpha = 0.05; for (let i = 0; i < 6000; i++) { g.fillStyle = R() > 0.5 ? '#fff' : '#000'; g.fillRect(R() * 1024, R() * 1024, 2, 2); }
    if (set.lines) { g.globalAlpha = 0.8; g.strokeStyle = set.lines; g.lineWidth = 5; for (let k = 1; k < 6; k++) { const p = k * 1024 / 6; g.beginPath(); g.moveTo(p, 0); g.lineTo(p, 1024); g.stroke(); } }
    g.globalAlpha = 1; g.globalCompositeOperation = 'destination-in';
    const rg = g.createRadialGradient(512, 512, 0, 512, 512, 512); rg.addColorStop(0, '#000'); rg.addColorStop(set.fade ?? 0.45, '#000'); rg.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = rg; g.fillRect(0, 0, 1024, 1024);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(S, S), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, toneMapped: false }));
    floor.rotation.x = -Math.PI / 2; floor.renderOrder = -1; scene.add(floor); env.push(floor);
    const catcher = new THREE.Mesh(new THREE.PlaneGeometry(S, S), new THREE.ShadowMaterial({ opacity: set.shadow ?? 0.55, depthWrite: false }));
    catcher.rotation.x = -Math.PI / 2; catcher.position.y = 0.002; catcher.receiveShadow = true; scene.add(catcher); env.push(catcher);
  }
  return out;
}

// ---------------- anime post pass ----------------
// lens: barrel distortion, chromatic aberration, radial zoom blur towards `center`; then the anime pass (three flat cel tones,
// hand-drawn outlines that boil on twos, scratchy hatching in the shadows, glow off the brightest light; near-black stays
// black) and a grade (saturation, tint). Uniforms: k, ca, zoom, center, cel, anime, sat, tint, time.
function makeAnimePost(THREE, W, H) {
  const rt = new THREE.WebGLRenderTarget(W, H, { samples: 4, type: THREE.HalfFloatType });
  const lensMat = new THREE.ShaderMaterial({
    uniforms: { tDiffuse: { value: rt.texture }, k: { value: 0 }, ca: { value: 0.06 }, aspect: { value: W / H }, zoom: { value: 0 }, cel: { value: 0.75 }, px: { value: new THREE.Vector2(1 / W, 1 / H) }, center: { value: new THREE.Vector2(0.5, 0.5) }, sat: { value: 1 }, tint: { value: new THREE.Vector3(1, 1, 1) }, anime: { value: 1 }, time: { value: 0 } },
    vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
    fragmentShader: `uniform sampler2D tDiffuse; uniform float k; uniform float ca; uniform float aspect; uniform float zoom; uniform vec2 center; uniform float cel; uniform vec2 px; uniform float sat; uniform vec3 tint; uniform float anime; uniform float time; varying vec2 vUv;
      float hh(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float hn(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hh(i), hh(i + vec2(1.0, 0.0)), f.x), mix(hh(i + vec2(0.0, 1.0)), hh(i + vec2(1.0, 1.0)), f.x), f.y); }
      vec2 warp(vec2 uv, float kk) {
        vec2 p = (uv - 0.5) * vec2(aspect, 1.0); float r2 = dot(p, p), rc2 = 0.25 * (aspect * aspect + 1.0);
        return 0.5 + p * ((1.0 + kk * r2) / (1.0 + kk * rc2)) / vec2(aspect, 1.0); }
      float tl(vec2 uv) { float L = dot(texture2D(tDiffuse, uv).rgb, vec3(0.333)); return L / (1.0 + L); }
      void main() {
        vec4 g = vec4(0.0); float r = 0.0, b = 0.0;
        if (zoom < 0.002) {
          g = texture2D(tDiffuse, warp(vUv, k));
          r = texture2D(tDiffuse, warp(vUv, k * (1.0 + ca))).r; b = texture2D(tDiffuse, warp(vUv, k * (1.0 - ca))).b;
        } else {
          for (int i = 0; i < 12; i++) {
            vec2 u = center + (vUv - center) * (1.0 - zoom * float(i) / 11.0);
            g += texture2D(tDiffuse, warp(u, k));
            r += texture2D(tDiffuse, warp(u, k * (1.0 + ca * 2.0))).r; b += texture2D(tDiffuse, warp(u, k * (1.0 - ca * 2.0))).b;
          }
          g /= 12.0; r /= 12.0; b /= 12.0;
        }
        gl_FragColor = vec4(r, g.g, b, g.a);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
        if (cel > 0.0 && anime > 0.5) {
          vec3 c = gl_FragColor.rgb;
          float l = dot(c, vec3(0.299, 0.587, 0.114)), bt = floor(time * 12.0) / 12.0;
          float tq = l < 0.3 ? 0.19 : (l < 0.66 ? 0.5 : 0.86);
          vec3 cq = c * (tq + 0.02) / (l + 0.02);
          float m = dot(cq, vec3(0.333)); cq = mix(vec3(m), cq, 1.3);
          if (l < 0.3) cq *= vec3(0.94, 0.94, 1.06);
          cq = mix(c, cq, smoothstep(0.05, 0.12, l));
          vec2 q = vUv * vec2(aspect, 1.0);
          vec2 wob = (vec2(hn(q * 6.0 + bt * 7.0), hn(q * 6.0 + 9.0 + bt * 5.0)) - 0.5) * px * 3.0;
          vec2 o = px * 2.2;
          float lx = tl(warp(vUv + wob + vec2(o.x, 0.0), k)) - tl(warp(vUv + wob - vec2(o.x, 0.0), k));
          float ly = tl(warp(vUv + wob + vec2(0.0, o.y), k)) - tl(warp(vUv + wob - vec2(0.0, o.y), k));
          float edge = smoothstep(0.07, 0.18, sqrt(lx * lx + ly * ly));
          vec2 hd = normalize(vec2(0.62, 0.78)); float across = dot(gl_FragCoord.xy, hd) / 5.0 + hn(q * 9.0 + bt) * 2.0;
          float hl = abs(fract(across) - 0.5);
          float dash = step(0.4, hn(vec2(dot(gl_FragCoord.xy, vec2(-hd.y, hd.x)) / 18.0 + floor(across) * 1.7, floor(across) * 0.37 + bt * 11.0)));
          float hatch = step(hl, 0.18) * dash * (1.0 - smoothstep(0.18, 0.34, l)) * smoothstep(0.06, 0.12, l);
          vec3 outc = mix(cq, cq * 0.5, hatch * 0.55);
          vec3 glow = vec3(0.0);
          for (int i = 0; i < 8; i++) { float a = float(i) * 0.785; vec2 dd = vec2(cos(a), sin(a)) * px * 9.0;
            vec3 s1 = texture2D(tDiffuse, warp(vUv + dd, k)).rgb; s1 = s1 / (1.0 + s1); glow += max(s1 - 0.62, 0.0); }
          outc += glow * 0.35 * vec3(1.0, 0.92, 0.8);
          outc = mix(outc, vec3(0.02, 0.02, 0.05), edge * 0.95);
          gl_FragColor.rgb = mix(c, outc, cel);
        } else if (cel > 0.0) {
          vec3 c = gl_FragColor.rgb;
          float l = dot(c, vec3(0.299, 0.587, 0.114));
          float q = (floor(l * 4.0 + 0.5) / 4.0);
          vec3 cq = c * (q + 0.04) / (l + 0.04);
          float m = dot(cq, vec3(0.333)); cq = mix(vec3(m), cq, 1.25);
          vec2 o = px * 1.6;
          float lx = tl(warp(vUv + vec2(o.x, 0.0), k)) - tl(warp(vUv - vec2(o.x, 0.0), k));
          float ly = tl(warp(vUv + vec2(0.0, o.y), k)) - tl(warp(vUv - vec2(0.0, o.y), k));
          float edge = smoothstep(0.12, 0.32, sqrt(lx * lx + ly * ly));
          vec2 g = fract(gl_FragCoord.xy / 7.0) - 0.5;
          float dots = step(length(g), 0.5 * clamp((0.32 - l) / 0.32, 0.0, 1.0));
          vec3 outc = mix(cq, cq * 0.55, dots * 0.6);
          outc = mix(outc, vec3(0.04, 0.05, 0.1), edge * 0.85);
          gl_FragColor.rgb = mix(c, outc, cel);
        }
        float gl = dot(gl_FragColor.rgb, vec3(0.299, 0.587, 0.114));
        gl_FragColor.rgb = mix(vec3(gl), gl_FragColor.rgb, sat) * tint;
      }`,
    depthTest: false, depthWrite: false });
  const postScene = new THREE.Scene(), postCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  postScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), lensMat));
  return { rt, lensMat, postScene, postCam };
}

// ---------------- ink impact frame ----------------
// anime "sakuga" impact frames: reads the scene render (the character in white ink materials, lit by the impact alone, on a
// transparent background) and redraws it as a two-tone brush drawing: light/shadow along a ragged edge, hatching across it,
// outlines in the opposite tone, energy streaks from the hit, a fisheye on the hit (bulge), a flash out of it (flashR, with a
// torn edge and spikes), everything boiling on twos. ink/paper: the palette.
function makeInkPass(THREE, W, H, src) {
  const inkMat = new THREE.ShaderMaterial({
    uniforms: { tDiffuse: { value: src }, px: { value: new THREE.Vector2(1 / W, 1 / H) }, aspect: { value: W / H }, time: { value: 0 },
      center: { value: new THREE.Vector2(0.5, 0.5) }, thr: { value: 0.95 }, band: { value: 0.22 },
      ink: { value: new THREE.Color(0xffffff) }, paper: { value: new THREE.Color(0x000000) }, streaks: { value: 1 }, seed: { value: 0 },
      bulge: { value: 0 }, flashR: { value: 0 }, lineW: { value: 2.4 }, core: { value: 1 } },
    vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
    fragmentShader: `uniform sampler2D tDiffuse; uniform vec2 px; uniform float aspect; uniform float time; uniform vec2 center;
      uniform float thr; uniform float band; uniform vec3 ink; uniform vec3 paper; uniform float streaks; uniform float seed;
      uniform float bulge; uniform float flashR; uniform float lineW; uniform float core; varying vec2 vUv;
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7)) + seed * 17.0) * 43758.5453); }
      float noise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y); }
      float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { s += a * noise(p); p *= 2.03; a *= 0.5; } return s; }
      vec4 tap(vec2 uv) { vec4 c = texture2D(tDiffuse, uv); float L = dot(c.rgb, vec3(0.299, 0.587, 0.114)); return vec4(L / (1.0 + L) * 1.7, c.a, 0.0, 0.0); }
      void main() {
        float bt = floor(time * 12.0) / 12.0;
        vec2 dc = (vUv - center) * vec2(aspect, 1.0); float rc = length(dc), rn = rc / 1.3;
        vec2 fuv = center + dc * (pow(max(rn, 1e-4), 1.0 + bulge) / max(rn, 1e-4)) / vec2(aspect, 1.0);
        vec2 q = fuv * vec2(aspect, 1.0);
        vec2 wob = (vec2(fbm(q * 5.0 + bt * 7.1), fbm(q * 5.0 + 13.0 + bt * 5.3)) - 0.5) * px * 7.0;
        vec2 uv = fuv + wob;
        vec4 c = tap(uv); float l = c.x, A = c.y;
        float jit = (fbm(q * 34.0 + bt * 3.0) - 0.5) * 0.16;
        float d = l - thr + jit;
        float fill = step(0.0, d) * step(0.5, A);
        vec2 hd = normalize(vec2(0.62, 0.78));
        float along = dot(q, vec2(-hd.y, hd.x)), across = dot(q, hd) * 230.0 + fbm(q * 9.0 + bt) * 3.0;
        float id = floor(across), line = abs(fract(across) - 0.5);
        float dash = step(0.42, noise(vec2(along * 26.0 + id * 1.7, id * 0.37 + bt * 11.0)));
        float k = clamp(1.0 - abs(d) / band, 0.0, 1.0);
        float hatch = step(line, 0.07 + 0.33 * k * k) * dash * step(0.01, k) * step(0.5, A);
        float r = (1.6 + 1.4 * noise(q * 60.0 + bt * 5.0)) * lineW;
        vec4 e1 = tap(uv + vec2(px.x * r, 0.0)), e2 = tap(uv - vec2(px.x * r, 0.0)), e3 = tap(uv + vec2(0.0, px.y * r)), e4 = tap(uv - vec2(0.0, px.y * r));
        float sil = length(vec2(e1.y - e2.y, e3.y - e4.y));
        float inner = length(vec2(e1.x - e2.x, e3.x - e4.x)) * step(0.5, A);
        float edge = max(step(0.35, sil), step(0.22 + 0.1 * noise(q * 40.0), inner));
        vec2 dv = (vUv - center) * vec2(aspect, 1.0); float rr = length(dv), th = atan(dv.y, dv.x);
        float s1 = fbm(vec2(th * 9.0, log(rr + 0.002) * 1.6 - bt * 1.5) + seed);
        float s2 = noise(vec2(th * 60.0, rr * 4.0 + bt * 2.0));
        float s3 = noise(vec2(th * 140.0 + seed, log(rr + 0.002) * 0.7 - bt * 3.0));
        float streak = max(step(0.66 + 0.12 * smoothstep(0.1, 0.6, rr), s1 + 0.1 * s2) * step(0.35, s3), step(0.86, s3) * step(0.5, s1))
          * smoothstep(0.06, 0.2, rr) * (1.0 - step(0.5, A)) * streaks;
        float burst = (1.0 - smoothstep(0.02, 0.06 + 0.03 * noise(vec2(th * 8.0, bt * 9.0)), rr)) * streaks * core;
        float fr = flashR * (0.82 + 0.36 * noise(vec2(th * 7.0 + seed, bt * 13.0)));
        float flash = (1.0 - step(fr, rr)) * step(0.001, flashR);
        float spike = step(0.72, noise(vec2(th * 34.0 + seed * 3.0, bt * 17.0))) * (1.0 - smoothstep(fr, fr * 2.4 + 0.05, rr)) * step(0.001, flashR);
        float v = abs(fill - max(hatch, edge));
        v = max(v, max(max(streak, burst), max(flash, spike)));
        gl_FragColor = vec4(mix(paper, ink, v), 1.0);
      }`,
    depthTest: false, depthWrite: false });
  const inkScene = new THREE.Scene(), inkCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  inkScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), inkMat));
  return { inkMat, inkScene, inkCam };
}
// impact-frame palettes [ink, paper]: white on black, the negative, black brush on red, mint on black
const INK_PALETTES = [[0xffffff, 0x000000], [0x0b0b0b, 0xf6f3ec], [0x120000, 0xd0101c], [0xcff2e0, 0x040807]];
