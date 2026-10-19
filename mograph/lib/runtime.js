/*
 * vedit motion-graphics runtime. Injected into every page the renderer loads
 * (templates and custom HTML alike), so pages can use `VM` without importing it.
 *
 * Contract for a page:
 *   - Draw on a transparent background (body { background: transparent }), or on
 *     black when the graphic is meant to be screen-blended (light leaks, flares).
 *   - Make every visual a pure function of time: register `VM.onFrame(t => ...)`
 *     (t in seconds). CSS animations / WAAPI also work: the renderer pauses them and
 *     sets currentTime for each frame. Never rely on wall-clock time or rAF.
 *   - Read options with `const P = VM.params({...defaults})`.
 *   - Use vw/vh units so the design works at any output resolution.
 */
(() => {
  if (window.VM) return;
  const clamp = (x, a = 0, b = 1) => Math.min(Math.max(x, a), b);
  const lerp = (a, b, t) => a + (b - a) * t;
  const c1 = 1.70158, c3 = c1 + 1;
  const ease = {
    linear: (x) => x,
    inQuad: (x) => x * x,
    outQuad: (x) => 1 - (1 - x) * (1 - x),
    inOutQuad: (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2),
    inCubic: (x) => x * x * x,
    outCubic: (x) => 1 - Math.pow(1 - x, 3),
    inOutCubic: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    inQuart: (x) => x * x * x * x,
    outQuart: (x) => 1 - Math.pow(1 - x, 4),
    inOutQuart: (x) => (x < 0.5 ? 8 * x ** 4 : 1 - Math.pow(-2 * x + 2, 4) / 2),
    inExpo: (x) => (x === 0 ? 0 : Math.pow(2, 10 * x - 10)),
    outExpo: (x) => (x === 1 ? 1 : 1 - Math.pow(2, -10 * x)),
    inOutExpo: (x) => x === 0 ? 0 : x === 1 ? 1 : x < 0.5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2,
    inOutSine: (x) => -(Math.cos(Math.PI * x) - 1) / 2,
    outBack: (x) => 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2),
    inBack: (x) => c3 * x * x * x - c1 * x * x,
    outElastic: (x) => x === 0 ? 0 : x === 1 ? 1 : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1,
  };
  const frameFns = [];
  const meta = (name, dflt) => {
    const el = document.querySelector(`meta[name="vedit:${name}"]`);
    return el ? el.getAttribute('content') : dflt;
  };

  const VM = {
    ease, clamp, lerp,
    /** Merge defaults with the params passed by the edit spec. */
    params(defaults = {}) { return Object.assign({}, defaults, window.PARAMS || {}); },
    /** Seconds the graphic lasts (from the spec, else the template meta). */
    get duration() { return (window.VEDIT && window.VEDIT.duration) || parseFloat(meta('duration', '2')); },
    /** Eased 0..1 progress of a window [start, start + dur]. */
    prog(t, start, dur, e = 'linear') { return (ease[e] || ease.linear)(clamp((t - start) / Math.max(dur, 1e-6))); },
    /** Value tweened from `from` to `to` over [start, start + dur]. */
    tween(t, start, dur, from, to, e = 'outCubic') { return lerp(from, to, VM.prog(t, start, dur, e)); },
    /** Envelope: rises over `inDur`, holds, falls over `outDur` before `end`. */
    env(t, start, end, inDur, outDur, eIn = 'outCubic', eOut = 'inCubic') {
      return Math.min(VM.prog(t, start, inDur, eIn), 1 - VM.prog(t, end - outDur, outDur, eOut));
    },
    /** Deterministic PRNG: VM.rand(seed)() -> [0, 1). */
    rand(seed = 1) {
      let s = seed >>> 0 || 1;
      return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
    },
    /** Smooth deterministic noise in [-1, 1]. */
    noise(x, seed = 0) {
      const h = (n) => { const s = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453; return s - Math.floor(s); };
      const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
      return (lerp(h(i), h(i + 1), u)) * 2 - 1;
    },
    /** Wrap each character (or word) of el in a span; returns the spans. */
    split(el, mode = 'chars') {
      const text = el.textContent;
      el.textContent = '';
      const parts = mode === 'words' ? text.split(/(\s+)/) : Array.from(text);
      const spans = [];
      for (const p of parts) {
        if (/^\s+$/.test(p)) { el.appendChild(document.createTextNode(p)); continue; }
        const s = document.createElement('span');
        s.textContent = p;
        s.style.display = 'inline-block';
        s.style.whiteSpace = 'pre';
        el.appendChild(s);
        spans.push(s);
      }
      return spans;
    },
    /** Piecewise keyframes: VM.keys(t, [[0, 0], [0.5, 1, 'outBack'], [2, 1], [2.4, 0, 'inCubic']]).
     *  Each key is [time, value, easeIntoThisKey]; values may be numbers or arrays of numbers. */
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
    /** Damped spring response (0 -> 1 with overshoot) started at `start`. */
    spring(t, start = 0, { stiffness = 180, damping = 12, mass = 1 } = {}) {
      const x = t - start;
      if (x <= 0) return 0;
      const w0 = Math.sqrt(stiffness / mass), zeta = damping / (2 * Math.sqrt(stiffness * mass));
      if (zeta < 1) {
        const wd = w0 * Math.sqrt(1 - zeta * zeta);
        return 1 - Math.exp(-zeta * w0 * x) * (Math.cos(wd * x) + (zeta * w0 / wd) * Math.sin(wd * x));
      }
      return 1 - Math.exp(-w0 * x) * (1 + w0 * x);
    },
    /** Delay for item i of a staggered group (seconds). `from`: 'start' | 'end' | 'center'. */
    stagger(i, n, each = 0.06, from = 'start') {
      const k = from === 'end' ? n - 1 - i : from === 'center' ? Math.abs(i - (n - 1) / 2) : i;
      return k * each;
    },
    /** Draw an SVG path/shape progressively (p in 0..1) using its stroke. */
    draw(el, p) {
      const len = el.__len || (el.__len = el.getTotalLength ? el.getTotalLength() : 1000);
      el.style.strokeDasharray = `${len} ${len}`;
      el.style.strokeDashoffset = String(len * (1 - clamp(p)));
    },
    /** Animated number: VM.count(t, 0.5, 1.5, 0, 12800, {decimals: 0, sep: '.'}) -> "12.800". */
    count(t, start, dur, from, to, { decimals = 0, sep = '.', ease: e = 'outExpo', prefix = '', suffix = '' } = {}) {
      const v = lerp(from, to, VM.prog(t, start, dur, e));
      const [i, d] = v.toFixed(decimals).split('.');
      return prefix + i.replace(/\B(?=(\d{3})+(?!\d))/g, sep) + (d ? (sep === '.' ? ',' : '.') + d : '') + suffix;
    },
    /** Interpolate two CSS hex colours. */
    mix(c1, c2, p) {
      const h = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
      const a = h(c1), b = h(c2);
      return `rgb(${a.map((x, i) => Math.round(lerp(x, b[i], clamp(p)))).join(',')})`;
    },
    /** Music beats (seconds, relative to this scene's start) passed in by the editor. */
    get beats() { return (window.VEDIT && window.VEDIT.beats) || []; },
    /** Index of the last beat at or before t (-1 before the first). */
    beatIndex(t) { const b = VM.beats; let i = -1; while (i + 1 < b.length && b[i + 1] <= t) i++; return i; },
    /** 1 on each beat, decaying to 0 (exponential, `decay` per second): for pulses and flashes. */
    pulse(t, decay = 8) {
      const i = VM.beatIndex(t);
      return i < 0 ? 0 : Math.exp(-(t - VM.beats[i]) * decay);
    },
    /** Register a per-frame render function f(t). */
    onFrame(fn) { frameFns.push(fn); },
    /** Called once by the renderer before the first frame. */
    __start() {
      if (window.gsap) { window.gsap.ticker.lagSmoothing(0); window.gsap.globalTimeline.pause(); }
    },
    /** Called by the renderer for every frame. */
    __seek(t) {
      for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
      if (window.gsap) window.gsap.globalTimeline.seek(t, false);
      if (window.lottie && window.lottie.getRegisteredAnimations) {
        for (const an of window.lottie.getRegisteredAnimations()) an.goToAndStop(t * 1000, false);
      }
      for (const fn of frameFns) fn(t);
      if (typeof window.seek === 'function') window.seek(t);
    },
  };
  window.VM = VM;
  // Freeze GSAP's clock before any page script creates tweens, so every tween is anchored at
  // t = 0 and the renderer can seek them exactly.
  if (window.__VEDIT_RENDERER__ && window.gsap) {
    window.gsap.ticker.lagSmoothing(0);
    window.gsap.globalTimeline.pause();
    window.gsap.globalTimeline.seek(0, false);
  }

  // Opened directly in a browser (not by the renderer): loop in real time for previewing.
  if (!window.__VEDIT_RENDERER__) {
    window.addEventListener('load', async () => {
      if (window.VM_READY) await window.VM_READY;
      VM.__start();
      const t0 = performance.now();
      const loop = () => { VM.__seek(((performance.now() - t0) / 1000) % VM.duration); requestAnimationFrame(loop); };
      requestAnimationFrame(loop);
    });
  }
})();
