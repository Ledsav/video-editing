# Motion-design recipes

All snippets assume the scene contract (see SKILL.md). `t` is seconds since the scene starts.

## Text

```js
// Mask reveal per character (GSAP)
const chars = VM.split(document.querySelector('.title'));        // wraps chars in inline-block spans
document.querySelector('.title').style.overflow = 'hidden';
gsap.from(chars, { yPercent: 115, rotate: 6, duration: 0.6, ease: 'expo.out', stagger: 0.03, delay: 0.2 });

// Word-per-beat kinetic text without GSAP
const words = VM.split(el, 'words');
VM.onFrame((t) => words.forEach((w, i) => {
  const t0 = VM.beats[i * 2] ?? 0.2 + i * 0.4;
  const p = VM.prog(t, t0, 0.35, 'outBack');
  w.style.opacity = p; w.style.transform = `scale(${0.6 + 0.4 * p})`;
}));

// Typewriter with caret
VM.onFrame((t) => { const n = Math.floor(VM.prog(t, 0.3, 1.8) * text.length); el.textContent = text.slice(0, n) + (t % 0.8 < 0.4 ? '▍' : ''); });
```

## Shapes and lines

```js
// Draw any SVG path/circle/rect progressively
VM.onFrame((t) => VM.draw(pathEl, VM.prog(t, 0.2, 1.4, 'inOutCubic')));

// Morph-like transition: animate clip-path shapes
el.style.clipPath = `circle(${VM.prog(t, 0, 0.8, 'inOutExpo') * 150}% at 50% 50%)`;

// Keyframed position (arrays interpolate component-wise)
const [x, y] = VM.keys(t, [[0, [-40, 0]], [0.8, [0, 0], 'outExpo'], [3, [0, 0]], [3.4, [40, -10], 'inExpo']]);
```

## Physics and organic motion

```js
const s = VM.spring(t, 0.5, { stiffness: 200, damping: 10 });   // 0 -> 1 with overshoot
el.style.transform = `scale(${s})`;
const wobble = VM.noise(t * 1.5, 7) * 3;                          // smooth deterministic noise
```

## Data

```js
num.textContent = VM.count(t, 0.4, 1.6, 0, 12800, { sep: '.', suffix: ' km' });   // "12.800 km"
bar.style.transform = `scaleX(${VM.prog(t, 0.4, 1.6, 'outExpo') * value / max})`;
```
Charts: build with SVG (paths for lines, rects for bars) and reveal with `VM.draw` / scale transforms.
Label every axis value you animate; keep the final state on screen ≥ 1.5 s.

## Music sync

```js
const k = VM.beatIndex(t);          // which beat we're on
const hit = VM.pulse(t, 10);        // 1 on each beat, decays: scale/brightness accents
el.style.transform = `scale(${1 + 0.05 * hit})`;
```
`VM.beats` are relative to the scene start; they exist when the edit has a `sync.beats` file.

## Lottie (After Effects exports)

```html
<meta name="vedit:libs" content="lottie">
<div id="anim" style="position:absolute;inset:10vmin"></div>
<script>
  const P = VM.params({ animation: 'assets/rocket.json' });   // path relative to the edit
  lottie.loadAnimation({ container: document.getElementById('anim'), path: P.animation, renderer: 'svg', autoplay: false, loop: false });
  window.VM_READY = new Promise((r) => setTimeout(r, 300));   // let it parse
</script>
```
The runtime seeks every registered Lottie animation to `t` each frame.

## three.js

```js
window.VM_READY = (async () => {
  const THREE = await import(VEDIT.libs.three);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setSize(innerWidth, innerHeight); document.body.appendChild(renderer.domElement);
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.1, 500);
  // ... meshes, lights ...
  VM.onFrame((t) => { camera.position.z = 10 - t; renderer.render(scene, camera); });
})();
```
Addons (OrbitControls, loaders, postprocessing): `await import(VEDIT.libs.three_addons + 'loaders/GLTFLoader.js')`
(they import `three` by bare name: prefer core-only code, or inline what you need).

## Transitions between scenes

- Hard cut on a beat with a **match** (same colour block or shape continues): cleanest.
- Built-in: `crossfade`, `dip_black`, any xfade; designed: `shape_wipe`, `circle_reveal`, `bars_stagger`, `ink_spread`.
- In-scene exits: end each scene with its own 0.3–0.5 s exit so cuts feel intentional.

## Checklist before rendering

- [ ] Every scene previewed at 3–4 times, at the target aspect ratio
- [ ] Text readable for long enough, inside safe margins
- [ ] Palette and type consistent across scenes
- [ ] Big moves land on beats; scene lengths snap to the beat grid (`sync`)
- [ ] No element pops in/out without easing (unless it is a deliberate hard cut)
