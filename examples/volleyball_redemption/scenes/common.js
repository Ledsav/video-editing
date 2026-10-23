// Shared design system for the "Rise Again" scenes: palette, the hero ball, grain, text reveals.
// Everything here is a pure function of time (called from VM.onFrame).
const C = {
  ink: '#0a1020', ink2: '#141d34', cream: '#f3ede2', orange: '#ff6b2c', gold: '#ffb547',
  blue: '#5b7fd6', steel: '#8ea0c4', red: '#e8473a',
};
const DISPLAY = "'Anton', 'Bebas Neue', sans-serif";
const TEXT = "'Montserrat', 'Inter', sans-serif";

function el(tag, css = {}, parent = document.getElementById('stage') || document.body, html = '') {
  const e = document.createElement(tag);
  Object.assign(e.style, css);
  if (html) e.innerHTML = html;
  parent.appendChild(e);
  return e;
}

// ---- the hero: a stylised volleyball (cream + orange panels, spin via the inner group) ----
let _ballN = 0;
function makeBall(parent, sizeVmin, opts = {}) {
  const id = `b${_ballN++}`;
  const panel = opts.panel || C.orange, base = opts.base || C.cream, seam = opts.seam || 'rgba(10,16,32,0.55)';
  const seg = (k) => `<g transform="rotate(${k * 120})">
      <path d="M0 0 C 14 -30, 40 -44, 70 -40 L 70 -18 C 44 -22, 22 -8, 10 12 Z" fill="${k === 1 ? base : panel}"/>
      <path d="M0 0 C 14 -30, 40 -44, 70 -40" fill="none" stroke="${seam}" stroke-width="2.2"/>
      <path d="M10 12 C 22 -8, 44 -22, 70 -18" fill="none" stroke="${seam}" stroke-width="2.2"/>
    </g>`;
  const wrap = document.createElement('div');
  Object.assign(wrap.style, { position: 'absolute', width: `${sizeVmin}vmin`, height: `${sizeVmin}vmin`,
    left: '0', top: '0', marginLeft: `${-sizeVmin / 2}vmin`, marginTop: `${-sizeVmin / 2}vmin`, willChange: 'transform' });
  wrap.innerHTML = `<svg viewBox="-50 -50 100 100" width="100%" height="100%" style="overflow:visible">
    <defs>
      <clipPath id="${id}c"><circle r="49"/></clipPath>
      <radialGradient id="${id}s" cx="-0.35" cy="-0.4" r="1.25" gradientUnits="objectBoundingBox" gradientTransform="translate(0.5 0.5)">
        <stop offset="0" stop-color="#fff" stop-opacity="0.35"/><stop offset="0.45" stop-color="#fff" stop-opacity="0"/>
        <stop offset="0.8" stop-color="#000" stop-opacity="0.35"/><stop offset="1" stop-color="#000" stop-opacity="0.6"/>
      </radialGradient>
      <radialGradient id="${id}r" r="0.5"><stop offset="0.82" stop-color="${opts.rim || '#000'}" stop-opacity="0"/>
        <stop offset="1" stop-color="${opts.rim || '#000'}" stop-opacity="${opts.rim ? 0.9 : 0}"/></radialGradient>
    </defs>
    <g clip-path="url(#${id}c)">
      <circle r="50" fill="${base}"/>
      <g class="spin">${seg(0)}${seg(1)}${seg(2)}</g>
      <circle r="50" fill="url(#${id}s)"/>
      <circle r="50" fill="url(#${id}r)" class="rim"/>
    </g>
  </svg>`;
  parent.appendChild(wrap);
  const spin = wrap.querySelector('.spin');
  return {
    el: wrap, size: sizeVmin,
    // x, y in vw/vh (centre); rot in degrees; scale; sx/sy squash
    set({ x = 50, y = 50, rot = 0, scale = 1, sx = 1, sy = 1, opacity = 1 } = {}) {
      wrap.style.transform = `translate(${x}vw, ${y}vh) scale(${scale * sx}, ${scale * sy})`;
      wrap.style.opacity = opacity;
      spin.setAttribute('transform', `rotate(${rot})`);
    },
  };
}

