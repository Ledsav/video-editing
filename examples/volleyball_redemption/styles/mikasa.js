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
async function createMikasa({ size = 60, look = 'studio', key = [-2.5, 3, 4], keyColor = 0xffffff, rim = 0x6aa0ff, rimI = 1.2, colors } = {}) {
  const THREE = await import(VEDIT.libs.three);
  const px = Math.round(Math.min(innerWidth, innerHeight) * size / 100);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1); renderer.setSize(px, px);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(20, 1, 0.1, 100); cam.position.set(0, 0, 6.1);
  const tex = new THREE.CanvasTexture(mikasaTexture(2048, 1024, colors)); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  const bump = new THREE.CanvasTexture(dimpleTexture());
  const mat = look === 'flat'
    ? new THREE.MeshLambertMaterial({ map: tex })
    : new THREE.MeshStandardMaterial({ map: tex, roughness: look === 'print' ? 0.9 : 0.42, metalness: 0, bumpMap: bump, bumpScale: 0.6 });
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
