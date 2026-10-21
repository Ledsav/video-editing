// Shared by the volleyball scenes (spike_seq.html, story.html): the anime lens post pass and the arena.

// lens post pass: barrel distortion, chromatic aberration, radial zoom blur, then the anime pass
// (posterised tones, ink outlines, halftone shadows) and a grade (saturation + tint).
function makeAnimePost(THREE, W, H) {
    const rt = new THREE.WebGLRenderTarget(W, H, { samples: 4, type: THREE.HalfFloatType });
    const lensMat = new THREE.ShaderMaterial({
      uniforms: { tDiffuse: { value: rt.texture }, k: { value: 0 }, ca: { value: 0.06 }, aspect: { value: W / H }, zoom: { value: 0 }, cel: { value: 0.75 }, px: { value: new THREE.Vector2(1 / W, 1 / H) }, center: { value: new THREE.Vector2(0.5, 0.5) }, sat: { value: 1 }, tint: { value: new THREE.Vector3(1, 1, 1) }, anime: { value: 1 }, time: { value: 0 } },
      vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
      fragmentShader: `uniform sampler2D tDiffuse; uniform float k; uniform float ca; uniform float aspect; uniform float zoom; uniform vec2 center; uniform float cel; uniform vec2 px; uniform float sat; uniform vec3 tint; uniform float anime; uniform float time; varying vec2 vUv;
        float hh(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        float hn(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
          return mix(mix(hh(i), hh(i + vec2(1.0, 0.0)), f.x), mix(hh(i + vec2(0.0, 1.0)), hh(i + vec2(1.0, 1.0)), f.x), f.y); }
        vec2 warp(vec2 uv, float kk) {            // barrel: centre magnified, edges compressed, corners stay put
          vec2 p = (uv - 0.5) * vec2(aspect, 1.0); float r2 = dot(p, p), rc2 = 0.25 * (aspect * aspect + 1.0);
          return 0.5 + p * ((1.0 + kk * r2) / (1.0 + kk * rc2)) / vec2(aspect, 1.0); }
        float tl(vec2 uv) { float L = dot(texture2D(tDiffuse, uv).rgb, vec3(0.333)); return L / (1.0 + L); }
        void main() {
          vec4 g = vec4(0.0); float r = 0.0, b = 0.0;
          if (zoom < 0.002) {
            g = texture2D(tDiffuse, warp(vUv, k));
            r = texture2D(tDiffuse, warp(vUv, k * (1.0 + ca))).r; b = texture2D(tDiffuse, warp(vUv, k * (1.0 - ca))).b;
          } else {                                   // radial zoom blur towards the point of action: speed + power
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
          // ---- anime pass (display space): posterised tones, ink outlines, halftone shadows ----
          if (cel > 0.0 && anime > 0.5) {
            // anime: three flat cel tones (cool shadows), hand-drawn outlines that wobble on twos, scratchy hatching in the
            // shadows (the impact frames' strokes, in colour), a soft glow off the brightest light
            vec3 c = gl_FragColor.rgb;
            float l = dot(c, vec3(0.299, 0.587, 0.114)), bt = floor(time * 12.0) / 12.0;
            float tq = l < 0.3 ? 0.19 : (l < 0.66 ? 0.5 : 0.86);
            vec3 cq = c * (tq + 0.02) / (l + 0.02);
            float m = dot(cq, vec3(0.333)); cq = mix(vec3(m), cq, 1.3);
            if (l < 0.3) cq *= vec3(0.94, 0.94, 1.06);                      // cool shadow paint
            cq = mix(c, cq, smoothstep(0.05, 0.12, l));                     // near-black stays black (the arena, the hair)
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
            float q = (floor(l * 4.0 + 0.5) / 4.0);                       // 4 tone bands
            vec3 cq = c * (q + 0.04) / (l + 0.04);
            float m = dot(cq, vec3(0.333)); cq = mix(vec3(m), cq, 1.25);  // a touch more saturation, like cel paint
            // ink: luminance edges of the warped image (Sobel-ish cross)
            vec2 o = px * 1.6;
            // compressed (L / (1 + L)) so bright HDR skin does not read as edges everywhere
            float lx = tl(warp(vUv + vec2(o.x, 0.0), k)) - tl(warp(vUv - vec2(o.x, 0.0), k));
            float ly = tl(warp(vUv + vec2(0.0, o.y), k)) - tl(warp(vUv - vec2(0.0, o.y), k));
            float edge = smoothstep(0.12, 0.32, sqrt(lx * lx + ly * ly));
            // halftone dots in the shadows (screen space)
            vec2 g = fract(gl_FragCoord.xy / 7.0) - 0.5;
            float dots = step(length(g), 0.5 * clamp((0.32 - l) / 0.32, 0.0, 1.0));
            vec3 outc = mix(cq, cq * 0.55, dots * 0.6);
            outc = mix(outc, vec3(0.04, 0.05, 0.1), edge * 0.85);
            gl_FragColor.rgb = mix(c, outc, cel);
          }
          // grade: saturation (0 = the grey past) and a tint
          float gl = dot(gl_FragColor.rgb, vec3(0.299, 0.587, 0.114));
          gl_FragColor.rgb = mix(vec3(gl), gl_FragColor.rgb, sat) * tint;
        }`,
      depthTest: false, depthWrite: false });
    const postScene = new THREE.Scene(), postCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    postScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), lensMat));
    return { rt, lensMat, postScene, postCam };
}

