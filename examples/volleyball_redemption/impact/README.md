# Impact frame

`impact.html` poses a rigged Mixamo character at the moment of the spike (each bone aimed at a direction),
lights it in the arena and adds the burst, shockwave and streaks around the 18-panel ball.

The models are not committed; fetch them from the three.js examples:

```bash
for f in Xbot.glb Michelle.glb; do
  curl -sSL -o impact/$f https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/$f
done
../../bin/vedit hf snapshot impact/impact.html --times 0 --variables '{"model":"Michelle.glb"}'
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
`part: "outro"` is the match cut from last year's ball to today's, with the roar (both fists up, see below) and the end card.
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
Rest calibration: the Motion Cast skeleton's joints don't sit where the rig's do. Its spine zig-zags: the lower-spine joint sits behind
the pelvis joint and the head joint well ahead of the neck. Its collarbones run from the sternum back to the shoulders, and its ankle sits
lower over the toe. Copied raw, the segment directions tipped the standing character's pelvis 27° back and pulled his collarbones 24° back.
In the cheer, the sway-back made the hips read as facing the other way. `makeRetarget` therefore turns each segment by the difference
between the capture standing still and the rig at rest, in the body's own frame. `CAP_STAND` holds the Motion Cast values, measured
over `1-IDLE` with `calib_probe.html`; a BVH take is calibrated from its own opening frames (`measureStand`). `rtFlags: {restCal: false}`
turns the calibration off for comparisons. `cheer_compare.html` draws the raw capture as a mannequin next to the character.

## Roar: Bandai Namco Research Motiondataset-2 (CC BY-NC 4.0)

The roar at the end of the spike and today's shot in the outro use "raise up both hands, masculine" takes (`_007` and `_002`). These come
from github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset, `dataset/Bandai-Namco-Research-Motiondataset-2/data/`.
The licence is CC BY-NC 4.0: non-commercial use only, with credit, which both scenes show. The files aren't committed; put them in
`impact/mocap/bandai/`. `loadMocap` reads BVH: three's BVHLoader, joints renamed to the capture's names, cm to m, a mid-spine joint
added. These takes have no fingers, so `xf.fist` closes the hands into fists, with the thumb wrapped over the fingers.
`roar: "win"` (spike) and `today: "win"` (outro) bring back the Motion Cast won-point reaction.
`retarget_check.html` draws the capture skeleton (red) over the character (blue skeleton, translucent mesh) from the side and front.
It also logs per-joint distances and the hand gap, for example:
`../../bin/vedit hf snapshot impact/retarget_check.html --duration 6 --width 1280 --height 540 --times 2.6,3.4` for the stills and
`../../bin/vedit hf console impact/retarget_check.html --duration 6 --width 1280 --height 540 --times 2.6,3.4` for the log.

## Character: VRoid "HairSample_Male" (CC0) in a painted volleyball kit

`impact/vrm/HairSample_Male.vrm` is an official VRoid sample by pixiv. It's CC0 (commercial use and modification allowed, no credit required).
It isn't committed. Get it from the `vroid/beta/` folder of github.com/madjin/vrm-samples.
- `loadCharacter` (loadglb.js): renames the VRM humanoid bones to Mixamo names, adds a HeadTop_End marker, and exposes the facial blendshape groups:
  `gltf.expr('angry', 1)`, `'a'`, `'sorrow'`, `'joy'`, `'blink'`.
- `paintKit` (kit.js) hides the VRoid hoodie and trousers, then paints a jersey with a number, shorts, knee pads and socks onto the body texture.
  The body and the face get the same skin tone (`SKIN_TONE`). It is deep enough that lit skin stays out of the cel pass's top tone band, which reads as white.
  The hands' UV islands, which sit inside the torso area, are masked out using the skin weights.
- `kitNormalMap` bakes the fabric relief (knit, twill, seams, hems, raised number, quilted pads) into the normal map, and into the colour as fold shading.

## Opening and ending pages (anime_pages.html)

`page: "op"` is the title card before the story (3.5 s): 打ち返せ！ is stamped kanji by kanji on the song's beats over the ink key
art, which flips to its negative on the last stamp; then UCHIKAESE! / HIT IT BACK and the episode badge 第1話「最後の一点」.
`page: "ed"` is the end card (3.4 s, on the song's final chord): a tilted manga panel with the eyes, 諦めない in vertical brush,
NEVER GIVE UP., つづく / TO BE CONTINUED and a credits strip. Every text is a param.
- Fonts: Dela Gothic One and Yuji Boku (SIL Open Font License), not committed. Put them in `impact/fonts/` from
  github.com/google/fonts (`ofl/delagothicone/DelaGothicOne-Regular.ttf`, `ofl/yujiboku/YujiBoku-Regular.ttf`). The page loads them with
  the FontFace API (file:// pages can't use @font-face URLs).
- Art: stills rendered from the film without any text, with `art: 1`: `impact/art/op_key.png` = spike_seq.html at 4.25 s,
  `op_key_neg.png` = 4.60 s, `ed_eyes.png` = story.html (part intro) at 6.30 s, all 1920x1080.
