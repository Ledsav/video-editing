// A Mikasa-style volleyball (V200W colourway: royal blue + yellow swirl panels) as a lit three.js sphere.
// No wordmark: only the panel design and colours.
const MIKASA = { blue: '#1347a8', yellow: '#ffd21f', seam: '#0b1f4a' };

function mikasaTexture(W = 2048, H = 1024, { blue = MIKASA.blue, yellow = MIKASA.yellow, seam = MIKASA.seam } = {}) {
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d'), img = g.createImageData(W, H), d = img.data;
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const B = hex(blue), Y = hex(yellow), S = hex(seam);
  const N = 6;                                    // 3 yellow + 3 blue panels per swirl
  for (let j = 0; j < H; j++) {
    const th = (j / H) * Math.PI, sy = Math.cos(th), r = Math.sin(th);
    for (let i = 0; i < W; i++) {
      const ph = (i / W) * Math.PI * 2;
      const x = -Math.cos(ph) * r, z = Math.sin(ph) * r;
      // panels swirl around the y axis; the twist grows away from the equator (S-curves)
      const a = Math.atan2(z, x) + 1.5 * sy + 0.5 * Math.sin(3 * sy);
      let f = ((a / (Math.PI * 2)) * N) % 1; if (f < 0) f += 1;
      const band = Math.floor((((a / (Math.PI * 2)) * N) % N + N) % N);
      // seams: at panel edges plus the thin double line inside each yellow panel
      const edge = Math.min(f, 1 - f) * r;        // fades to 0 at the poles -> crisp centre
      const inner = Math.abs(f - 0.5) * r;
      let col = band % 2 ? B : Y;
      let s = 0;
      if (edge < 0.012) s = 1 - edge / 0.012;
      if (band % 2 === 0 && inner < 0.006) s = Math.max(s, 0.55 * (1 - inner / 0.006));
      const k = (j * W + i) * 4;
      d[k] = col[0] + (S[0] - col[0]) * s; d[k + 1] = col[1] + (S[1] - col[1]) * s; d[k + 2] = col[2] + (S[2] - col[2]) * s; d[k + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  return c;
}


// V200W structure: 18 panels = 6 cube faces x 3 strips, strip direction rotating between faces.
// Colour (from the maker's description: royal blue + yellow): yellow centre strip, blue outer strips,
// the colour boundary waves across the straight seams.
function v200wTexture(W = 2048, H = 1024, { blue = MIKASA.blue, yellow = MIKASA.yellow, seam = MIKASA.seam, wave = 0.11 } = {}) {
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d'), img = g.createImageData(W, H), d = img.data;
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const B = hex(blue), Y = hex(yellow), S = hex(seam);
  for (let j = 0; j < H; j++) {
    const th = (j / H) * Math.PI, py = Math.cos(th), r = Math.sin(th);
    for (let i = 0; i < W; i++) {
      const ph = (i / W) * Math.PI * 2, px = -Math.cos(ph) * r, pz = Math.sin(ph) * r;
      const ax = Math.abs(px), ay = Math.abs(py), az = Math.abs(pz);
      let a, b, face;
      if (ax >= ay && ax >= az) { a = py / ax; b = pz / ax; face = 0; }
      else if (ay >= az) { a = pz / ay; b = px / ay; face = 1; }
      else { a = px / az; b = py / az; face = 2; }
      // gnomonic -> equal-angle so strips look even on the sphere
      a = Math.atan(a) / (Math.PI / 4); b = Math.atan(b) / (Math.PI / 4);
      const edge = Math.min(1 - Math.abs(a), 1 - Math.abs(b), Math.abs(Math.abs(b) - 1 / 3));
      const bound = 1 / 3 + wave * Math.sin(a * Math.PI * 1.5 + face);
      const col = Math.abs(b) < bound ? Y : B;
      let s = edge < 0.022 ? 1 - edge / 0.022 : 0;
      s *= 0.85;
      const k = (j * W + i) * 4;
      d[k] = col[0] + (S[0] - col[0]) * s; d[k + 1] = col[1] + (S[1] - col[1]) * s; d[k + 2] = col[2] + (S[2] - col[2]) * s; d[k + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  return c;
}


// V200W matched to the reference photo (ref/v200w.jpg): golden-yellow ball crossed by a royal-blue band that
// follows a tennis-ball seam curve (S-sweep across the front, splitting at the sides), dotted texture on the
// blue, soft pillow seams of the 18 panels everywhere, white wordmark in the band.
const V200W = { yellow: '#f6c300', blue: '#2140a6', seamY: '#c99a00', seamB: '#16307e', dot: '#4a63c4' };
function v200wRefMaps(W = 2048, H = 1024, { wordmark = true, halfWidth = 0.205, lobe = 0.27 } = {}) {
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const Y = hex(V200W.yellow), B = hex(V200W.blue), SY = hex(V200W.seamY), SB = hex(V200W.seamB), D = hex(V200W.dot);
  // seam curve samples (unit vectors)
  const a = 1 - lobe, b = lobe, cz = 2 * Math.sqrt(a * b), N = 720, curve = new Float32Array(N * 3);
  for (let k = 0; k < N; k++) { const t = (k / N) * Math.PI * 2;
    let x = a * Math.cos(t) + b * Math.cos(3 * t), y = a * Math.sin(t) - b * Math.sin(3 * t), z = cz * Math.sin(2 * t);
    const l = Math.hypot(x, y, z); curve[k * 3] = x / l; curve[k * 3 + 1] = y / l; curve[k * 3 + 2] = z / l; }
  const dir = (i, j, w, h) => { const th = ((j + 0.5) / h) * Math.PI, ph = ((i + 0.5) / w) * Math.PI * 2, r = Math.sin(th);
    return [-Math.cos(ph) * r, Math.cos(th), Math.sin(ph) * r]; };
  // coarse angular distance field to the curve, upsampled bilinearly
  const cw = 512, ch = 256, field = new Float32Array(cw * ch);
  for (let j = 0; j < ch; j++) for (let i = 0; i < cw; i++) {
    const [x, y, z] = dir(i, j, cw, ch); let best = -2;
    for (let k = 0; k < N; k++) { const d = x * curve[k * 3] + y * curve[k * 3 + 1] + z * curve[k * 3 + 2]; if (d > best) best = d; }
    field[j * cw + i] = Math.acos(Math.min(1, best));
  }
  const fieldAt = (u, v) => { const fx = u * cw - 0.5, fy = Math.min(ch - 1.001, Math.max(0, v * ch - 0.5));
    const i0 = Math.floor(fx), j0 = Math.floor(fy), tx = fx - i0, ty = fy - j0, w = (i) => ((i % cw) + cw) % cw;
    const g = (i, j) => field[j * cw + w(i)];
    return (g(i0, j0) * (1 - tx) + g(i0 + 1, j0) * tx) * (1 - ty) + (g(i0, j0 + 1) * (1 - tx) + g(i0 + 1, j0 + 1) * tx) * ty; };
  // wordmark: rendered once, mapped onto the band around the curve point t = 0 (local tangent frame)
  let word = null, P0, T0, N0;
  if (wordmark) {
    word = document.createElement('canvas'); word.width = 1024; word.height = 256;
    const wg = word.getContext('2d'); wg.fillStyle = '#fff'; wg.textAlign = 'center'; wg.textBaseline = 'middle';
    wg.font = "700 150px 'Montserrat', 'Inter', sans-serif"; if ('letterSpacing' in wg) wg.letterSpacing = '6px'; wg.fillText('MIKASA', 512, 140);
    wg.beginPath(); const sx = 300, sy = 52, R1 = 18, R2 = 7;   // the star above the first letters
    for (let k = 0; k < 10; k++) { const r = k % 2 ? R2 : R1, an = -Math.PI / 2 + k * Math.PI / 5; wg.lineTo(sx + Math.cos(an) * r, sy + Math.sin(an) * r); }
    wg.fill();
    word = wg.getImageData(0, 0, 1024, 256).data;
    P0 = [curve[0], curve[1], curve[2]];
    const p1 = [curve[3], curve[4], curve[5]]; let tx = p1[0] - P0[0], ty = p1[1] - P0[1], tz = p1[2] - P0[2]; const tl = Math.hypot(tx, ty, tz);
    T0 = [tx / tl, ty / tl, tz / tl];
    N0 = [P0[1] * T0[2] - P0[2] * T0[1], P0[2] * T0[0] - P0[0] * T0[2], P0[0] * T0[1] - P0[1] * T0[0]];
  }
  const col = document.createElement('canvas'); col.width = W; col.height = H;
  const bump = document.createElement('canvas'); bump.width = W; bump.height = H;
  const cg = col.getContext('2d'), bg = bump.getContext('2d');
  const ci = cg.createImageData(W, H), bi = bg.createImageData(W, H), cd = ci.data, bd = bi.data;
  for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) {
    const [x, y, z] = dir(i, j, W, H);
    const dist = fieldAt((i + 0.5) / W, (j + 0.5) / H);
    const blueK = Math.min(1, Math.max(0, (halfWidth - dist) / 0.006 + 0.5));        // anti-aliased band edge
    // 18-panel pillow seams (cube faces x 3 strips)
    const ax = Math.abs(x), ay = Math.abs(y), az = Math.abs(z); let u, v;
    if (ax >= ay && ax >= az) { u = y / ax; v = z / ax; } else if (ay >= az) { u = z / ay; v = x / ay; } else { u = x / az; v = y / az; }
    u = Math.atan(u) / (Math.PI / 4); v = Math.atan(v) / (Math.PI / 4);
    const vw_ = v + 0.05 * Math.sin(u * Math.PI * 1.5), uw_ = u + 0.04 * Math.sin(v * Math.PI * 1.5);   // softly curved panels
    const e = Math.min(1 - Math.abs(uw_), 1 - Math.abs(vw_), Math.abs(Math.abs(vw_) - 1 / 3));
    const seam = Math.max(0, 1 - e / 0.014);
    const pillow = Math.min(1, e / 0.12);                                              // panels bulge between seams
    // dot texture (isotropic lattice in 3D), strong on the blue
    const k = 150, dots = Math.max(0, Math.cos(k * x) * Math.cos(k * y) * Math.cos(k * z) - 0.45) / 0.55;
    let r = Y[0] + (B[0] - Y[0]) * blueK, g = Y[1] + (B[1] - Y[1]) * blueK, bl = Y[2] + (B[2] - Y[2]) * blueK;
    const sc = [SY[0] + (SB[0] - SY[0]) * blueK, SY[1] + (SB[1] - SY[1]) * blueK, SY[2] + (SB[2] - SY[2]) * blueK];
    const dk = Math.min(1, dots * 1.6) * blueK * 0.85;
    r += (D[0] - r) * dk; g += (D[1] - g) * dk; bl += (D[2] - bl) * dk;
    const sk = seam * 0.32; r += (sc[0] - r) * sk; g += (sc[1] - g) * sk; bl += (sc[2] - bl) * sk;
    if (word) {
      const dp = x * P0[0] + y * P0[1] + z * P0[2];
      if (dp > 0.7) {
        const lu = x * T0[0] + y * T0[1] + z * T0[2], lv = x * N0[0] + y * N0[1] + z * N0[2];
        const wu = Math.round(512 - lu / 0.62 * 512), wv = Math.round(128 + lv / 0.62 * 512);
        if (wu >= 0 && wu < 1024 && wv >= 0 && wv < 256) { const wa = word[(wv * 1024 + wu) * 4 + 3] / 255 * 0.92;
          r += (238 - r) * wa; g += (242 - g) * wa; bl += (250 - bl) * wa; }
      }
    }
    const o = (j * W + i) * 4;
    cd[o] = r; cd[o + 1] = g; cd[o + 2] = bl; cd[o + 3] = 255;
    const h = 150 + pillow * 45 - seam * 60 - dots * (0.35 + 0.65 * blueK) * 40;
    bd[o] = bd[o + 1] = bd[o + 2] = Math.max(0, Math.min(255, h)); bd[o + 3] = 255;
  }
  cg.putImageData(ci, 0, 0); bg.putImageData(bi, 0, 0);
  return { color: col, bump };
}

// dimpled micro-texture used as a bump map
function dimpleTexture(W = 1024, H = 512) {
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d'); g.fillStyle = '#808080'; g.fillRect(0, 0, W, H);
  const R = VM.rand(4);
  for (let n = 0; n < 9000; n++) {
    const x = R() * W, y = R() * H, rr = 1.2 + R() * 1.6;
    const gr = g.createRadialGradient(x, y, 0, x, y, rr); gr.addColorStop(0, '#5a5a5a'); gr.addColorStop(1, 'rgba(128,128,128,0)');
    g.fillStyle = gr; g.fillRect(x - rr, y - rr, rr * 2, rr * 2);
  }
  return c;
}

// Creates a renderer canvas with the ball; returns { canvas, render(t, opts) }.
// look: 'studio' (lit, glossy), 'flat' (graphic, little shading), 'print' (high-contrast for halftone)
async function createMikasa({ size = 60, look = 'studio', key = [-2.5, 3, 4], keyColor = 0xffffff, rim = 0x6aa0ff, rimI = 1.2, colors, pattern = 'v200w' } = {}) {
  const THREE = await import(VEDIT.libs.three);
  const px = Math.round(Math.min(innerWidth, innerHeight) * size / 100);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1); renderer.setSize(px, px);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(20, 1, 0.1, 100); cam.position.set(0, 0, 6.1);
  let tex, bump;
  if (pattern === 'v200w') { const m = v200wRefMaps(); tex = new THREE.CanvasTexture(m.color); bump = new THREE.CanvasTexture(m.bump); }
  else { tex = new THREE.CanvasTexture(mikasaTexture(2048, 1024, colors)); bump = new THREE.CanvasTexture(dimpleTexture()); }
  tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  const mat = look === 'flat'
    ? new THREE.MeshLambertMaterial({ map: tex })
    : new THREE.MeshStandardMaterial({ map: tex, roughness: look === 'print' ? 0.9 : 0.5, metalness: 0, bumpMap: bump, bumpScale: 1.4 });
  const ball = new THREE.Mesh(new THREE.SphereGeometry(1, 128, 96), mat);
  ball.rotation.set(0.5, 0.3, 0.25);
  scene.add(ball);
  if (look === 'flat') {
    scene.add(new THREE.AmbientLight(0xffffff, 2.2));
    const k = new THREE.DirectionalLight(0xffffff, 0.9); k.position.set(...key); scene.add(k);
  } else {
    scene.add(new THREE.HemisphereLight(0xffffff, 0x223355, look === 'print' ? 1.4 : 0.55));
    const k = new THREE.DirectionalLight(keyColor, look === 'print' ? 2.4 : 3.2); k.position.set(...key); scene.add(k);
    const r = new THREE.DirectionalLight(rim, rimI); r.position.set(3, -1, -3); scene.add(r);
  }
  const canvas = renderer.domElement;
  Object.assign(canvas.style, { position: 'absolute', width: `${size}vmin`, height: `${size}vmin` });
  return {
    canvas, ball, THREE,
    render({ rx = 0.5, ry = 0.3, rz = 0.25 } = {}) { ball.rotation.set(rx, ry, rz); renderer.render(scene, cam); },
  };
}
