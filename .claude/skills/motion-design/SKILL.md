---
name: motion-design
description: Create motion-design videos from a prompt - explainers, promos, kinetic typography, logo reveals, title sequences, data/infographic animations, 3D scenes, photo montages, social ads - designed as HyperFrames compositions (HTML/CSS/SVG/canvas/WebGL with GSAP, Lottie and three.js), rendered frame-accurately and, when they need music cut to the beat, footage or a graded story, assembled with vedit. Use whenever the user asks for motion graphics, an animated video, an animation, an intro/outro, a lyric or kinetic text video, an animated infographic, or a "motion design" piece.
---

# Motion design

You are the art director, designer and animator. Scenes are **HyperFrames compositions**. Read
the `hyperframes` skill first: it holds the composition contract, the work loop and what each
kind of video needs. Where it says `npx hyperframes`, run `bin/hyperframes` (the pinned CLI;
telemetry off). Search the registry before hand-building a named effect (`hyperframes-registry`),
and get media through `media-use`.

## Pick the assembly

- **Pure HyperFrames**: one project whose root mounts the scenes as sub-compositions, with music
  as an `<audio>` element. Render with `bin/hyperframes render`. Best for a designed piece with
  no footage and simple audio.
- **vedit edit with scene clips**: each scene is its own HyperFrames project used as a clip
  (`{"hyperframes": "hf/opener", "variables": {...}}`). vedit adds beat-synced cuts, music
  crossfades and loudness, transitions between scenes, real footage graded along a story arc,
  and text. Use it when any of those matter. Everything in the `video-edit` skill applies; read
  its `references/hyperframes.md` for the vedit side (variables, durations, built-ins, beats).

## Workflow

1. **Brief → concept**, stated to the user in a few lines: message, audience, platform
   (16:9 / 9:16 / 1:1), length, tone, and 2–3 reference adjectives ("Swiss, bold, kinetic").
2. **Style frame first.** Decide the palette (3–4 colours plus one accent), the type pairing
   (one display face, one text face), the grid and margins, and the shape language.
3. **Storyboard as scenes**: 3–8 scenes, one idea each, 2–6 s. Time them against the music
   (`bin/vedit beats music/x.mp3`).
4. **Build scenes**: start from a built-in (`bin/vedit hf list`: scene-kinetic, scene-stats,
   scene-logo-reveal, scene-3d-mountains, scene-photo-stack) and set its variables. Or start
   from a registry block, or scaffold a new one: `bin/vedit hf new projects/<name>/hf/<scene>
   --duration 5 --width 1080 --height 1920`. Pass content through variables.
5. **Review stills** after every change: run `bin/vedit hf snapshot <scene> --variables '{...}'
   --times 0.3,1,2,3.5` and Read the images. Run `bin/hyperframes lint` inside the project.
   Check hierarchy, spacing, legibility, timing, safe margins and colour.
6. **Assemble and render**: run `bin/vedit plan`, `storyboard` and `render --preview`. Inspect
   frames around every cut with `bin/vedit frames`, fix, then run the final render.

## Writing scenes

- GSAP is the native way: one paused timeline, registered as `window.__timelines["<id>"] = tl`.
- The vedit helpers in `assets/vedit/vm-shim.js` (`VM.params`, `VM.onFrame(t => ...)`,
  `VM.tl`, springs, counters, SVG line drawing, deterministic noise, `VM.beats`) are a good fit
  for pure functions of time. They are what the built-ins use. Recipes:
  [references/recipes.md](references/recipes.md).
- Units: `vw`/`vh`/`vmin`, so one scene renders at 1920×1080, 1080×1920 and 1080×1080 (the
  build resizes it to the edit's output). Branch the layout on `innerHeight > innerWidth`.
- Never use timers, `Date.now()`, rAF loops or unseeded `Math.random()`.
- three.js: `await import('https://cdn.jsdelivr.net/npm/three@0.186.1/build/three.module.js')`
  inside `VM.ready(...)`, with `preserveDrawingBuffer: true`, and draw in `VM.onFrame`. WebGL is
  software-rendered, so keep geometry moderate (under about 300k triangles). CDN libraries are
  vendored locally at build time, so renders work offline.
- Existing single-page scenes in the vedit style (`<meta name="vedit:*">`, `VM.onFrame`, `VEDIT.libs.three`,
  `window.VM_READY`) still render as they are: point the spec at the `.html` file. See "vedit pages" in
  the video-edit skill's `references/hyperframes.md`, including `vedit:deps` for files a page loads.
- Music sync: a scene that reads `VM.beats` (or `VM.pulse`/`beatIndex`) receives the edit's beats that
  fall inside it, as the `vedit_beats` variable.

## Design principles (apply every time)

- **One idea per scene**, one focal point per frame. Build hierarchy with size and contrast,
  not by adding things.
- **Timing**: entrances take 0.4–0.8 s and exits are faster (0.25–0.4 s). Hold readable text at
  least 1 s plus 0.3 s per word. Stagger by 25–80 ms. Animate in on the beat, and let big moves
  land on downbeats.
- **Easing**: `expo.out` for entrances, `expo.in` for exits, `inOutCubic` for moves between
  states, and springs for playful or physical motion. Never linear, except constant drifts.
- **Continuity**: carry an element, colour or direction across a cut (match cuts) so scenes
  flow. Vary scale and rhythm between consecutive scenes.
- **Type**: at most two families. Use tight leading (0.85–0.95) for display and generous
  tracking for small caps. Keep text inside 7% horizontal and 9% vertical safe margins; in
  portrait, avoid the bottom 18%.
- **Colour**: a dominant neutral, a secondary, and one accent used sparingly for emphasis.
- **Restraint**: no gratuitous glitches, lens flares or effects that don't serve the message.

## Mixing with footage

Scenes and footage clips sit in the same vedit `timeline`. Footage follows the story grade,
while scenes keep their exact colours (add `"graded": true` to a scene to follow the arc). To
use the footage's own stills in scenes, run `bin/vedit frames media/x.mp4 --times 3.2 --out
scenes/img` and pass the paths in `variables.images`. They are copied into the build for you.