// arena: screen-space bokeh background, court (terracotta playing area, blue free zone), net, posts, light beams.
// Meshes are pushed into env (hidden in comic mode). Returns { bgTex, NETZ }.
function buildArena(THREE, scene, env) {
  const out = {};
    { // screen-space background: dark arena with out-of-focus lights
      const c = document.createElement('canvas'); c.width = 960; c.height = 540; const g = c.getContext('2d');
      const gr = g.createLinearGradient(0, 0, 0, 540); gr.addColorStop(0, '#060a16'); gr.addColorStop(0.55, '#0d1630'); gr.addColorStop(1, '#070a12');
      g.fillStyle = gr; g.fillRect(0, 0, 960, 540);
      const R = VM.rand(31);
      for (let i = 0; i < 46; i++) { const x = R() * 960, y = 60 + R() * 260, r = 4 + R() * 22, warm = R() > 0.3;
        const rg = g.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, warm ? 'rgba(255,214,140,0.55)' : 'rgba(140,170,255,0.4)'); rg.addColorStop(1, 'rgba(0,0,0,0)');
        g.fillStyle = rg; g.fillRect(x - r, y - r, r * 2, r * 2); }
      for (let i = 0; i < 9; i++) { const x = 40 + i * 110 + R() * 30; const rg = g.createRadialGradient(x, 30, 0, x, 30, 60);
        rg.addColorStop(0, 'rgba(255,245,220,0.9)'); rg.addColorStop(0.2, 'rgba(255,230,180,0.25)'); rg.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = rg; g.fillRect(x - 60, 0, 120, 90); }
      const bgTex = new THREE.CanvasTexture(c); bgTex.colorSpace = THREE.SRGBColorSpace; scene.background = bgTex; out.bgTex = bgTex;
    }
    const NETZ = 0.55;
    { // court floor
      const c = document.createElement('canvas'); c.width = 2048; c.height = 4096; const g = c.getContext('2d');
      const S = 2048 / 14;                                  // px per metre: 14 m wide x 28 m long
      g.fillStyle = '#1c3a8e'; g.fillRect(0, 0, 2048, 4096);            // free zone: Mikasa blue
      const cx = 1024, cz = 2048 - NETZ * S;                 // court origin (x = 0, z = net)
      g.fillStyle = '#c8653a'; g.fillRect(cx - 4.5 * S, cz - 9 * S, 9 * S, 18 * S);   // playing area: terracotta orange
      g.strokeStyle = '#e9ecf2'; g.lineWidth = 0.05 * S;
      g.strokeRect(cx - 4.5 * S, cz - 9 * S, 9 * S, 18 * S);
      [0, -3, 3].forEach((dz) => { g.beginPath(); g.moveTo(cx - 4.5 * S, cz - dz * S); g.lineTo(cx + 4.5 * S, cz - dz * S); g.stroke(); });
      const R = VM.rand(5); g.globalAlpha = 0.05;
      for (let i = 0; i < 4000; i++) { g.fillStyle = R() > 0.5 ? '#fff' : '#000'; g.fillRect(R() * 2048, R() * 4096, 2, 2); }
      const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
      const floor = new THREE.Mesh(new THREE.PlaneGeometry(14, 28), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.68, metalness: 0.0 }));
      floor.rotation.x = -Math.PI / 2; floor.position.z = 0; floor.receiveShadow = true; scene.add(floor); env.push(floor);
      // the canvas is drawn with +z (towards the net) upwards; plane uv v grows towards -z after the rotation
      tex.center.set(0.5, 0.5); tex.rotation = Math.PI; tex.repeat.set(-1, 1);
    }
    { // net: mesh texture, white tape, antennas, posts
      const c = document.createElement('canvas'); c.width = 1900; c.height = 200; const g = c.getContext('2d');
      g.strokeStyle = 'rgba(10,10,14,0.95)'; g.lineWidth = 2.2;
      for (let x = 0; x <= 1900; x += 20) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, 200); g.stroke(); }
      for (let y = 0; y <= 200; y += 20) { g.beginPath(); g.moveTo(0, y); g.lineTo(1900, y); g.stroke(); }
      g.fillStyle = '#f2f2f2'; g.fillRect(0, 0, 1900, 14); g.fillRect(0, 192, 1900, 8);
      const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
      const net = new THREE.Mesh(new THREE.PlaneGeometry(9.5, 1.0), new THREE.MeshStandardMaterial({ map: tex, transparent: true, side: THREE.DoubleSide, roughness: 0.8, alphaTest: 0.05 }));
      net.position.set(0, 2.43 - 0.5, NETZ); scene.add(net); env.push(net);
      for (const sx of [-1, 1]) {
        const ant = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 0.01, 1.8, 8), new THREE.MeshStandardMaterial({ color: 0xffffff }));
        ant.position.set(sx * 4.5, 2.43, NETZ); scene.add(ant); env.push(ant);
        const post = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 2.6, 16), new THREE.MeshStandardMaterial({ color: 0x1b2440, roughness: 0.4 }));
        post.position.set(sx * 5.4, 1.3, NETZ); scene.add(post); env.push(post);
      }
    }
    // light beams from the roof (additive cones)
    const beamMat = new THREE.MeshBasicMaterial({ color: 0xfff1d0, transparent: true, opacity: 0.006, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    [[-1.2, 0.0], [1.8, -1.5], [-3.5, 2.5]].forEach(([x, z]) => { const b = new THREE.Mesh(new THREE.ConeGeometry(0.9, 14, 32, 1, true), beamMat); b.position.set(x, 7, z); scene.add(b); env.push(b); });

  out.NETZ = NETZ; return out;
}

// ink impact frame (anime "sakuga" impact frames: black and white brush drawing, boiling lines). Reads the scene render (the
// character lit by white materials on a transparent background) and redraws it: light/shadow split into two flat tones along a
// ragged edge, scratchy hatching across that edge (light strokes into the dark, dark strokes into the light), outlines in the
// opposite tone, rough energy streaks radiating from the hit, everything wobbling on twos. ink/paper/accent are the palette.
function makeInkPass(THREE, W, H, src) {
  const inkMat = new THREE.ShaderMaterial({
    uniforms: { tDiffuse: { value: src }, px: { value: new THREE.Vector2(1 / W, 1 / H) }, aspect: { value: W / H }, time: { value: 0 },
      center: { value: new THREE.Vector2(0.5, 0.5) }, dir: { value: new THREE.Vector2(0, -1) }, thr: { value: 0.42 }, band: { value: 0.22 },
      ink: { value: new THREE.Color(0xffffff) }, paper: { value: new THREE.Color(0x000000) }, streaks: { value: 1 }, seed: { value: 0 },
      bulge: { value: 0 }, flashR: { value: 0 }, dbg: { value: 0 }, lineW: { value: 1.6 }, core: { value: 1 } },
    vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
    fragmentShader: `uniform sampler2D tDiffuse; uniform vec2 px; uniform float aspect; uniform float time; uniform vec2 center; uniform vec2 dir;
      uniform float thr; uniform float band; uniform vec3 ink; uniform vec3 paper; uniform float streaks; uniform float seed;
      uniform float bulge; uniform float flashR; uniform float dbg; uniform float lineW; uniform float core; varying vec2 vUv;
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7)) + seed * 17.0) * 43758.5453); }
      float noise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y); }
      float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { s += a * noise(p); p *= 2.03; a *= 0.5; } return s; }
      vec4 tap(vec2 uv) { vec4 c = texture2D(tDiffuse, uv); float L = dot(c.rgb, vec3(0.299, 0.587, 0.114)); return vec4(L / (1.0 + L) * 1.7, c.a, 0.0, 0.0); }
      void main() {
        float bt = floor(time * 12.0) / 12.0;                                   // the drawing boils on twos
        // fisheye centred on the ball: the drawing is sampled closer to the centre the nearer it is (bulge 0 = none)
        vec2 dc = (vUv - center) * vec2(aspect, 1.0); float rc = length(dc), rn = rc / 1.3;
        vec2 fuv = center + dc * (pow(max(rn, 1e-4), 1.0 + bulge) / max(rn, 1e-4)) / vec2(aspect, 1.0);
        vec2 q = fuv * vec2(aspect, 1.0);
        vec2 wob = (vec2(fbm(q * 5.0 + bt * 7.1), fbm(q * 5.0 + 13.0 + bt * 5.3)) - 0.5) * px * 7.0;
        vec2 uv = fuv + wob;
        vec4 c = tap(uv); float l = c.x, A = c.y;
        if (dbg > 0.5) { gl_FragColor = vec4(vec3(l * 0.5), 1.0); if (A < 0.5) gl_FragColor.b = 0.3; return; }   // debug: the light the drawing reads (x0.5), background blue
        // fill: two tones along a ragged brush edge
        float jit = (fbm(q * 34.0 + bt * 3.0) - 0.5) * 0.16;
        float d = l - thr + jit;
        float fill = step(0.0, d) * step(0.5, A);
        // hatching across the edge: dashes of parallel strokes, densest at the edge
        vec2 hd = normalize(vec2(0.62, 0.78));
        float along = dot(q, vec2(-hd.y, hd.x)), across = dot(q, hd) * 230.0 + fbm(q * 9.0 + bt) * 3.0;
        float id = floor(across), line = abs(fract(across) - 0.5);
        float dash = step(0.42, noise(vec2(along * 26.0 + id * 1.7, id * 0.37 + bt * 11.0)));
        float k = clamp(1.0 - abs(d) / band, 0.0, 1.0);
        float hatch = step(line, 0.07 + 0.33 * k * k) * dash * step(0.01, k) * step(0.5, A);
        // outlines: silhouette (coverage) and inner light edges, thickness breathing with noise
        float r = (1.6 + 1.4 * noise(q * 60.0 + bt * 5.0)) * lineW;
        vec4 e1 = tap(uv + vec2(px.x * r, 0.0)), e2 = tap(uv - vec2(px.x * r, 0.0)), e3 = tap(uv + vec2(0.0, px.y * r)), e4 = tap(uv - vec2(0.0, px.y * r));
        float sil = length(vec2(e1.y - e2.y, e3.y - e4.y));
        float inner = length(vec2(e1.x - e2.x, e3.x - e4.x)) * step(0.5, A);
        float edge = max(step(0.35, sil), step(0.22 + 0.1 * noise(q * 40.0), inner));
        // energy streaks from the hit (outside the figure): elongated noise in polar space, ragged ends
        vec2 dv = (vUv - center) * vec2(aspect, 1.0); float rr = length(dv), th = atan(dv.y, dv.x);
        float s1 = fbm(vec2(th * 9.0, log(rr + 0.002) * 1.6 - bt * 1.5) + seed);
        float s2 = noise(vec2(th * 60.0, rr * 4.0 + bt * 2.0));
        float s3 = noise(vec2(th * 140.0 + seed, log(rr + 0.002) * 0.7 - bt * 3.0));      // thin, long strokes
        float streak = max(step(0.66 + 0.12 * smoothstep(0.1, 0.6, rr), s1 + 0.1 * s2) * step(0.35, s3), step(0.86, s3) * step(0.5, s1))
          * smoothstep(0.06, 0.2, rr) * (1.0 - step(0.5, A)) * streaks;
        float burst = (1.0 - smoothstep(0.02, 0.06 + 0.03 * noise(vec2(th * 8.0, bt * 9.0)), rr)) * streaks * core;   // the white core of the hit (from contact on)
        // the flash out of the ball: a disc with a torn edge and spikes shooting past it
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
