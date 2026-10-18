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
    /** Register a per-frame render function f(t). */
    onFrame(fn) { frameFns.push(fn); },
    /** Called by the renderer for every frame. */
    __seek(t) {
      for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
      for (const fn of frameFns) fn(t);
      if (typeof window.seek === 'function') window.seek(t);
    },
  };
  window.VM = VM;

  // Opened directly in a browser (not by the renderer): loop in real time for previewing.
  if (!window.__VEDIT_RENDERER__) {
    window.addEventListener('load', () => {
      const t0 = performance.now();
      const loop = () => { VM.__seek(((performance.now() - t0) / 1000) % VM.duration); requestAnimationFrame(loop); };
      requestAnimationFrame(loop);
    });
  }
})();
