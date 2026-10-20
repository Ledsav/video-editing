# Impact frame

`impact.html` poses a rigged Mixamo character at the moment of the spike (each bone aimed at a direction),
lights it in the arena and adds the burst, shockwave and streaks around the 18-panel ball.

The models are not committed; fetch them from the three.js examples:

```bash
for f in Xbot.glb Michelle.glb; do
  curl -sSL -o impact/$f https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/$f
done
../../bin/vedit mograph render impact/impact.html --duration 0.04 --params '{"model":"Michelle.glb"}'
```

`spike_seq.html` is the spike as a shot sequence (male athlete, Xbot): behind-the-hitter set, feet, wide jump,
POV, comic-book impact frame, ball into the court, roar. Render with `bin/vedit render spike_seq.json`.
The ball (`styles/mikasa.js`, `v200wRefMaps`) is matched to a V200W product photo.

Player model (default in `spike_seq.html`): "RIGGED ANIME MALE CHARACTER-1" by Ret.ouchs (Sketchfab), CC BY-SA 4.0.
Not committed: download it from Sketchfab and save it as `impact/anime_male.glb`. The scene credits it on screen.
`intro_ngu.html` is the NEVER GIVE UP intro; `spike_full.json` assembles intro + rendered spike + outro (same template, faster params).

## Converting Cinema 4D mocap (.c4d) without Cinema 4D

`tools/c4d_anim.py` reads joint animation straight from a `.c4d` file (reverse-engineered: big-endian typed
stream, UTF-16BE names, CKey records with rational times and f64 values) and writes a standard glTF `.glb`
(skeleton + baked animation, upright, metres). Rotation convention: Ry(-H)·Rx(-P)·Rz(-B), left-handed → right-handed
by mirroring Z (chosen by minimising foot slide over all 96 order/sign/handedness combinations).

    python3 tools/c4d_anim.py "8-Smash-Take1.c4d" impact/mocap/8-Smash-Take1.glb

`impact/glb_check.html` draws the converted skeleton as a stick-figure contact sheet for verification.
Tested on the Motion Cast "Volley-ball" pack (Cinema 4D 2024); geometry/materials are not extracted.
The mocap and ball model are licensed assets and are not committed.

## Story bookends (final cut)

`story.html` reuses the arena, the anime post pass (`stage.js`, shared with `spike_seq.html`), the character and the retarget:
`part: "intro"` is last year's lost point in grey (`3-Dig in front with one knee on the ground`) and today's eyes (`1-IDLE`);
`part: "outro"` is the match cut from last year's ball to today's, with the roar (`12-Reaction after point obtained-Take3`) and the end card.
`story_full.json` assembles intro + spike + outro with music and sound effects.
`mocap_probe.html` prints a clip's detected events and the hip/hand path (debugging helper).

Retarget notes: the retarget takes bone directions from the capture itself. To turn a clip, rotate the capture's points
(`placer(...).rot` in `story.html`); turning only the root offset leaves the body facing the captured way.
In the converted Motion Cast clips `Head_end` sits on the head joint. `loadMocap` rebuilds it along the head's own axis so the head pitch carries over.
The toon materials keep the source `side`. The face mesh is double-sided, and with front faces only the dark mouth interior shows through it.
Smoothing: `loadMocap` bakes every captured frame and low-passes it. The filter is zero-phase Gaussian, with sigma 1.2 frames for the body,
1.5 for forearms and 2 for hands. Fingers get sigma 3, as offsets from their hand. Frames are then sampled with Catmull-Rom.
Raw marker noise was about 1°/frame on the hands, with up to 14° palm spikes near contact. It showed as jitter, worst in the slow-motion shots,
where one captured frame spans up to 6 video frames.
The spike adds an additive layer on the hitting arm (`attackArm`): a deeper bow-and-arrow cock before contact (elbow high and back)
and a full follow-through after it (arm down across the body). Both are zero at contact, so the hand still meets the ball.
Hands and face: `makeRetarget` limits the wrist's twist (±1 rad from rest) and its bend off the forearm line (0.8 rad). The rig has no twist bones,
so past those limits the wrist skin collapses. Arm layers (`swingChain`) turn the hand and fingers rigidly with the arm.
In the spike, `openHand` straightens the hitting hand's fingers through the attack, because the captured fingers curl into a claw.
The painted face details (eyes, brows, lashes, eye lines, mouth) use unlit materials like the source; lit, the gold rim lights turned the brows into an orange band.
IK: directions alone don't keep contacts on a body with other proportions (shorter torso, different shoulder width and arm length).
The capture's bagher kept 13 cm between the hands, but the character's were 20 cm apart, and his feet slid 7–13 cm.
After the direction pass, `makeRetarget` therefore runs two-bone IK:
- **Ankles:** placed exactly on the capture's, with the knee as the pole.
- **Hands:** placed where the capture's are relative to the chest, scaled to this arm length, with the elbow as the pole.

`xf.footDy` matches standing ankle heights, and `xf.ik = false` turns the IK off.
`retarget_check.html` draws the capture skeleton (red) over the character (blue skeleton, translucent mesh) from the side and front.
It also logs per-joint distances and the hand gap, for example:
`node ../../mograph/render.mjs --html impact/retarget_check.html --out work/rc.mov --duration 6 --fps 2 --opaque 1 --width 1280 --height 540 --stills 2.6,3.4`.

## Character: VRoid "HairSample_Male" (CC0) in a painted volleyball kit

`impact/vrm/HairSample_Male.vrm` is an official VRoid sample by pixiv. It's CC0 (commercial use and modification allowed, no credit required).
It isn't committed. Get it from the `vroid/beta/` folder of github.com/madjin/vrm-samples.
- `loadCharacter` (loadglb.js): renames the VRM humanoid bones to Mixamo names, adds a HeadTop_End marker, and exposes the facial blendshape groups:
  `gltf.expr('angry', 1)`, `'a'`, `'sorrow'`, `'joy'`, `'blink'`.
- `paintKit` (kit.js) hides the VRoid hoodie and trousers, then paints a jersey with a number, shorts, knee pads and socks onto the body texture.
  The hands' UV islands, which sit inside the torso area, are masked out using the skin weights.
- `kitNormalMap` bakes the fabric relief (knit, twill, seams, hems, raised number, quilted pads) into the normal map, and into the colour as fold shading.
- `makeRetarget(..., { rhythm: true })` uses a scapulohumeral rhythm: the shoulder girdle supplies a third of the arm's elevation, so a raised arm doesn't pinch the shoulder.
