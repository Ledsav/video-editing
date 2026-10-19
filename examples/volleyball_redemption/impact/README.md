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
