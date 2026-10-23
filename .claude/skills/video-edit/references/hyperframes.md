# Designed graphics with HyperFrames

Every designed element of an edit (titles, lower thirds, designed transitions, overlays and
full-screen motion-design scenes) is a **HyperFrames composition**: a project folder with an
`index.html`, rendered by the HyperFrames CLI (`bin/hyperframes`, pinned in `mograph/package.json`)
and composited by vedit with alpha. vedit keeps the footage side: cuts, grading, beat sync, audio.

For the HyperFrames contract itself (timelines, `class="clip"`, variables, sub-compositions,
fonts, media), read the `hyperframes` skill. Where it says `npx hyperframes`, run `bin/hyperframes`.
Before building a named effect by hand, search the registry (`hyperframes-registry` skill):
`bin/hyperframes catalog <words> --json`.

## Using a composition in an edit

```json
"graphics":   [{"hyperframes": "title-card", "at_clip": "c1", "offset": 0.5, "duration": 4,
                "variables": {"title": "NORTH\nBOUND", "accent": "#ffb347"}}],
"timeline":   [{"id": "s1", "hyperframes": "hf/opener", "variables": {...}},          // full-screen scene clip
               {"id": "c2", "source": "a", "in": 3, "out": 6,
                "transition": {"type": "hyperframes", "project": "ink-spread", "duration": 1.2,
                               "variables": {"color": "#1a0f05"}}}]
```

- `hyperframes` / `project`: a folder relative to the edit, a vedit page (an `.html` file, see below),
  or a built-in name (below). Specs written for the old renderer still work: `html`, `scene` and
  `template` read as `hyperframes`, `params` as `variables`, and transition type `mograph` as `hyperframes`.
- `variables`: values for the composition's variables. Paths to images, Lottie JSON or clips are
  resolved relative to the edit and copied into the build, so pass them as-is.
- `duration`: overrides the composition's `data-duration`. The built-ins time everything off it,
  so they stretch to fit; a transition's cover point moves proportionally.
- Graphics are transparent overlays (ProRes 4444 with alpha). `blend: "screen"` (or
  `data-vedit-blend="screen"` on the root) renders opaque on black and screen-blends: use it for
  light, glow and flares.
- Scene clips render opaque at the output size and keep their own colours (`"graded": true` to
  follow the story arc). A scene that reads `VM.beats` (or `beatIndex`/`pulse`, or mentions the
  `vedit_beats` variable) receives the music beats that fall inside it, in seconds from its start.

## Built-ins (`hf/builtin/`, list with `bin/vedit hf list`)

| kind | names |
|---|---|
| transition (cover the frame at `cover-at`) | `shape-wipe`, `circle-reveal`, `bars-stagger`, `ink-spread`, `film-burn` |
| title | `title-card`, `kinetic-type`, `chapter-marker`, `glitch-title` |
| lower third | `lower-third` |
| overlay | `light-leak` (screen), `shape-burst`, `speed-lines` |
| scene (full screen) | `scene-kinetic`, `scene-stats`, `scene-logo-reveal`, `scene-3d-mountains`, `scene-photo-stack` |

Each one's header comment lists its variables. Old underscore names (`shape_wipe`) still resolve.
The `light_leak` and `film_burn` transition presets use the built-ins of the same name.

## Making your own

```bash
bin/vedit hf new projects/<name>/hf/my-title --overlay --duration 3     # transparent, 1920x1080
bin/vedit hf new projects/<name>/hf/opener --duration 6 --width 1080 --height 1920   # opaque scene
```
This runs `hyperframes init` and adds `assets/vedit/vm-shim.js`. Then either:

- **Write it with GSAP**, the HyperFrames way: build one paused timeline and register it as
  `window.__timelines["<composition id>"] = tl`.
- **Or start from a registry block**: `bin/hyperframes add <block> --dir <project> --json` writes
  `compositions/<block>.html` and prints a mount snippet. Replace the scaffold's placeholder `<h1>`
  with that snippet and set the root's `data-duration` to match.
- **Or use the vedit helpers** (what the built-ins use), which suit pure functions of time:
  ```html
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
  <script src="assets/vedit/vm-shim.js"></script>
  <script>
    const P = VM.params({ title: 'TITLE', accent: '#ff3b30' });   // HyperFrames variables over defaults
    VM.onFrame((t) => { el.style.opacity = VM.prog(t, 0.2, 0.6, 'outExpo'); });   // t in seconds
    VM.tl.from('.word', { yPercent: 110, stagger: 0.04, ease: 'expo.out' }, 0.3);  // or tween VM.tl
    window.__timelines = window.__timelines || {};
    window.__timelines[VM.id] = VM.start();                        // last lines of the page script
  </script>
  ```
  Helpers: `params`, `duration`, `prog`, `tween`, `env`, `keys`, `spring`, `stagger`, `split`,
  `draw` (SVG line drawing), `count`, `mix`, `rand`, `noise`, `ease.*`, music `beats`, `beatIndex`,
  `pulse`, and `ready(promise)` (or `window.VM_READY`) for async setup like three.js.

