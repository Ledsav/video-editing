# video-editing

Prompt-driven video editing toolkit (`vedit`) plus the `video-edit` skill in
`.claude/skills/video-edit/`. For any video editing request, follow that skill; for
designed/animated videos (motion graphics, promos, kinetic type, explainers) follow
`.claude/skills/motion-design/`.

- CLI: `bin/vedit <command>` (no install needed). `bin/vedit doctor` checks the toolchain; `scripts/setup.sh` installs it.
- User projects live in `projects/<name>/` (gitignored: media, work caches, renders). Never commit footage or renders.
- The edit spec format is documented in `.claude/skills/video-edit/references/edit-spec.md`; keep it in sync with `vedit/timeline.py`, `vedit/text.py` and `vedit/render.py` when changing behavior.
- Full-screen scenes use `<meta name="vedit:kind" content="scene">` and render opaque (fast path); libraries are declared with `vedit:libs` (gsap, lottie, three).
- New motion-graphics templates go in `mograph/templates/` and must follow the runtime contract in `mograph/lib/runtime.js` (pure function of time, `vedit:*` meta tags, vw/vh units).
- New tone presets go in `vedit/tones.py`; keep `tests/test_vedit.py::test_every_tone_is_monotonic_on_gray_ramp` passing.
- Tests: `python3 -m unittest discover -s tests -v` (renders small synthetic clips end to end).
- Always look at rendered output (`bin/vedit frames`, `storyboard`, `mograph preview` produce images) before calling an edit done.