// soft contact shadow on the floor
function makeShadow(parent) {
  return el('div', { position: 'absolute', left: 0, top: 0, width: '20vmin', height: '3vmin', marginLeft: '-10vmin', marginTop: '-1.5vmin',
    borderRadius: '50%', background: 'radial-gradient(closest-side, rgba(0,0,0,0.65), rgba(0,0,0,0))' }, parent);
}

// ---- film grain + vignette (deterministic: tile chosen per frame) ----
function addFinish({ grain = 0.08, vignette = 0.55 } = {}) {
  const tiles = [];
  const rnd = VM.rand(42);
  for (let k = 0; k < 6; k++) {
    const c = document.createElement('canvas'); c.width = c.height = 220;
    const g = c.getContext('2d'), d = g.createImageData(220, 220);
    for (let i = 0; i < d.data.length; i += 4) { const v = rnd() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
    g.putImageData(d, 0, 0); tiles.push(c.toDataURL());
  }
  const vig = el('div', { position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 50,
    background: `radial-gradient(ellipse 75% 70% at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,${vignette}) 100%)` }, document.body);
  const gr = el('div', { position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 51, opacity: grain,
    mixBlendMode: 'overlay', backgroundSize: '220px 220px' }, document.body);
  VM.onFrame((t) => { gr.style.backgroundImage = `url(${tiles[Math.floor(t * 24) % tiles.length]})`; });
  return { vig, gr };
}

// chapter tag, top-left: "01 — THE DREAM"
function chapterTag(num, label, t0 = 0.3, t1 = 99) {
  const tag = el('div', { position: 'absolute', left: '7vw', top: '9vh', font: `600 1.7vmin ${TEXT}`, letterSpacing: '0.45em',
    color: C.cream, zIndex: 40, display: 'flex', alignItems: 'center', gap: '1.4vmin', opacity: 0 });
  tag.innerHTML = `<span style="color:${C.orange}">${num}</span><span class="bar" style="display:inline-block;width:5vmin;height:0.22vmin;background:currentColor;transform-origin:left"></span><span>${label}</span>`;
  const bar = tag.querySelector('.bar');
  VM.onFrame((t) => {
    const a = VM.env(t, t0, t1, 0.5, 0.3);
    tag.style.opacity = a;
    tag.style.transform = `translateX(${(1 - VM.prog(t, t0, 0.7, 'outExpo')) * -2}vw)`;
    bar.style.transform = `scaleX(${VM.prog(t, t0 + 0.1, 0.7, 'outExpo')})`;
  });
  return tag;
}

// masked per-character rise: returns an updater(t)
function riseText(node, { t0 = 0, out = 99, stagger = 0.03, dur = 0.6, outDur = 0.3, from = 112, mode = 'chars' } = {}) {
  node.style.overflow = 'hidden';
  const parts = VM.split(node, mode);
  return (t) => parts.forEach((p, i) => {
    const pin = VM.prog(t, t0 + i * stagger, dur, 'outExpo');
    const pout = VM.prog(t, out + i * stagger * 0.5, outDur, 'inExpo');
    p.style.transform = `translateY(${(1 - pin) * from - pout * from}%)`;
  });
}

// soft word-by-word fade with blur (reflective lines)
function softWords(node, { t0 = 0, out = 99, stagger = 0.12, dur = 0.8 } = {}) {
  const parts = VM.split(node, 'words');
  return (t) => parts.forEach((p, i) => {
    const a = VM.env(t, t0 + i * stagger, out + 0.6, dur, 0.5);
    p.style.opacity = a;
    p.style.filter = `blur(${(1 - a) * 0.8}vmin)`;
    p.style.transform = `translateY(${(1 - a) * 1.2}vh)`;
  });
}

// deterministic camera shake that decays after `at`
function shake(t, at, amp = 1.5, decay = 6, seed = 3) {
  if (t < at) return [0, 0];
  const k = Math.exp(-(t - at) * decay) * amp;
  return [VM.noise((t - at) * 40, seed) * k, VM.noise((t - at) * 40, seed + 9) * k];
}
