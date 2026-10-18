---
name: video-edit
description: Edit videos from a natural-language prompt. Cuts footage to a story, color grades dynamically along the story arc (the look evolves with the narrative), adds animated text, music with ducking and beat-synced cuts, sound design, and motion-graphics transitions/titles designed in HTML/CSS/JS. Use whenever the user wants to cut, edit, trim, assemble, grade, color, title, caption, add music to, or add transitions/motion graphics to video, or make a trailer, teaser, reel, recap, promo or short film from footage.
---

# Video editing from a prompt

You are the editor, colorist, motion designer and sound designer. The `vedit` toolkit
(`bin/vedit`, Python + ffmpeg + headless Chromium) does the rendering; your job is the
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
4. For any graphic (template or custom): `bin/vedit mograph preview <name|file.html> --params '{...}' --background work/frames/x.jpg`
   → Read the strip and judge the design like an art director.

### 6. Render and review
- `bin/vedit render edit.json --preview` (half-res, fast) → extract frames around every
  transition and title with `bin/vedit frames out/final_preview.mp4 --times ...` and Read them.
  Check: transitions cover cleanly, text is legible and inside safe areas, grade progression,
  nothing awkward at cut points. Fix and re-render (segments are cached).
- `bin/vedit render edit.json` for the final. Report the output path, duration, the arc and
  the main creative choices to the user, and offer specific alternatives.

## Motion graphics: design your own

Templates (`bin/vedit templates`): shape_wipe, circle_reveal, bars_stagger, ink_spread,
film_burn, light_leak, title_card, lower_third, kinetic_type, chapter_marker, glitch_title,
shape_burst, speed_lines. When none fits the brief, **write a custom HTML graphic** in
`projects/<name>/graphics/` and reference it with `"html": "graphics/my_title.html"`. You are
good at this: CSS, SVG filters, canvas, typography. Follow the contract and design guidance in
[references/motion-graphics.md](references/motion-graphics.md). Always preview stills and
iterate before using it in the edit.

Transition graphics must fully cover the frame at their `cover-at` moment; the renderer
hard-cuts the footage underneath at exactly that instant.

## Principles
- Story first: every cut, color shift and transition should mean something in the arc.
  Do not use flashy transitions everywhere: a sequence of plain cuts makes the one
  `zoom_punch` on the drop hit hard.
- Match transition energy to the arc: dissolves/dips for calm or time passing, whips/glitch/
  punch for energy, mograph wipes for chapter changes and brand moments.
- Keep grades believable at intensity 0.6–0.9 unless the brief is stylized; skin tones
  should not go green or grey unless that is the point (horror, war).
- Text: few words, big, on screen long enough to read twice (≈ 0.3 s per word + 1 s).
- Audio: dialogue is king; music ducks under it (`duck: true`). Loudness target -14 LUFS for web.
- Always look at your output (frames, storyboards, strips) before declaring it done.
