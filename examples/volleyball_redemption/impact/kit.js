// Volleyball kit painted onto a VRoid body texture (Mikasa colours): fitted jersey with number and short sleeves,
// shorts with a side stripe, knee pads, socks. The VRoid clothes (hoodie, trousers) are hidden.
// UV layout of the VRoid male body (in 1024 units): arms x 0-245 / 780-1024, y 0 (shoulder) -> 500 (wrist);
// legs x 0-245 / 780-1024, y 505 (top of thigh) -> 940 (ankle); torso x 245-780, y 0 (neck) -> 440; hips y 440-600.
// UV-space mask of the triangles skinned mostly to the hands and fingers (their UV islands sit inside the torso area)
function handMask(THREE, model, size, re = /(Left|Right)Hand/, minW = 0) {
  const c = document.createElement('canvas'); c.width = c.height = size; const g = c.getContext('2d'); g.fillStyle = '#fff';
  model.traverse((o) => {
    if (!o.isSkinnedMesh || !/Body_00_SKIN/.test(o.material.name || '')) return;
    const geo = o.geometry, uv = geo.attributes.uv, si = geo.attributes.skinIndex, sw = geo.attributes.skinWeight, idx = geo.index, bones = o.skeleton.bones;
    const isHand = (v) => { let best = 0, b = -1, tot = 0; for (let k = 0; k < 4; k++) { const w = sw.getComponent(v, k), bi = si.getComponent(v, k); if (re.test(bones[bi].name)) tot += w; if (w > best) { best = w; b = bi; } }
      return minW > 0 ? tot >= minW : b >= 0 && re.test(bones[b].name); };
    const n = idx ? idx.count : uv.count;
    for (let t = 0; t < n; t += 3) {
      const a = idx ? idx.getX(t) : t, b = idx ? idx.getX(t + 1) : t + 1, d = idx ? idx.getX(t + 2) : t + 2;
      if (!(minW > 0 ? isHand(a) && isHand(b) && isHand(d) : isHand(a) || isHand(b) || isHand(d))) continue;
      g.beginPath(); g.moveTo(uv.getX(a) * size, uv.getY(a) * size); g.lineTo(uv.getX(b) * size, uv.getY(b) * size); g.lineTo(uv.getX(d) * size, uv.getY(d) * size); g.closePath(); g.fill();
      g.lineWidth = 3; g.strokeStyle = '#fff'; g.stroke();
    }
  });
  return c;
}
function paintKit(THREE, model, opt = {}) {
  const HANDS = handMask(THREE, model, 1024);
  const NECK = handMask(THREE, model, 1024, /^(Neck|Head)$/, opt.neckW ?? 0.5);   // neck skin: weighted mostly to the neck/head
  const BLUE = opt.blue || '#1f3fa8', NAVY = opt.navy || '#0f1d4a', YEL = opt.yellow || '#f6c300', WHITE = '#f4f4f2';
  const NUM = opt.number ?? '7';
  let done = false, painted = null;   // the body is split into several meshes sharing one texture: paint once, assign to all
  model.traverse((o) => {
    if (!o.isMesh) return;
    const name = o.material.name || '';
    if (/Tops_|Bottoms_/.test(name)) { o.visible = false; return; }
    if (/Shoes_/.test(name)) { o.material = o.material.clone(); o.material.map = null; o.material.color = new THREE.Color(0xeeeef0); return; }   // white court shoes
    if (!/Body_00_SKIN/.test(name) || !o.material.map) return;
    if (painted) { o.material = o.material.clone(); o.material.map = painted.map; o.material.normalMap = painted.normalMap; if (painted.normalScale) o.material.normalScale = painted.normalScale; o.material.needsUpdate = true; return; }
    const src = o.material.map, im = src.image, S = im.width / 1024;
    const c = document.createElement('canvas'); c.width = im.width; c.height = im.height; let g = c.getContext('2d');
    g.drawImage(im, 0, 0);
    g.globalCompositeOperation = 'multiply'; g.fillStyle = opt.skin || '#d9ab8f'; g.fillRect(0, 0, c.width, c.height);   // sun-warmed skin (the bare texture blows out under the arena lights)
    g.globalCompositeOperation = 'source-over';
    g.save(); g.scale(S, S);
    const R = (x, y, w, h, col) => { g.fillStyle = col; g.fillRect(x, y, w, h); };   // (uses the current layer)
    // the kit is drawn on its own layer, the hand islands erased from it, then laid over the skin
    const skinG = g, K = document.createElement('canvas'); K.width = c.width; K.height = c.height;
    g = K.getContext('2d'); g.scale(S, S);
    // ---- jersey: torso, V-neck collar, side panels, number ----
    R(245, 30, 535, 412, BLUE);
    g.save(); g.globalCompositeOperation = 'destination-out'; g.beginPath(); g.moveTo(450, 0); g.lineTo(450, 28); g.lineTo(512, 120); g.lineTo(574, 28); g.lineTo(574, 0); g.closePath(); g.fill();
    g.fillRect(245, 0, 535, 28); g.restore();                                                                                     // V-neck and neck: cut out (bare skin, no fabric)
    g.strokeStyle = YEL; g.lineWidth = 9; g.beginPath(); g.moveTo(444, 26); g.lineTo(512, 126); g.lineTo(580, 26); g.stroke();
    g.beginPath(); g.moveTo(245, 34); g.lineTo(444, 34); g.moveTo(580, 34); g.lineTo(780, 34); g.stroke();                      // collar line at the back
    R(330, 120, 26, 320, YEL); R(668, 120, 26, 320, YEL);                                                                        // side panels
    g.fillStyle = WHITE; g.font = `400 150px Anton, 'Bebas Neue', Impact, sans-serif`; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.lineWidth = 10; g.strokeStyle = NAVY; g.strokeText(NUM, 512, 255); g.fillText(NUM, 512, 255);
    R(245, 425, 535, 18, YEL);                                                                                                    // hem
    // ---- short sleeves with a yellow cuff ----
    for (const x of [0, 780]) { R(x, 0, 245, 175, BLUE); R(x, 165, 245, 14, YEL); }                                       // sleeves to mid upper arm: cover the deltoid
    // ---- shorts: hips + top of the thighs, side stripe ----
    R(245, 440, 535, 165, NAVY); R(470, 590, 84, 70, NAVY);                                                                     // (crotch gusset)
    for (const x of [0, 780]) { R(x, 505, 245, 118, NAVY); R(x, 612, 245, 12, YEL); }
    // ---- knee pads ----
    for (const x of [0, 780]) { R(x, 690, 245, 78, '#16181d'); R(x, 690, 245, 6, '#3a3d46'); R(x, 762, 245, 6, '#3a3d46'); }
    // ---- socks ----
    for (const x of [0, 780]) { R(x, 862, 245, 162, WHITE); R(x, 868, 245, 8, BLUE); R(x, 882, 245, 6, YEL); }
    g.setTransform(1, 0, 0, 1, 0, 0);
    // collar: a smooth trim band along the neck line (the raw mask is triangle-jagged), then the neck cut out with a soft edge
    // blur then threshold: a smooth, crisp outline (dilated when the threshold is low)
    const soft = (src, blur, thr, col) => { const k = document.createElement('canvas'); k.width = c.width; k.height = c.height; const kg = k.getContext('2d');
      kg.filter = `blur(${blur * S}px)`; kg.drawImage(src, 0, 0, c.width, c.height); kg.filter = 'none';
      const d = kg.getImageData(0, 0, k.width, k.height), p = d.data;
      for (let i = 3; i < p.length; i += 4) { const a = p[i]; p[i] = a > thr + 12 ? 255 : a < thr - 12 ? 0 : Math.round((a - thr + 12) / 24 * 255); }
      kg.putImageData(d, 0, 0);
      if (col) { kg.globalCompositeOperation = 'source-in'; kg.fillStyle = col; kg.fillRect(0, 0, k.width, k.height); } return k; };
    g.globalCompositeOperation = 'source-atop'; g.drawImage(soft(NECK, 6, 18, YEL), 0, 0);                                   // trim band
    g.globalCompositeOperation = 'destination-out'; g.drawImage(HANDS, 0, 0, c.width, c.height); g.drawImage(soft(NECK, 4, 110), 0, 0);
    g = skinG; g.restore(); g.drawImage(K, 0, 0);
    const t = new THREE.CanvasTexture(c); t.flipY = src.flipY; t.colorSpace = src.colorSpace; t.wrapS = src.wrapS; t.wrapT = src.wrapT; t.anisotropy = 8;
    o.material = o.material.clone(); o.material.map = t; o.material.needsUpdate = true; done = true;
    if (opt.relief !== false) kitNormalMap(THREE, o, { number: NUM, bakeK: opt.bakeK, hands: HANDS, cloth: K });
    painted = { map: o.material.map, normalMap: o.material.normalMap, normalScale: o.material.normalScale };
  });
  return done;
}

