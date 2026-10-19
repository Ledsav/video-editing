// Shared by the volleyball scenes (spike_seq.html, story.html): the anime lens post pass and the arena.

// lens post pass: barrel distortion, chromatic aberration, radial zoom blur, then the anime pass
// (posterised tones, ink outlines, halftone shadows) and a grade (saturation + tint).
function makeAnimePost(THREE, W, H) {
    const rt = new THREE.WebGLRenderTarget(W, H, { samples: 4, type: THREE.HalfFloatType });
    const lensMat = new THREE.ShaderMaterial({
      uniforms: { tDiffuse: { value: rt.texture }, k: { value: 0 }, ca: { value: 0.06 }, aspect: { value: W / H }, zoom: { value: 0 }, cel: { value: 0.75 }, px: { value: new THREE.Vector2(1 / W, 1 / H) }, center: { value: new THREE.Vector2(0.5, 0.5) }, sat: { value: 1 }, tint: { value: new THREE.Vector3(1, 1, 1) } },
      vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
      fragmentShader: `uniform sampler2D tDiffuse; uniform float k; uniform float ca; uniform float aspect; uniform float zoom; uniform vec2 center; uniform float cel; uniform vec2 px; uniform float sat; uniform vec3 tint; varying vec2 vUv;
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
          if (cel > 0.0) {
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
