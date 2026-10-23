# Pitfalls (each of these cost a round of feedback once)

**Working with the user**
- Don't render without being asked; show screenshots of every change. A full render can take 45+ minutes.
- One change at a time, then look. When the user says something looks wrong, find out why before editing.
- When the user wants to sell: list every non-commercial asset at once, with the replacement for each.

**Mocap and retarget**
- A take's standing pose is its calibration: a BVH that starts mid-action calibrates wrong (body leaning, hips
  "reversed"). Give `stand: [t0, t1]` on a standing stretch, or use a take with a T-pose first frame (CMU).
- Scout takes before writing shots: `shot_stills.py --mocap` (whole take, then the moment at 0.1 s steps, from the
  side with `--orbit 70`). The log's `strikes` list finds punches and kicks.
- A shot's `from`/`to` are take seconds; slow motion = a short take range over a long `dur`. Below ¼ speed, one
  captured frame spans many video frames: the kit interpolates and smooths, but prefer ⅓-½.
- Takes without fingers have flat T-pose hands: always set `fist` (0.35 relaxed, 1 a fist).
- A pose that looks impossible may be real: check the raw take from another angle before "fixing" the retarget.

**Cameras**
- `orbit` is relative to the character's facing at the shot start. Fighters stand bladed: use `ref: "head"` or `hips`.
- Following a hand or foot (`target: "RightHand"`) jitters with the motion; `follow: false` locks the frame, but only
  for a character that stays in place: a running kick leaves a locked frame. For moving action, target `Hips` (follow)
  and give the hand/foot to the `impact.target` instead.
- A light-haired character (silver, white, blonde) reads as a white shape in wide shots under the warm rims: that's
  right for the character (check a close-up); for more shading set `hair` to a cool grey multiply (`#8890b0`).
- Don't cut between two shots from nearly the same angle (a jump cut): change orbit by ≥ 30° or the size by 2x.

**Impact frames**
- The impact time must be the strike's own peak (`at: {"clip": t}` from the strikes list or `"contact"`): a frame
  early and the fist is still bent; late and it's already coming back.
- A hold lengthens the shot: `dur` includes it. Re-run shot_stills after changing it: the sound plans follow
  `work/anime_times/`.
- The ink pass needs the figure big and lit from the hit; tiny figures turn into noise.

**Pages and text**
- Brush fonts make digits ambiguous (Yuji Boku's 1 reads as 7): set numbers in the logo face.
- Elements that pop in with `outBack` from 0 are visible at t=0 (outBack(0) ≠ 0 in floating point): gate them by time.
- Vertical brush text longer than ~5 characters runs into the bands: shorten it (the size adapts down to 4-6 chars).

**Sound**
- A sub-heavy hit sounds like slow motion; stopping the music under the action feels like a mistake.
- Pipe-to-`head` kills Python scripts mid-write (broken pipe): don't pipe the tools' output into `head`.

**Toolkit**
- Scene renders are cached by the page, its variables and its `vedit:deps` files: the kit pages declare `anime.js` and
  `mocap.js`. Replacing an asset file under the same name (a new .vrm, a new .bvh) does **not** invalidate the cache:
  rename the file or change a param.
- `new_project.sh` copies the kit into the project; after improving the kit, re-run it to refresh the copies (it
  keeps edit.json and the plans).
