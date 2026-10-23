/*
 * vedit helpers for HyperFrames compositions (assets/vedit/vm-shim.js).
 *
 * Wires a composition into the HyperFrames seek protocol and offers animation helpers:
 *   const P = VM.params({ title: 'Hi' });   // HyperFrames variables (JSON strings become arrays/objects)
 *   VM.onFrame((t) => { ... });             // draw the frame for time t (pure function of t)
 *   VM.tl                                   // the composition's paused GSAP timeline (absolute seconds)
 *   VM.ready(promise)                       // async setup (three.js, image decode) before frame 0
 *   window.__timelines = window.__timelines || {};
 *   window.__timelines[VM.id] = VM.start(); // LAST lines of the page script: register the timeline
 * Requires GSAP loaded before this file and one root element with data-composition-id/data-duration.
 */
(() => {
  if (window.VM) return;
  const root = document.querySelector('[data-composition-id]');
  const id = root.getAttribute('data-composition-id');
  const D = parseFloat(root.getAttribute('data-duration') || '3');
  const clamp = (x, a = 0, b = 1) => Math.min(Math.max(x, a), b);
  const lerp = (a, b, t) => a + (b - a) * t;
  const c1 = 1.70158, c3 = c1 + 1;
  const ease = {
    linear: (x) => x, inQuad: (x) => x * x, outQuad: (x) => 1 - (1 - x) * (1 - x),
    inOutQuad: (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2),
    inCubic: (x) => x * x * x, outCubic: (x) => 1 - Math.pow(1 - x, 3),
    inOutCubic: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    inQuart: (x) => x ** 4, outQuart: (x) => 1 - Math.pow(1 - x, 4),
    inOutQuart: (x) => (x < 0.5 ? 8 * x ** 4 : 1 - Math.pow(-2 * x + 2, 4) / 2),
    inExpo: (x) => (x === 0 ? 0 : Math.pow(2, 10 * x - 10)), outExpo: (x) => (x === 1 ? 1 : 1 - Math.pow(2, -10 * x)),
    inOutExpo: (x) => x === 0 ? 0 : x === 1 ? 1 : x < 0.5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2,
    inOutSine: (x) => -(Math.cos(Math.PI * x) - 1) / 2,
    outBack: (x) => 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2), inBack: (x) => c3 * x ** 3 - c1 * x * x,
  };
  const raw = (window.__hyperframes && window.__hyperframes.getVariables) ? window.__hyperframes.getVariables() : {};
  const parse = (v) => {
    if (typeof v === 'string' && /^\s*[\[{]/.test(v)) { try { return JSON.parse(v); } catch (e) { return v; } }
    return v;
  };
  const vars = Object.fromEntries(Object.entries(raw || {}).map(([k, v]) => [k, parse(v)]));
  const frameFns = [];
  const draw = (t) => { for (const fn of frameFns) fn(Math.max(0, Math.min(D, t))); };
  const tl = window.gsap.timeline({ paused: true });
  const state = { time: 0 };
  tl.to(state, { time: D, duration: D, ease: 'none', onUpdate: () => draw(state.time) }, 0);

  const VM = {
    id, root, ease, clamp, lerp, tl,
    duration: D,
    params(defaults = {}) { return Object.assign({}, defaults, vars); },
    /** Music beats (seconds from this composition's start) passed in by vedit as `vedit_beats`. */
    get beats() { return Array.isArray(vars.vedit_beats) ? vars.vedit_beats : []; },
    beatIndex(t) { const b = VM.beats; let i = -1; while (i + 1 < b.length && b[i + 1] <= t) i++; return i; },
    /** 1 on each beat, decaying to 0 (`decay` per second): for pulses and flashes. */
    pulse(t, decay = 8) { const i = VM.beatIndex(t); return i < 0 ? 0 : Math.exp(-(t - VM.beats[i]) * decay); },
    mix(c1, c2, p) {
      const h = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
      const a = h(c1), b = h(c2);
      return `rgb(${a.map((x, i) => Math.round(lerp(x, b[i], clamp(p)))).join(',')})`;
    },
    prog(t, start, dur, e = 'linear') { return (ease[e] || ease.linear)(clamp((t - start) / Math.max(dur, 1e-6))); },
    tween(t, start, dur, from, to, e = 'outCubic') { return lerp(from, to, VM.prog(t, start, dur, e)); },
    env(t, start, end, inDur, outDur, eIn = 'outCubic', eOut = 'inCubic') {
      return Math.min(VM.prog(t, start, inDur, eIn), 1 - VM.prog(t, end - outDur, outDur, eOut));
    },
    keys(t, ks) {
      if (t <= ks[0][0]) return ks[0][1];
      for (let i = 1; i < ks.length; i++) {
        const [t1, v1, e] = ks[i], [t0, v0] = ks[i - 1];
        if (t <= t1) {
          const p = (ease[e] || ease.inOutCubic)(clamp((t - t0) / Math.max(t1 - t0, 1e-6)));
          return Array.isArray(v0) ? v0.map((x, j) => lerp(x, v1[j], p)) : lerp(v0, v1, p);
        }
      }
      return ks[ks.length - 1][1];
    },
    spring(t, start = 0, { stiffness = 180, damping = 12, mass = 1 } = {}) {
      const x = t - start;
      if (x <= 0) return 0;
      const w0 = Math.sqrt(stiffness / mass), z = damping / (2 * Math.sqrt(stiffness * mass));
      if (z < 1) { const wd = w0 * Math.sqrt(1 - z * z); return 1 - Math.exp(-z * w0 * x) * (Math.cos(wd * x) + (z * w0 / wd) * Math.sin(wd * x)); }
      return 1 - Math.exp(-w0 * x) * (1 + w0 * x);
    },
    stagger(i, n, each = 0.06, from = 'start') {
      const k = from === 'end' ? n - 1 - i : from === 'center' ? Math.abs(i - (n - 1) / 2) : i;
      return k * each;
    },
    draw(el, p) {
      const len = el.__len || (el.__len = el.getTotalLength ? el.getTotalLength() : 1000);
      el.style.strokeDasharray = `${len} ${len}`;
      el.style.strokeDashoffset = String(len * (1 - clamp(p)));
    },
    count(t, start, dur, from, to, { decimals = 0, sep = '.', ease: e = 'outExpo', prefix = '', suffix = '' } = {}) {
      const v = lerp(from, to, VM.prog(t, start, dur, e));
      const [i, d] = v.toFixed(decimals).split('.');
      return prefix + i.replace(/\B(?=(\d{3})+(?!\d))/g, sep) + (d ? (sep === '.' ? ',' : '.') + d : '') + suffix;
    },
    rand(seed = 1) { let s = seed >>> 0 || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); },
    noise(x, seed = 0) {
      const h = (n) => { const s = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453; return s - Math.floor(s); };
      const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
      return lerp(h(i), h(i + 1), u) * 2 - 1;
    },
    split(el, mode = 'chars') {
      const text = el.textContent; el.textContent = '';
      const parts = mode === 'words' ? text.split(/(\s+)/) : Array.from(text);
      const spans = [];
      for (const p of parts) {
        if (/^\s+$/.test(p)) { el.appendChild(document.createTextNode(p)); continue; }
        const s = document.createElement('span'); s.textContent = p;
        s.style.display = 'inline-block'; s.style.whiteSpace = 'pre';
        el.appendChild(s); spans.push(s);
      }
      return spans;
    },
    onFrame(fn) { frameFns.push(fn); },
    ready(promise) { window.__hf = window.__hf || {}; window.__hf.buildReady = window.__hf.buildReady || {}; window.__hf.buildReady[id] = promise; },
    start() {
      if (window.VM_READY && window.VM_READY.then) VM.ready(window.VM_READY);
      window.addEventListener('hf-seek', (e) => { if (typeof e.detail?.time === 'number') draw(e.detail.time); });
      window.__timelines = window.__timelines || {};
      window.__timelines[id] = tl;
      draw(0);
      return tl;
    },
  };
  window.VM = VM;
})();
