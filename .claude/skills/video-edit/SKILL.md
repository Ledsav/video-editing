---
name: video-edit
description: Edit videos from a natural-language prompt. Cuts footage to a story, color grades dynamically along the story arc (the look evolves with the narrative), adds animated text, music with ducking and beat-synced cuts, sound design, and motion-graphics transitions/titles designed as HyperFrames compositions (HTML/CSS/GSAP). Use whenever the user wants to cut, edit, trim, assemble, grade, color, title, caption, add music to, or add transitions/motion graphics to video, or make a trailer, teaser, reel, recap, promo or short film from footage.
---

# Video editing from a prompt

You are the editor, colorist, motion designer and sound designer. The `vedit` toolkit
(`bin/vedit`, Python + ffmpeg, with HyperFrames for designed graphics) does the rendering; your job is the
creative decisions, written down as an **edit spec** (`edit.json`). Everything is
re-renderable and cached, so iterate freely.

First run `bin/vedit doctor`. If something is missing, run `scripts/setup.sh`
(`--with-whisper` for transcription).

## Workflow

### 1. Ingest
- Create a project: `bin/vedit new <name>` → `projects/<name>/{media,music,graphics,work,out}` + `edit.json`.
- Put footage in `media/`, music in `music/`. If the user has no music, generate a placeholder
  bed: `bin/vedit synth-music --mood <uplifting|tense|sad|epic|chill|hype|dreamy> --duration N --out music/bed.wav`
  and tell them to swap in a licensed track later.

### 2. Understand the footage (look before you cut)
- `bin/vedit analyze media/*` → shots (scene cuts), silences, loudest moments, and
  **contact sheets** with timecodes. **Open the contact sheet images with Read** and actually
  look at them: note what is in each shot, its quality, its energy, where the good moments are.
- Need a closer look? `bin/vedit frames media/x.mp4 --times 12.5,14,30 --out work/frames` then Read.
- Dialogue/interviews: `bin/vedit transcribe media/x.mp4` (word timestamps). Cut on sentence
  boundaries; use the transcript to find the lines that tell the story.
- Music: `bin/vedit beats music/track.mp3` → tempo, beats, downbeats, energy rises (drops).

### 3. Write the brief (in the spec's `brief`, and say it to the user in 3–5 lines)
Translate the prompt into: logline, target duration, audience/platform (aspect ratio!),
**story arc** (3–5 beats: e.g. setup → rising tension → climax → resolution), and for each
beat a feeling. Map feelings to tones with `bin/vedit tones --mood <word>` and
[references/creative-direction.md](references/creative-direction.md) (pacing, transitions,
type and music per genre/mood).

### 4. Build the edit spec
Full schema: [references/edit-spec.md](references/edit-spec.md). Essentials:
- `story.arc`: keyframes `{at: "35%", label, tone, intensity}`. Clips without their own `grade`
  are graded by interpolating the arc at their position on the output timeline, and grades
  ramp *within* clips, so the look evolves continuously with the story.
- `timeline`: ordered clips `{source, in, out, motion, transition, speed, volume}`.
  Pick shots that serve each beat. Shot length follows the arc's energy (long and calm at
  setup; shorter as tension rises; hold the payoff).
- `text`, `graphics`, `effects`, `music`, `sfx`, `captions`: anchor them to clips with
  `{"at_clip": "c4", "offset": 0.3}` so they survive re-timing.
- Music-driven edits: add `"sync": {"beats": "music/track.beats.json", "every": 2}` and cuts snap
  to beats; give a clip `"beats": 4` to make it last exactly 4 beats.

### 5. Check before rendering
1. `bin/vedit validate edit.json` then `bin/vedit plan edit.json` (timeline table + arc).
2. `bin/vedit storyboard edit.json` → **Read the image**: one graded still per clip with
   the arc label. Does the color progression read as the story? Adjust tones/intensity/overrides.
3. For a specific look decision: `bin/vedit look media/x.mp4 --at 12 --tones original,teal_orange,cold_thriller`.
4. For any graphic (built-in or your own): `bin/vedit hf snapshot <name|dir> --variables '{...}' --times 0.3,1,2`
   → Read the stills and judge the design like an art director.

### 6. Render and review
- `bin/vedit render edit.json --preview` (half-res, fast) → extract frames around every
  transition and title with `bin/vedit frames out/final_preview.mp4 --times ...` and Read them.
  Check: transitions cover cleanly, text is legible and inside safe areas, grade progression,
  nothing awkward at cut points. Fix and re-render (segments are cached).
- `bin/vedit render edit.json` for the final. Report the output path, duration, the arc and
  the main creative choices to the user, and offer specific alternatives.

## Motion graphics: HyperFrames

Titles, lower thirds, designed transitions, overlays and full-screen scenes are HyperFrames
compositions, referenced from the spec with `"hyperframes": "<dir or built-in>"` plus `variables`.
Built-ins (`bin/vedit hf list`): shape-wipe, circle-reveal, bars-stagger, ink-spread, film-burn,
light-leak, title-card, lower-third, kinetic-type, chapter-marker, glitch-title, shape-burst,
speed-lines, and the scene-* compositions. When none fits the brief, search the HyperFrames
registry (`hyperframes-registry` skill) or **design your own**: `bin/vedit hf new
projects/<name>/hf/<thing> --overlay`. You are good at this: CSS, SVG, canvas, GSAP, typography.
Follow [references/hyperframes.md](references/hyperframes.md) (vedit specifics) and the
`hyperframes` skill (the composition contract). Always look at stills and iterate before using
a graphic in the edit.

Transition compositions must fully cover the frame at their cover point (`data-vedit-cover-at`);
the renderer hard-cuts the footage underneath at exactly that instant.

## Principles
- Story first: every cut, color shift and transition should mean something in the arc.
  Do not use flashy transitions everywhere: a sequence of plain cuts makes the one
  `zoom_punch` on the drop hit hard.
- Match transition energy to the arc: dissolves/dips for calm or time passing, whips/glitch/
  punch for energy, designed wipes for chapter changes and brand moments.
- Keep grades believable at intensity 0.6–0.9 unless the brief is stylized; skin tones
  should not go green or grey unless that is the point (horror, war).
- Text: few words, big, on screen long enough to read twice (≈ 0.3 s per word + 1 s).
- Audio: dialogue is king; music ducks under it (`duck: true`). Loudness target -14 LUFS for web.
- Always look at your output (frames, storyboards, strips) before declaring it done.
