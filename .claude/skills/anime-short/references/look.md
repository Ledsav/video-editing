# The anime look, and how to judge a still

## The layers (all in the kit)
1. **Cel-shaded character**: toon materials with a 3-step ramp; painted face details unlit (lit, warm rims turn brows
   orange); skin multiplied (`skin`) so lit skin never reaches the top band (the "white face").
2. **Lighting**: a key spot with soft shadows, two warm rims, a blue back rim, a fill from the camera. Rims make the
   silhouette pop against a dark set: keep the set darker than the character.
3. **The anime post pass**: three flat tones with cool shadows, hand-drawn outlines that wobble on twos (12 fps),
   scratchy hatching in the shadows, a glow off the brightest light, near-black kept black. `cel` 0.6-0.85.
4. **Lens**: barrel distortion (`lens`), chromatic fringes, radial zoom blur towards the action (`zoom`, pulses after
   impacts), fov punch, shake.
5. **Motion**: subframe motion blur (3 samples, half shutter), never across a cut or into a hold; a 6-sample smear on
   the release of a hold; speed lines centred on the action.
6. **Impact frames** (`style: ink`): the scene re-rendered in white ink materials lit only by a light at the hit and
   a rim from behind, redrawn as a two-tone brush drawing: ragged light/shadow edge, hatching, outlines in the opposite
   tone, energy streaks, a **heavy fisheye centred on the hit** that punches in at contact and settles, and a **flash
   out of the hit** that fills the frame and collapses back (smaller at each new drawing). 3-4 drawings, 0.25 s each,
   palettes white-on-black → negative → black-on-red → mint, each from its own angle (`angles: true`), one white frame
   between drawings. Short ones (0.13-0.25 s, 2-3 drawings at 0.07-0.09 s) for a takeoff or a landing.
7. **Grades**: `memory: true` for the past (grey, cold); a red tint for rage.
8. **Finish**: grain 0.07, vignette 0.5.

## What to check in every sheet
- **Pose**: does the silhouette read in one glance? Arms/legs bend the right way? Hands not inside the body? Wrists
  not broken? If a pose looks wrong, **check the raw capture first** (scout the take with `--mocap` from another angle,
  or compare with another character): a 40° lean can be the actor's own slip, not a bug.
- **Faces**: in a close-up the eyes must be visible (`cam.target: "Head"`, `lookY` ≈ 0.07: VRoid head joints sit
  at the jaw). Is the expression right for the beat (`face`)?
- **Framing**: the subject off-centre in wides (thirds), centred in impacts; headroom; nothing important under where
  the TikTok UI will sit if the film is also cut vertical (bottom 20%, right 13%).
- **Impact frames**: centred on the hit? The figure big in frame (≥ 40% height)? The drawing readable (not all
  black or all white: adjust `inkThr` 0.8-1.1, `inkHit` 6-14)?
- **Colour**: the character's colours read against the set; the set darker than the character; no blown-out floor.
- **Continuity**: the screen direction of the action stays the same across cuts (cross the line only on purpose).

## Fixes that worked
| symptom | cause | fix |
|---|---|---|
| white face | lit skin posterised into the top band | darker `skin` multiply (body and face together) |
| body looks reversed / sway-back | capture's standing pose ≠ rig's rest pose | rest calibration (automatic: T-pose frame or opening frames; `stand: [t0, t1]` for a take that starts mid-action) |
| hands and arms rotated, palms flipped | takes without finger data, wrist twist | `fist` 0.35-1; the retarget limits wrist twist/bend |
| floor blown out orange | rims skimming a lit floor | the floor is unlit now; `set.pool` for a light pool |
| close-up shows the top of the head | camera "front" taken from bladed shoulders | `cam.ref: "head"` (default for Head targets) |
| impact flash before contact | the flash/burst core started with the shot | flashes start at the impact time only |
| black frames | a JS error in the page | the stills log prints `ERR ...`: fix it, look again |
