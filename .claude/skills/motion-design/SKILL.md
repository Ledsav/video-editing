---
name: motion-design
description: Create motion-design videos from a prompt - explainers, promos, kinetic typography, logo reveals, title sequences, data/infographic animations, 3D scenes, photo montages, social ads - entirely designed in HTML/CSS/SVG/canvas/WebGL with GSAP, Lottie and three.js, rendered frame-accurately to video and edited with music, beat sync and transitions. Also for designed scenes mixed with real footage. Use whenever the user asks for motion graphics, an animated video, an animation, an intro/outro, a lyric or kinetic text video, an animated infographic, or a "motion design" piece.
---

# Motion design

You are the art director, designer and animator. A motion-design video here is an
**edit spec whose clips are HTML scenes** (`"scene": "<template>"` or `"html": "scenes/x.html"`),
optionally mixed with footage. Everything else (music, beat sync, transitions, text,
grading, export) works exactly as in the `video-edit` skill (read its `references/edit-spec.md`).

Rendering is deterministic: every frame is produced by seeking the page to time `t`
(`mograph/lib/runtime.js`), so animations must be pure functions of time.

## Workflow

1. **Brief → concept** (state it to the user in a few lines): message, audience, platform
   (16:9 / 9:16 / 1:1), length, tone, 2–3 reference adjectives ("Swiss, bold, kinetic").
2. **Style frame first.** Decide palette (3–4 colours + one accent), type pairing (one display +
   one text face), grid/margins, shape language. Write it at the top of the spec's `brief`.
3. **Storyboard as scenes**: 3–8 scenes, each one idea, 2–6 s. Write the scene list with
   timing against the music (beats/downbeats from `bin/vedit beats`).
4. **Build scenes**: start from a template (`bin/vedit templates`, kinds `scene`) and customise via
   `params`, or write a new page in `projects/<name>/scenes/` (copy a template). Keep each
   scene self-contained; pass content through `params`.
5. **Review stills** after every change: `bin/vedit mograph preview <scene> --params '{...}' --times 0.3,1,2,3.5`
   and Read the image. Check hierarchy, spacing, legibility, timing, safe margins, colour.
6. **Assemble** in `edit.json`, `bin/vedit plan`, `bin/vedit storyboard`, `bin/vedit render --preview`,
   inspect frames around every cut, fix, then final render.

## Scene contract (custom pages)

```html
<meta name="vedit:kind" content="scene">          <!-- full-screen, opaque: rendered fast (JPEG frames, H.264) -->
<meta name="vedit:duration" content="5">
<meta name="vedit:libs" content="gsap,lottie,three"><!-- only what you use; all offline -->
<meta name="vedit:deps" content="lib.js,data.json"> <!-- local files the page loads: part of the render cache key -->
<script>
  const P = VM.params({ title: 'Hello' });          // spec params override these defaults
  // Option A: GSAP. Build timelines at load; the renderer seeks the (paused) global timeline.
  const tl = gsap.timeline();
  tl.from('.title .ch', { yPercent: 110, stagger: 0.03, duration: 0.6, ease: 'expo.out' }, 0.2);
  // Option B: pure functions of time
  VM.onFrame((t) => { el.style.transform = `scale(${VM.spring(t, 0.4)})`; });
  // Async setup (three.js, images, Lottie JSON): assign a promise to VM_READY
  window.VM_READY = (async () => { const THREE = await import(VEDIT.libs.three); /* ... */ })();
</script>
```
- Units: `vw`/`vh`/`vmin` only, so one scene renders at 1920×1080, 1080×1920 and 1080×1080.
  Branch layout on `innerHeight > innerWidth` for portrait.
- Never use timers, `Date.now()`, rAF loops or `Math.random()`; use `VM.rand(seed)`, `VM.noise`.
- Lottie: `lottie.loadAnimation({container, path: P.animation, autoplay: false, renderer: 'svg'})`;
  every registered animation is seeked automatically. Paths in params resolve relative to the edit.
- three.js: `new THREE.WebGLRenderer({ preserveDrawingBuffer: true, alpha: true })` and render inside
  `VM.onFrame`. WebGL is software-rendered: keep geometry moderate (< ~300k triangles).
- Overlays (not full-screen) omit `vedit:kind scene`; they render with alpha (see video-edit skill).
- Renders are cached by the page's text and params. A page that loads its own scripts or data lists them in
  `vedit:deps` (relative to the page) so editing them re-renders it; without it, edits to those files reuse stale renders.

Runtime helpers (`VM`): `params`, `duration`, `prog`, `tween`, `env`, `keys` (keyframes),
`spring`, `stagger`, `split` (chars/words), `draw` (SVG line drawing), `count` (number counters),
`mix` (colours), `rand`, `noise`, `ease.*`, and music sync: `beats` (seconds, relative to the scene),
`beatIndex(t)`, `pulse(t)`. Details and recipes: [references/recipes.md](references/recipes.md).

## Scene templates

| template | what |
|---|---|
| `scene_kinetic` | kinetic typography, lines land on beats, colour-block wipes, final lockup (GSAP) |
| `scene_stats` | counters in drawn rings with labels (data / recap) |
| `scene_logo_reveal` | wordmark outline draws, fills, ring trace, light sweep, tagline |
| `scene_3d_mountains` | three.js low-poly landscape flythrough at golden hour with title |
| `scene_photo_stack` | photos fly into a 3D stack with handwritten captions |

Overlay templates from the video-edit skill (titles, lower thirds, transitions) work on scenes too.

## Design principles (apply every time)

- **One idea per scene**, one focal point per frame. Hierarchy by size and contrast, not by adding things.
- **Timing**: entrances 0.4–0.8 s, exits faster (0.25–0.4 s), hold readable text ≥ 1 s + 0.3 s/word.
  Stagger 25–80 ms. Animate in on the beat; let big moves land on downbeats.
- **Easing**: `expo.out`/`outExpo` for entrances, `expo.in` for exits, `inOutCubic` for moves
  between states, springs for playful/physical. Never linear except constant drifts.
- **Continuity**: carry an element, colour or direction across a cut (match cuts) so scenes flow;
  vary scale and rhythm between consecutive scenes.
- **Type**: max two families; tight leading (0.85–0.95) for display; generous tracking for small caps;
  keep text inside 7% horizontal / 9% vertical safe margins (portrait: avoid the bottom 18%).
- **Colour**: a dominant neutral, a secondary, one accent used sparingly for emphasis.
- **Texture/polish**: subtle grain, motion blur by staggering/filters, parallax layers at different speeds.
- **Restraint**: no gratuitous glitches, lens flares or effects that don't serve the message.

## Mixing with footage

Scenes and footage clips sit in the same `timeline`. Footage keeps the story grade; scenes keep
their exact colours (add `"graded": true` to a scene to follow the arc). Use the footage's own
stills in scenes: `bin/vedit frames media/x.mp4 --times 3.2 --out scenes/img` then pass the paths
in `params.images`.