// Fabric relief for the kit, baked into the body's normal map: the model's own anatomy normals + a height field for the
// clothes (knit, twill, raised seams and hems, heat-pressed number, quilted knee pads, waistband), converted to normals.
function kitNormalMap(THREE, mesh, opt = {}) {
  const base = mesh.material.normalMap, map = mesh.material.map;
  const N = 2048, S = N / 1024;
  const hc = document.createElement('canvas'); hc.width = hc.height = N; const h = hc.getContext('2d');
  h.fillStyle = '#808080'; h.fillRect(0, 0, N, N);
  h.save(); h.scale(S, S);
  const R = (x, y, w, hh, v) => { h.fillStyle = `rgb(${v},${v},${v})`; h.fillRect(x, y, w, hh); };
  const ridge = (x0, y0, x1, y1, w, v) => { h.strokeStyle = `rgb(${v},${v},${v})`; h.lineWidth = w; h.lineCap = 'round'; h.beginPath(); h.moveTo(x0, y0); h.lineTo(x1, y1); h.stroke(); };
  h.restore();
  // fabric textures as pixel patterns, written per region
  const img = h.getImageData(0, 0, N, N), px = img.data;
  const inRect = (x, y, x0, y0, w, hh) => x >= x0 * S && x < (x0 + w) * S && y >= y0 * S && y < (y0 + hh) * S;
  const knit = (x, y) => { const a = Math.sin(x * 0.42) * Math.sin(y * 0.42 + (Math.floor(y / 15) % 2) * 1.6); return 128 + 12 * a; };          // mesh knit (coarse: no aliasing)
  const twill = (x, y) => 128 + 10 * Math.sin((x + y) * 0.3);                                                                              // diagonal twill
  const quilt = (x, y) => 128 + 70 * Math.pow(Math.abs(Math.sin(y * 0.11)), 0.5) - 30;                                                      // padded ribs
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    let v = 128;
    const torso = inRect(x, y, 245, 30, 535, 412), sleeve = inRect(x, y, 0, 0, 245, 175) || inRect(x, y, 780, 0, 244, 175);
    const shorts = inRect(x, y, 245, 440, 535, 165) || inRect(x, y, 0, 505, 245, 118) || inRect(x, y, 780, 505, 244, 118);
    const pad = inRect(x, y, 0, 690, 245, 78) || inRect(x, y, 780, 690, 244, 78);
    const sock = inRect(x, y, 0, 862, 245, 162) || inRect(x, y, 780, 862, 244, 162);
    if (torso || sleeve) v = knit(x, y); else if (shorts) v = twill(x, y); else if (pad) v = quilt(x, y); else if (sock) v = 128 + 16 * Math.sin(x * 0.7);   // ribbed sock
    const i = (y * N + x) * 4; px[i] = px[i + 1] = px[i + 2] = v;
  }
  h.putImageData(img, 0, 0);
  // seams, hems, collar, side panels, waistband, printed number: raised ridges drawn over the fabric (blurred = soft relief)
  if (opt.cloth) { const m = document.createElement('canvas'); m.width = m.height = N; const mg = m.getContext('2d'); mg.drawImage(opt.cloth, 0, 0, N, N);
    const md = mg.getImageData(0, 0, N, N).data, d = h.getImageData(0, 0, N, N);
    for (let i = 0; i < md.length; i += 4) if (md[i + 3] < 128) d.data[i] = d.data[i + 1] = d.data[i + 2] = 128;   // no fabric on bare skin
    h.putImageData(d, 0, 0); }
  if (opt.hands) { const m = document.createElement('canvas'); m.width = m.height = N; const mg = m.getContext('2d'); mg.drawImage(opt.hands, 0, 0, N, N);
    const md = mg.getImageData(0, 0, N, N).data, d = h.getImageData(0, 0, N, N);
    for (let i = 0; i < md.length; i += 4) if (md[i + 3] > 0) d.data[i] = d.data[i + 1] = d.data[i + 2] = 128;
    h.putImageData(d, 0, 0); }
  h.save(); h.scale(S, S); h.filter = 'blur(1.2px)';
  ridge(444, 26, 512, 126, 7, 210); ridge(512, 126, 580, 26, 7, 210); ridge(245, 34, 444, 34, 6, 200); ridge(580, 34, 780, 34, 6, 200);   // collar
  for (const x of [330, 356, 668, 694]) ridge(x, 120, x, 440, 4, 190);                                                                     // side panel seams
  ridge(245, 434, 780, 434, 10, 200);                                                                                                       // jersey hem
  for (const x of [0, 780]) { ridge(x, 172, x + 245, 172, 9, 205); ridge(x, 618, x + 245, 618, 8, 200); }                                  // sleeve cuffs, shorts hems
  ridge(245, 448, 780, 448, 12, 215);                                                                                                       // waistband
  for (const x of [0, 780]) { ridge(x, 690, x + 245, 690, 5, 60); ridge(x, 768, x + 245, 768, 5, 60); }                                     // pad edges sink in
  h.fillStyle = 'rgb(185,185,185)'; h.font = `400 150px Anton, 'Bebas Neue', Impact, sans-serif`; h.textAlign = 'center'; h.textBaseline = 'middle';
  h.fillText(opt.number ?? '7', 512, 255);                                                                                                  // heat-pressed number
  h.restore();
  // height -> tangent-space normal, blended onto the anatomy normals (detail added in xy, renormalised)
  const H = h.getImageData(0, 0, N, N).data;
  const bc = document.createElement('canvas'); bc.width = bc.height = N; const b = bc.getContext('2d');
  if (base && base.image) b.drawImage(base.image, 0, 0, N, N); else { b.fillStyle = 'rgb(128,128,255)'; b.fillRect(0, 0, N, N); }
  const out = b.getImageData(0, 0, N, N), o = out.data, k = opt.strength ?? 4;
  const hv = (x, y) => H[((Math.min(N - 1, Math.max(0, y)) * N) + Math.min(N - 1, Math.max(0, x))) * 4] / 255;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const dx = (hv(x + 1, y) - hv(x - 1, y)) * k, dy = (hv(x, y + 1) - hv(x, y - 1)) * k, i = (y * N + x) * 4;
    let nx = o[i] / 127.5 - 1 - dx, ny = o[i + 1] / 127.5 - 1 + dy, nz = o[i + 2] / 127.5 - 1;
    const l = Math.hypot(nx, ny, nz) || 1; o[i] = (nx / l + 1) * 127.5; o[i + 1] = (ny / l + 1) * 127.5; o[i + 2] = (nz / l + 1) * 127.5;
  }
  b.putImageData(out, 0, 0);
  // the toon ramp flattens fine normals: bake the relief into the colour too (light from the upper left), plus soft folds
  if (map && map.image && map.image.getContext) {
    const g = map.image.getContext('2d'), W = map.image.width, sc = W / N, col = g.getImageData(0, 0, W, W), cp = col.data;
    for (let y = 0; y < W; y++) for (let x = 0; x < W; x++) {
      const X = Math.floor(x / sc), Y = Math.floor(y / sc), dx = hv(X + 1, Y) - hv(X - 1, Y), dy = hv(X, Y + 1) - hv(X, Y - 1);
      const hh = hv(X, Y) - 0.5; if (Math.abs(dx) + Math.abs(dy) + Math.abs(hh) < 0.004) continue;
      const shade = Math.max(0.55, Math.min(1.25, 1 + (-dx * 0.7 - dy * 0.7) * (opt.bakeK ?? 5) + hh * 0.35)), i = (y * W + x) * 4;
      cp[i] = Math.min(255, cp[i] * shade); cp[i + 1] = Math.min(255, cp[i + 1] * shade); cp[i + 2] = Math.min(255, cp[i + 2] * shade);
    }
    g.putImageData(col, 0, 0);
    g.save(); g.scale(W / 1024, W / 1024); g.filter = 'blur(6px)'; g.globalCompositeOperation = 'multiply'; g.strokeStyle = 'rgba(40,50,90,0.35)'; g.lineCap = 'round';
    const fold = (pts, w) => { g.lineWidth = w; g.beginPath(); g.moveTo(...pts[0]); for (const p of pts.slice(1)) g.lineTo(...p); g.stroke(); };
    fold([[270, 405], [380, 395], [470, 410]], 10); fold([[560, 410], [650, 396], [760, 405]], 10);              // jersey bunching above the hem
    fold([[262, 60], [280, 140], [290, 230]], 12); fold([[762, 60], [744, 140], [734, 230]], 12);               // armpit folds (back edges)
    fold([[290, 470], [400, 500], [500, 470]], 9); fold([[530, 470], [630, 500], [740, 470]], 9);               // shorts under the waistband
    for (const x of [0, 780]) { fold([[x + 30, 540], [x + 120, 590], [x + 215, 545]], 9); fold([[x + 20, 130], [x + 120, 150], [x + 225, 130]], 7); }   // shorts legs, sleeves
    g.restore(); map.needsUpdate = true;
  }
  const t = new THREE.CanvasTexture(bc); const ref = base || map; t.flipY = ref.flipY; t.wrapS = ref.wrapS; t.wrapT = ref.wrapT; t.colorSpace = THREE.NoColorSpace;
  mesh.material.normalMap = t; if (!base) mesh.material.normalScale = new THREE.Vector2(1, 1); mesh.material.needsUpdate = true;
  return t;
}
