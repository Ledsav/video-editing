# Scene params: `anime_shot.html` and `anime_pages.html`

Paths are relative to the project folder (the scenes sit next to `edit.json`). Colours are CSS hex.

## anime_shot.html

```json
{"id": "fight", "html": "anime_shot.html", "duration": 6.2, "params": {
  "character": "assets/characters/HairSample_Male.vrm",
  "materials": {"Tops": "#b8141f", "Bottoms": "#1a1d29", "Shoes": "hide"},
  "clips": {"box": "assets/mocap/cmu/13_17.bvh"},
  "shots": [ {...}, {...} ]
}}
```
The clip's `duration` must equal the sum of the shots' `dur` (the log says so when it doesn't).

### Global params
| param | default | |
|---|---|---|
| `character` | `assets/characters/HairSample_Male.vrm` | VRM 0.x/1.0 (VRoid) or a Mixamo-rigged GLB |
| `height` | 1.75 | metres, sole to scalp |
| `skin` | `#c8957a` | multiplies the skin textures. Lit skin must stay out of the cel pass's top band or the face reads white: darker than you think |
| `hair` | – | multiplies the hair |
| `materials` | `{}` | `{"<regex on material/mesh name>": "#hex" or "hide"}`. VRoid names: `Tops`, `Bottoms`, `Shoes`, `HAIR`, `Body_00_SKIN`, `Face_00_SKIN` (all: `python3 tools/vrm_meta.py --materials`). Warm rims and the cel pass lift colours: pick darker, more saturated ones |
| `clips` | `{}` | `key: "file.bvh"` or `{"file", "stand": [t0, t1], "anim": 0, "tpose": false}`; `stand` = a standing stretch to calibrate from when the take doesn't start standing (a leading T-pose frame is detected and used automatically) |
| `props` | `{}` | `key: {"sphere": {"radius": 0.11, "color": "#f2c94c"}}` or `{"glb": "assets/props/x.glb", "scale": 1}` |
| `set` | night arena | `sky: [top, mid, bottom]`, `bokeh` (count), `warm`, `cool`, `lamps`, `seed`, or `image` (a background picture); `floor` (`#hex` or `null` = none), `floorSize`, `pool` (light pool under the action, 0-1), `poolSize`, `poolColor`, `lines` (court lines colour), `fade`, `shadow` (0-1) |
| `lights` | warm rims | `key`/`keyI`, `rim`/`rimI`, `rim2`/`rim2I`, `back`/`backI` (blue back rim), `fill`/`fillI` (from the camera), `sky`/`ground`/`amb` |
| `cel`, `anime` | 0.75, 1 | cel strength; `anime: 0` = the older 4-band halftone look |
| `lens`, `subframes`, `shutter` | 0.25, 3, 0.5 | barrel distortion; motion blur samples and shutter (fraction of a frame) |
| `grain`, `vignette`, `exposure` | 0.07, 0.5, 1.1 | |
| `inkHit`, `inkRim`, `inkThr`, `inkLine` | 10, 1.2, 0.95, 2.4 | impact-frame lighting (light at the hit, rim from behind), light/shadow threshold, line width |
| `debug` | 0 | 1: logs each clip's events and strikes, and the character's expression names |
| `art` | 0 | 1: no grain, flash or vignette (key-art stills) |

### Shot
| key | |
|---|---|
| `name`, `dur` | seconds on screen |
| `clip` | a key of `clips`; omit for an empty set (props only) |
| `from`, `to` | take time played over the shot (shorter than `dur` = slow motion); default: real speed from `from` |
| `keys` | `[[u, take t], ...]` instead: speed ramps (u = 0..1 through the shot's action time) |
| `ease` | easing on u (`outQuad` = fast then slow) |
| `place` | `{x, z, face, at, anchor}`: the hip at take time `at` lands on (x, z), the body turned to face `face` degrees (0 = +z); `anchor: true` cancels the capture's travel |
| `face` | VRM expressions, `{"angry": 0.8, "a": 1}` or ramps `{"a": [0, 1]}`; names: `angry`, `sorrow`, `joy`, `fun`, `a i u e o` (mouth), `blink` |
| `fist` | 0-1 (or a ramp): close the hands. Takes without finger data get relaxed half-curled hands (0.35) |
| `cam` | see below |
| `impact` | one or a list, see below |
| `speed` | speed lines 0-1 or `[from, to]`; `speedColor: [r, g, b]` |
| `zoom` | radial zoom blur 0-0.3 (or a ramp) |
| `lens`, `cel`, `shutter`, `subframes` | per-shot overrides |
| `grade` | `{"sat": 1, "tint": [r, g, b]}`; `memory: true` = the grey past (sat 0.07, cold tint) |
| `flashAt` | white flash at these shot seconds |
| `props` | `key: {"attach": "RightHand", "offset": [x, y, z]}` or `{"path": [[t, x, y, z], ...]}` (t = take time) or `{"pos": [x, y, z]}`; `spin` rad/s |

### Camera (`cam`)
Around a target, relative to where the character faces **at the shot start**:
`target` (a bone: `Hips`, `Head`, `Spine2`, `RightHand`, `LeftFoot`... or `[x, y, z]`), `orbit` degrees
(0 = in front, 180 = behind, 90 = his left), `dist` m, `height` m above the target, `lookY` aim offset, `fov`,
`roll` degrees, `to: {...}` = the values at the end of the shot (eased with `ease`, default `inOutSine`).
`follow: false` locks the target at the shot start (a fixed frame the action moves through), `shake` adds handheld
noise. `ref`: what "in front" means: `chest` (shoulders, default), `hips`, `head` (where the face points: default for
Head/Neck targets; fighters and hitters stand bladed, so their shoulders face sideways). `facing`: a fixed heading
instead. `pos` + `look`: absolute world positions.

Lenses: 14-24° portrait close-ups, 28-40° medium, 45-60° action wides (with `lens` 0.3-0.8 for the anime barrel).
Low angles (`height` < 0 on Hips) for power; overhead for defeat.

### Impact (`impact`)
| key | default | |
|---|---|---|
| `at` | – | shot seconds, `{"clip": take t}`, or a take event: `"contact"`, `"takeoff"`, `"land"` |
| `hold` | 0.6 | the action freezes this long (the shot gets longer by it: `dur` includes it) |
| `style` | `ink` | `ink` (brush drawings), `invert` (negative / red flicker), `flash` (white flash, no hold) |
| `step` | 0.25 | seconds per drawing; each new drawing cuts with one white frame |
| `palettes` | `[0,1,2,3]` | per drawing: 0 white on black, 1 black on paper, 2 black on red, 3 mint on black |
| `target` | `RightHand` | where the hit is: fisheye, flash, streaks and light centre on it |
| `angles` | false | each drawing from its own camera angle around the target (`dist` scales them) |
| `bulge`, `flash`, `streaks` | 0.85, 1, 1 | fisheye strength, flash size, energy streaks |
| `shake`, `zoom`, `punch` | 0.08, 0.3, 10 | after the release: camera shake, zoom blur, fov punch (degrees) |

The release (the 0.12 s after an ink hold) is smeared automatically (6 subframes over a full frame).

`window.ANIME_TIMES` (logged, and saved by shot_stills to `work/anime_times/<clip>.json`) gives the shots' starts
and each impact's time in clip seconds: the sound plans reference them.

## anime_pages.html

| param | |
|---|---|
| `page` | `op` (title card) or `ed` (end card) |
| `bpm`, `down` | the song's tempo and first downbeat in the page: the key art slams on beat 0, the title characters stamp on beats 1..N, the romaji on N+1, the badge on N+2 |
| `title` | the stamps: `["一", "撃", "！"]` (one entry per stamp; 2-5 entries) |
| `romaji`, `english` | |
| `ep`, `epTitle`, `epEn` | the badge: `第1話`, `最初の一撃`, `EPISODE 1 · THE FIRST PUNCH` |
| `art`, `artNeg` | op key art and its negative (from the last stamp); missing files fall back to an ink gradient |
| `panel` | ed: the manga panel picture |
| `motto`, `mottoEn`, `mottoAccent` | ed: vertical brush motto (≤ 6 characters), the English line, the word in the accent colour |
| `tbc`, `tbcEn` | `つづく`, `TO BE CONTINUED` (or `終`, `THE END`) |
| `credit` | ed: the credits strip (HTML; `&nbsp;·&nbsp;` between entries) |
| `colors` | `accent` (yellow), `band` (blue), `ink`, `paper`, `red` |
| `fonts` | `jp` (logo face), `brush` (brush face): ttf/otf paths |
| `flashOut`, `fadeAt` | op: the white flash out (s); ed: the fade to black (s) |

Duration: op ≈ `down` + (N + 3) beats + 0.3 s (3.5 s at 140 bpm with 3-4 stamps); ed 3-4 s on the song's final chord.
Portrait renders (1080x1920) re-lay the pages for 9:16.
