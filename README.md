# video-editing

Prompt-driven video editing for Claude Code. Describe the video you want ("a 30 s teaser
that starts calm, turns tense, ends hopeful, punchy transitions, bold titles") and the
**video-edit skill** (`.claude/skills/video-edit/`) cuts the footage to a story. It also:

- **Color grades dynamically along the story arc.** You set tone keyframes (`setup → tension →
  climax → resolution`), and every clip is graded by interpolating the arc. The look also
  ramps *inside* clips, so the color moves with the narrative. There are 18 tone presets
  (teal_orange, cold_thriller, golden_hour, vintage_film, noir, bleach_bypass,
  cyberpunk_neon, …), and each one is just a set of grade parameters (exposure, contrast curve,
  white balance, color wheels, split toning, film shoulder, bleach bypass, grain, bloom, …)
  turned into a 3D LUT.
- **Adds animated text.** Titles, lower thirds, kinetic words, quotes, chapters and captions
  from transcripts, using 10 display fonts.
- **Adds music and sound design.** Music is ducked under dialogue and loudness-normalized,
  and cuts can snap to the beats of the track. Procedural whooshes, impacts, risers and
  glitches land on transitions.
- **Adds motion graphics and transitions.** It has 50+ ffmpeg transitions, plus effect
  transitions (glitch, zoom punch, light leak, film burn) and designed titles, lower thirds,
  overlays and transitions built as **[HyperFrames](https://github.com/heygen-com/hyperframes)
  compositions** (HTML/CSS/GSAP rendered frame-accurately, with alpha). That covers the 18
  built-ins in `hf/builtin/`, ~450 HyperFrames registry blocks, and any custom graphic Claude
  designs for your edit.

## Motion design

The **motion-design skill** (`.claude/skills/motion-design/`) makes videos that are entirely
designed: promos, explainers, kinetic typography, logo reveals, data animations, 3D scenes and
photo montages. Each scene is a HyperFrames composition (CSS/SVG/canvas/WebGL, with **GSAP**,
**Lottie** and **three.js** served from local copies, so renders work offline). It can play on
its own, or be cut, beat-synced, transitioned and mixed with graded footage like any vedit clip:

```json
{"id": "s1", "hyperframes": "scene-kinetic", "duration": 6, "variables": {"lines": ["CORTES", "APERTAS"]}}
```

Built-in scenes: `scene-kinetic`, `scene-stats`, `scene-logo-reveal`, `scene-3d-mountains`,
`scene-photo-stack`. The HyperFrames skills (`hyperframes`, `hyperframes-cli`,
`hyperframes-registry`, `media-use`) are vendored in `.claude/skills/` to match the pinned CLI
(`bin/hyperframes`).

## Setup

```bash
scripts/setup.sh                # ffmpeg (if missing), Python deps, HyperFrames + its browser, fonts, sfx
scripts/setup.sh --with-whisper # + speech-to-text (needs huggingface.co access the first time)
bin/vedit doctor
```

Requirements: ffmpeg ≥ 5.1 (with libass, libx264), Python ≥ 3.10, Node ≥ 22 (for HyperFrames
graphics and scenes). In Claude Code cloud sessions the `SessionStart` hook runs the setup automatically.

## Using it with Claude

Put footage in a project folder and ask:

> Use the video-edit skill. Footage is in projects/trip/media, music in projects/trip/music.
> Make a 45 s travel reel: dreamy morning → energetic city → warm sunset ending. Cut to the
> beat, add a title at the start and an end card.

Claude analyzes the footage (contact sheets, scene cuts, transcripts, beats) and writes
`projects/trip/edit.json`. It checks a graded storyboard and renders a preview, looks at the
frames, iterates, and then renders the final.

## Using it by hand

```bash
bin/vedit new trip                                   # projects/trip/{media,music,graphics,work,out}
bin/vedit analyze projects/trip/media/*              # shots, silences, contact sheets
bin/vedit beats projects/trip/music/song.mp3         # tempo, beats, downbeats
bin/vedit tones --mood nostalgic                     # which looks fit a feeling
bin/vedit look projects/trip/media/a.mp4 --at 12 --tones original,golden_hour,vintage_film
bin/vedit plan projects/trip/edit.json               # resolved timeline + story arc
bin/vedit storyboard projects/trip/edit.json         # one graded still per clip
bin/vedit render projects/trip/edit.json --preview   # half-res draft
bin/vedit render projects/trip/edit.json             # final
bin/vedit hf list                                    # built-in HyperFrames compositions
bin/vedit hf snapshot title-card --variables '{"title":"HELLO"}' --times 0.5,1.5
bin/vedit hf new projects/trip/hf/end-card --overlay # scaffold your own (then bin/hyperframes add <block>)
bin/vedit lut teal_orange --out teal_orange.cube     # use the looks in Resolve/Premiere
```

A complete example spec, using generated demo media, is in `examples/demo/edit.json`:

```bash
bin/vedit demo-media --out projects/demo && bin/vedit render examples/demo/edit.json --preview
```

## How it works

| piece | file |
|---|---|
| edit spec → frame-accurate plan (transitions, arc grading, beat snapping) | `vedit/timeline.py` |
| grade model, LUT generation, finishing filters | `vedit/grade.py`, `vedit/tones.py` |
| per-clip segments (cut, speed, reframe, motion, graded ramp) + composite pass | `vedit/render.py` |
| animated typography / captions (ASS via libass) | `vedit/text.py` |
| HyperFrames bridge: offline build copies, variables, sizing → ProRes 4444 alpha / MP4 | `vedit/hyperframes.py`, `hf/`, `bin/hyperframes` |
| footage analysis, beat tracking, transcription | `vedit/analyze.py`, `vedit/beats.py`, `vedit/transcribe.py` |
| procedural sfx and placeholder music | `vedit/synth.py` |

Segments are cached by content hash in `<project>/work/`, so re-renders after small spec
changes are fast.

Tests: `python3 -m unittest discover -s tests -v`
