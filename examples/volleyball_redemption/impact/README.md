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