vedit hints go on the root element: `data-vedit-kind` (scene, title, overlay, transition),
`data-vedit-cover-at` (transitions: the second the frame is fully covered; the cut happens under
it), and `data-vedit-blend="screen"`.

Rules that matter for footage overlays:
1. Transparent background (`--ground: transparent`, the `--overlay` scaffold), or black with screen blend.
2. Size in `vw`/`vh`/`vmin`: the build resizes the composition to the output size (16:9, 9:16, 1:1).
3. Transitions: fully opaque full-frame coverage at `cover-at`, roughly symmetric in and out, 0.6–1.4 s.
4. Every frame is a pure function of time: no `Date.now()`, timers, rAF loops or unseeded `Math.random()`.
5. Libraries load from their jsDelivr/unpkg URLs (`gsap`, `lottie-web`, `three`); the build swaps in
   the local copies from `mograph/node_modules`, so renders work offline. Load three.js with
   `await import('https://cdn.jsdelivr.net/npm/three@0.186.1/build/three.module.js')`.
6. Fonts installed by `scripts/setup.sh` (Bebas Neue, Anton, Oswald, Montserrat, Playfair Display, ...)
   resolve by name; others need `@font-face` (see the hyperframes skill).

## vedit pages (single HTML files)

A spec can also point at one `.html` page written against the vedit runtime, the contract of the
former renderer that the volleyball example and the anime-short kit use. It runs unchanged inside
HyperFrames: the build mirrors the folder tree the page's `../` references reach (symlinks), adds
an `index.html` with `<base href>` set to the page's folder, and loads `hf/lib/vedit-runtime.js`, which
drives the page from HyperFrames' `hf-seek`.

```html
<meta name="vedit:kind" content="scene">          <!-- scene | title | overlay | transition | lower_third -->
<meta name="vedit:duration" content="5">          <!-- the spec's duration overrides it -->
<meta name="vedit:cover-at" content="0.5">        <!-- transitions -->
<meta name="vedit:blend" content="screen">        <!-- optional -->
<meta name="vedit:libs" content="gsap,lottie,three"><!-- gsap/lottie as globals; three via VEDIT.libs.three (+ three_addons) -->
<meta name="vedit:deps" content="lib.js,data.json"> <!-- local files it loads: part of the build key -->
<script>
  const P = VM.params({ title: 'Hello' });        // spec variables over these defaults
  VM.onFrame((t) => { /* draw frame t */ });       // or GSAP tweens: the global timeline is seeked
  window.VM_READY = (async () => { /* load models, decode images */ })();   // optional async setup
</script>
```

- Use pages for three.js-heavy or stateful work written in this style; new designed graphics are better as
  HyperFrames projects (registry blocks, Studio preview, lint).
- Asset paths in variables: image/audio/JSON paths are resolved against the edit, as before; other
  values (`.vrm`, `.glb`, `.bvh`) are passed through and the page resolves them against itself.
- Renders are cached by the page, its variables and its `vedit:deps` files. A page that loads other local
  scripts or data lists them there, or edits to them reuse stale renders.
- HyperFrames' snapshots don't relay the page console: `bin/vedit hf console <page> [--times ...]` prints what
  the page logs with `console.error` (and uncaught errors) while it loads and at those times.

## Review loop

```bash
bin/vedit hf snapshot <project|page.html|built-in> --variables '{...}' --times 0.3,0.8,1.5 --width 960 --height 540
bin/hyperframes lint          # inside the project: contract problems with a Fix: line
```
Read the PNGs and judge them like an art director: hierarchy, timing, spacing, legibility over the
actual footage, and colour harmony with the grade. Then render the edit with `--preview` and pull
frames at the graphic's moments with `bin/vedit frames`.

## Design guidance

- **Motion language**: fast-out-slow-in (`expo.out`, `outCubic`) for entrances and `expo.in` for exits.
  Stagger related elements by 40–80 ms. Use overshoot only for playful tones.
- **Timing**: entrances take 0.4–0.9 s. Hold text long enough to read twice. Exits are faster than entrances.
- **Masks beat fades**: reveal text from behind a clip (`overflow: hidden` plus a translate).
  Wipe shapes with `clip-path`, and grow rules with `scaleX` from an origin.
- **Layering**: 2–3 layers moving at different speeds or delays read as depth and polish.
- **Colour**: pull the accent from the grade (golden_hour gives amber; teal_orange gives orange on teal).
  Keep to 2–3 colours.
- **Texture**: SVG `feTurbulence` plus `feDisplacementMap` for organic edges, canvas for particles,
  and radial gradients on black with screen blend for glow.
