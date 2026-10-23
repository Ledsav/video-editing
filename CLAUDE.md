# video-editing

Prompt-driven video editing toolkit (`vedit`) plus the `video-edit` skill in
`.claude/skills/video-edit/`. For any video editing request, follow that skill; for
designed/animated videos (motion graphics, promos, kinetic type, explainers) follow
`.claude/skills/motion-design/`.

- CLI: `bin/vedit <command>` (no install needed). `bin/vedit doctor` checks the toolchain; `scripts/setup.sh` installs it.
- User projects live in `projects/<name>/` (gitignored: media, work caches, renders). Never commit footage or renders.
- The edit spec format is documented in `.claude/skills/video-edit/references/edit-spec.md`; keep it in sync with `vedit/timeline.py`, `vedit/text.py` and `vedit/render.py` when changing behavior.
- Designed graphics, transitions and scenes are HyperFrames compositions (`bin/hyperframes`, pinned in `mograph/package.json`; skills `hyperframes*` and `media-use` vendored in `.claude/skills/`). `vedit/hyperframes.py` renders them from build copies (CDN libraries vendored from `mograph/node_modules`, variables declared, resized to the output).
- New built-ins go in `hf/builtin/<name>/` with vedit hints on the root (`data-vedit-kind`, `data-vedit-cover-at`, `data-vedit-blend`), vw/vh units, a header comment listing variables, and a copy of `hf/lib/vm-shim.js`; keep `tests/test_vedit.py::HyperFramesTests` passing.
- New tone presets go in `vedit/tones.py`; keep `tests/test_vedit.py::test_every_tone_is_monotonic_on_gray_ramp` passing.
- Tests: `python3 -m unittest discover -s tests -v` (renders small synthetic clips end to end).
- Always look at rendered output (`bin/vedit frames`, `storyboard`, `hf snapshot` produce images) before calling an edit done.
