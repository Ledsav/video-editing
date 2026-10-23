# Motion graphics: writing your own HTML graphics

Any HTML page can become an overlay, title or transition. It is rendered in headless
Chromium frame by frame (deterministic, any resolution) and composited with alpha.

## The contract

```html
<!doctype html>
<html><head><meta charset="utf-8">
<meta name="vedit:kind" content="title">          <!-- title | overlay | transition | lower_third -->
<meta name="vedit:duration" content="3.0">        <!-- default length (spec can override) -->
<meta name="vedit:cover-at" content="0.5">        <!-- transitions only: when the frame is 100% covered -->
<meta name="vedit:blend" content="normal">        <!-- normal (alpha) | screen (draw on black: light, glow, flares) -->
<meta name="vedit:description" content="...">
<meta name="vedit:params" content="title; accent: CSS color">
<meta name="vedit:deps" content="lib.js">          <!-- local scripts/data the page loads: part of the render cache key -->
<style>
  html, body { margin: 0; width: 100vw; height: 100vh; overflow: hidden; background: transparent; }
  /* use vw / vh units only so the design works at any resolution and aspect ratio */
</style></head>
<body>
  <div id="t">TITLE</div>
<script>
  const P = VM.params({ title: 'TITLE', accent: '#ff3b30' });   // defaults, overridden by spec params
  const el = document.getElementById('t');
  el.textContent = P.title;
  VM.onFrame((t) => {                                             // t = seconds, called for every frame
    const D = VM.duration;
    const p = VM.prog(t, 0.2, 0.8, 'outExpo');                    // 0..1 eased progress of a window
    el.style.transform = `translateY(${(1 - p) * 40}vh)`;
    el.style.opacity = 1 - VM.prog(t, D - 0.4, 0.4);
  });
</script></body></html>
```

Rules:
1. **Every visual must be a pure function of `t`.** Use `VM.onFrame`. Never use `Date.now()`,
   `setTimeout`, `requestAnimationFrame` loops or `Math.random()` (use `VM.rand(seed)` /
   `VM.noise(x, seed)`; reseed with `Math.floor(t * fps)` for per-frame jitter).
   CSS `@keyframes` animations also work (the renderer pauses them and seeks `currentTime`).
2. Transparent background (`blend: normal`), or black background for `blend: screen`.
3. Use `vw`/`vh`. Size text in `vh`. Test the design at 1920x1080 and, for social, 1080x1920.
4. No network: use installed font families by name (Bebas Neue, Anton, Oswald, Archivo Black,
   Montserrat, Space Grotesk, Playfair Display, DM Serif Display, Cormorant Garamond,
   Permanent Marker, Inter). Inline SVG instead of remote images; local images by relative path work.
5. Transition graphics: fully opaque full-frame coverage at `cover-at` (the cut happens under it),
   symmetric-ish in/out, typically 0.6–1.4 s. Cover time scales with the duration given in the spec.

## Runtime helpers (`VM`, injected automatically)

| helper | use |
|---|---|
| `VM.params(defaults)` | merge spec `params` over defaults |
| `VM.duration` | duration in seconds |
| `VM.prog(t, start, dur, ease)` | eased 0..1 progress of a time window |
| `VM.tween(t, start, dur, from, to, ease)` | interpolated value |
| `VM.env(t, start, end, inDur, outDur)` | 0→1→0 envelope |
| `VM.ease.*` | linear, in/out/inOut Quad/Cubic/Quart/Expo, inOutSine, outBack, inBack, outElastic |
| `VM.rand(seed)()`, `VM.noise(x, seed)` | deterministic randomness / smooth noise |
| `VM.split(el, 'chars'|'words')` | wrap characters/words in spans for staggering |
| `VM.lerp`, `VM.clamp` | math |

## Workflow

1. Write `projects/<name>/graphics/<thing>.html` (copy a template from `mograph/templates/` as a start).
2. `bin/vedit mograph preview projects/<name>/graphics/<thing>.html --params '{...}' --background work/frames/shot.jpg --count 6`
   → Read the strip. Judge it like an art director: hierarchy, timing, spacing, legibility over
   the actual footage, color harmony with the grade. Iterate until it is good.
3. Use it: `"graphics": [{"html": "graphics/<thing>.html", "at_clip": "c1", "duration": 3, "params": {...}}]`
   or as a transition: `{"type": "mograph", "html": "graphics/<thing>.html", "duration": 1.0}`.

## Design guidance

- **Motion language**: fast-out-slow-in (`outExpo`, `outCubic`) for entrances; `inExpo` for exits;
  stagger related elements by 40–80 ms; overshoot (`outBack`) only for playful tones.
- **Timing**: entrances 0.4–0.9 s, holds long enough to read, exits faster than entrances.
- **Masks beat fades**: reveal text from behind a clip (`overflow: hidden` + translate),
  wipe shapes with `clip-path`, `scaleX` rules from an origin.
- **Layering**: 2–3 layers moving at different speeds/delays read as depth and polish.
- **Color**: pull the accent from the grade (golden_hour → amber, teal_orange → orange on teal,
  cyberpunk → magenta/cyan). Keep to 2–3 colors.
- **Texture**: SVG `feTurbulence` + `feDisplacementMap` for organic edges (ink, paper, smoke);
  canvas for particles, lines and procedural shapes; CSS `filter: blur()` + `mix-blend-mode: screen` for glow.
- **Brand pieces**: logo reveal = mask + line draw (`stroke-dasharray`/`stroke-dashoffset` on SVG paths) + subtle scale settle.

## Ideas that work well

- Line-draw logo or map route: SVG path with `stroke-dashoffset` driven by `VM.prog`.
- Data callouts: number counting up (`Math.round(VM.tween(...))`) + bar growing, in brand color.
- Split-screen reveal: two panels sliding apart revealing the next shot (transition).
- Typographic transition: a huge word slides across and covers the frame at `cover-at`.
- Lens flare / glow sweep: radial gradients on black, `blend: screen`.
- Film frame / viewfinder overlay: REC dot, timecode (`t` formatted), corner brackets.
