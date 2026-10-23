# Edit spec reference (`edit.json`)

Paths are relative to the spec file. Times are seconds (`12.5`), timecodes (`"1:02.5"`)
or, where noted, percentages of the final duration (`"40%"`).

```jsonc
{
  "brief":   { "prompt": "...", "logline": "...", "audience": "...", "duration_target": 60 },  // documentation only
  "output":  { "path": "out/final.mp4", "width": 1920, "height": 1080, "fps": 30,
               "crf": 18, "preset": "medium", "codec": "libx264|libx265|prores_ks",
               "audio_bitrate": "256k", "intermediate_crf": 12 },
  "sources": { "interview": "media/interview.mp4", "drone": "media/DJI_0042.mp4" },
  "story":   { "arc": [ ... ], "tone": "fallback tone", "look": { ... } },
  "sync":    { "beats": "music/track.beats.json", "to": "beats|downbeats", "every": 1, "max_shift": 0.4 },
  "timeline": [ ... ],
  "text":     [ ... ],
  "graphics": [ ... ],
  "effects":  [ ... ],
  "music":    [ ... ],
  "sfx":      [ ... ],
  "captions": { ... },
  "audio":    { "loudness": -14, "duck": { "threshold": 0.02, "ratio": 6, "attack": 20, "release": 450 } }
}
```

Common sizes: 16:9 `1920x1080`, vertical/Reels/TikTok `1080x1920`, square `1080x1080`, 4:5 `1080x1350`.

## Story arc → dynamic color grading

```json
"story": {
  "arc": [
    {"at": "0%",   "label": "setup",      "tone": "natural",       "intensity": 0.7},
    {"at": "40%",  "label": "tension",    "tone": "cold_thriller", "intensity": 0.9, "ease": "smooth"},
    {"at": "75%",  "label": "climax",     "tone": "low_key_dramatic", "intensity": 1.0, "overrides": {"grain": 0.4}},
    {"at": "100%", "label": "resolution", "tone": "golden_hour",   "intensity": 0.9}
  ],
  "look": {"letterbox": 2.39, "grain": 0.15}
}
```

- Between keyframes, every grade parameter is interpolated (`ease`: `smooth` default, `linear`,
  `hold` = keep previous look until this keyframe, `snap` = switch immediately).
- Each clip is graded from the arc value at its first frame to the value at its last frame,
  so the color shifts continuously *inside* clips too.
- Keyframes can be anchored to clips instead of times: `{"at_clip": "ch4", "offset": 0, "tone": ...}`
  (`"anchor": "end"` to use the clip's end), so the arc follows re-timing.
- `look` holds global grade overrides applied to every keyframe, plus `letterbox` (aspect ratio of bars).
- A clip's own `"grade"` replaces the arc for that clip: `"grade": "noir"` or
  `{"tone": "noir", "intensity": 0.8, "overrides": {...}}`. Use `{"overrides": {...}}` alone
  to keep the arc and adjust (e.g. `{"overrides": {"exposure": 0.3}}` to fix an underexposed shot).

### Grade parameters (for `overrides` and custom keyframes)

| param | range | effect |
|---|---|---|
| exposure | -2..2 stops | brightness in linear light |
| contrast | -1..1 | S-curve around `pivot` (0.45) |
| saturation | 0..2 | 1 = unchanged |
| vibrance | -1..1 | saturates muted colors more than vivid ones |
| temperature / tint | -1..1 | warm/cool, magenta/green |
| lift / gamma / gain | [r,g,b] | color wheels; lift -0.2..0.2, gamma/gain 0.5..1.5 |
| shadow_tint / highlight_tint | `{"color":"#hex","amount":0.2}` or `"#hex@0.2"` | split toning |
| tint_balance | -1..1 | favour shadow or highlight tint |
| black_point | -0.1..0.15 | >0 matte/faded blacks, <0 crushed |
| highlight_rolloff | 0..1 | soft film shoulder |
| bleach | 0..1 | bleach bypass |
| mono / mono_mix | 0..1 / [r,g,b] | black and white with channel mixer |
| grain, vignette, bloom, sharpen, chroma_shift | 0..1 | finishing effects |

Export any look as a LUT for other software: `bin/vedit lut teal_orange --out teal_orange.cube`.

## Timeline clips

```json
{"id": "c3", "source": "drone", "in": 12.0, "out": 16.5,
 "speed": 1.0, "volume": 1.0, "mute": false,
 "fit": "cover|contain|blur_fill", "crop": [x, y, w, h],
 "motion": "push_in" | {"type": "ken_burns", "amount": 0.12, "from": [0.3,0.4], "to": [0.6,0.5], "ease": "smooth"},
 "transition": "crossfade" | {"type": "whip_left", "duration": 0.3, "sfx": "whoosh"},
 "grade": null, "beats": 4, "snap": true, "captions": true, "label": "hero shot"}
```

- `out` or `duration` (output seconds). Stills (`.jpg/.png`) default to 3 s; use `motion` on them.
- Solid slug: `{"id": "black", "color": "#000000", "duration": 1.0}`.
- Motion-design scene: `{"id": "s1", "hyperframes": "hf/opener", "variables": {...}}` (or a built-in
  such as `"scene-kinetic"`): a HyperFrames composition rendered full-screen as a clip, lasting its
  own `data-duration` unless `duration`/`out` is given (see [hyperframes.md](hyperframes.md) and the
  motion-design skill). Scenes keep their own colours unless `"graded": true`.
- `speed` 0.5 = slow motion, 2 = double speed (audio pitch-preserved).
- `fit`: `cover` crops to fill, `contain` letterboxes, `blur_fill` puts vertical footage on a blurred copy of itself.
- `crop`: normalized source region (reframing), applied before fit.
- `motion`: `push_in`, `pull_out`, `pan_left|right|up|down`, `ken_burns`, `shake` (handheld energy), `drift` (subtle float),
  `crash_zoom` (fast zoom into `focus` [x, y] over `duration` s starting `at` s, then hold; the Tarantino crash zoom). `amount` = zoom fraction.
- `transition` is the transition INTO this clip from the previous one.

### Transitions

| name | what | default |
|---|---|---|
| `cut` | hard cut | |
| `crossfade`, `dissolve`, `fade_grays` | soft blends | 0.6–0.8 s |
| `dip_black`, `dip_white` | through black / white | 0.8 / 0.6 s |
| `flash` | white flash + impact sfx | 0.25 s |
| `whip_left|right|up|down`, `slide_left|right` | fast directional push + whoosh | 0.3 s |
| `zoom_in`, `blur`, `pixelate`, `radial`, `wind`, `slice`, `iris_open|close` | stylized xfades | 0.5–0.7 s |
| `glitch` | cut + RGB split, noise and slice displacement + glitch sfx | 0.3 s |
| `zoom_punch` | cut + incoming shot slams from 122% to 100% + flash + impact | 0.35 s |
| `light_leak` | crossfade + screen-blended warm light leak (built-in `light-leak`; `variables` pass through) | 1.0 s |
| `film_burn` | cut hidden under a celluloid burn (built-in `film-burn`) | 1.2 s |
| `hyperframes` | a HyperFrames composition that covers the frame: `{"type":"hyperframes","project":"shape-wipe","duration":0.9,"variables":{...}}`; `cover_at`, `blend`, `opacity` optional | composition |
| any ffmpeg xfade name | `circleopen`, `hlslice`, `squeezeh`, `coverleft`, `revealright`, `diagtl`, ... | 0.6 s |

Every transition accepts `duration`, `sfx` (name or file, `"none"` to disable), `sfx_volume`,
and `effect`/`overlay` to layer extras.

## Text (animated typography, rendered with libass)

```json
{"text": "THE *FUTURE* IS NOW", "style": "kinetic", "at_clip": "c5", "offset": 0.2, "duration": 2.5,
 "position": "center", "nudge": [0, -0.1], "animation": "words", "out": "fade",
 "color": "#ffffff", "accent_color": "#ff3b30", "size": 0.12, "font": "Anton",
 "subtext": "second smaller line", "box": "#000000@0.5", "uppercase": true}
```

- Timing: `start` / `end` / `duration`, or `at_clip` + `offset` (+ `"anchor": "end"`). End at another
  clip with `"end_at_clip": "ch3"` (its start; `"end_anchor": "end"` for its end, `"end_offset"` to nudge).
  The same timing keys work for `graphics`, `effects`, `music` and `sfx`. Default length: the anchored clip, else 3 s.
- `*word*` renders in `accent_color`.
- Styles: `title`, `subtitle`, `lower_third`, `caption`, `social`, `kinetic`, `quote`, `chapter`, `credit`, `handwritten`.
- Positions: `center top bottom left right lower_left lower_right upper_left upper_right` or `[x, y]` normalized. `nudge` shifts by a fraction of the frame.
- In animations: `none fade slide_up slide_down slide_left slide_right pop zoom_in tracking_in blur_in typewriter words flicker`. Out: `none fade blur zoom`. `in_duration` / `out_duration` in seconds.
- `size`, `spacing`, `outline`, `shadow` are fractions of frame height.
- Fonts installed by setup: Bebas Neue, Anton, Oswald, Archivo Black, Montserrat, Space Grotesk, Playfair Display, DM Serif Display, Cormorant Garamond, Permanent Marker, plus Inter/DejaVu.

## Graphics (HyperFrames overlays)

```json
{"hyperframes": "title-card", "at_clip": "c1", "offset": 0.5, "duration": 4,
 "variables": {"title": "NORTH\nBOUND", "subtitle": "a film by Ana", "accent": "#ffb347"},
 "blend": "normal|screen", "opacity": 1.0}
{"hyperframes": "hf/logo-reveal", "start": "90%", "duration": 3}
```
`hyperframes` is a composition folder relative to the edit, or a built-in (`bin/vedit hf list`).
`duration` defaults to the composition's own and stretches it when different. Identical graphics
(same composition, variables and length) render once. See [hyperframes.md](hyperframes.md).

## Effects (accents on the whole frame, e.g. on beat drops)

`{"type": "glitch|flash|rgb_split|blur|mono|invert|dim", "at_clip": "c7", "offset": 0, "duration": 0.3, "intensity": 1}`

## Music

```json
{"path": "music/track.mp3", "start": 0, "in": 12.0, "duration": 45, "volume": 0.8, "gain_db": -3,
 "fade_in": 1.0, "fade_out": 3.0, "duck": true, "loop": false}
```
- `filter`: optional raw ffmpeg audio filter applied to the track, e.g. `"atempo=0.9,lowpass=f=2000"` for a softer, slower, distant feel.
- `in` skips into the track (start on the drop); `start` is when it enters the edit (or `at_clip`).
- `duck: true` compresses the music under clip audio (dialogue). Mute b-roll (`"mute": true`) so it does not trigger ducking.
- Multiple tracks can overlap (crossfade them with fades).

## Sound effects

`{"name": "whoosh|impact|boom|riser|reverse_swell|glitch|tick" or "path": "sfx/x.wav", "at_clip": "c5", "offset": 0, "volume": 0.8, "peak": 0.0}`
Built-in effects are aligned so their peak lands on `at` (a riser ends exactly there, a reverse swell resolves there).

## Captions from transcripts

```json
"captions": {"transcripts": {"interview": "work/interview.transcript.json"},
             "style": "caption|social", "max_chars": 32, "max_words": 4, "accent_color": "#ffd400"}
```
Words are mapped through the cuts and speed changes onto the output timeline. `social` = big
centered words with the current word highlighted. Disable per clip with `"captions": false`.

## Beat sync

`"sync": {"beats": "music/track.beats.json", "to": "beats|downbeats", "every": 2, "max_shift": 0.4, "offset": 0}`
- Every cut moves to the nearest beat (within `max_shift`) when the source has the footage.
- `"beats": N` on a clip makes it last exactly N beats; `"snap": false` opts a clip out;
  `"from_clip": "c12"` snaps only that clip and the ones after it (e.g. when the beat-driven music starts mid-edit).
- The beat file must be relative to the music's placement: if the music starts at 0 with `in: 0`, beat times are output times. Otherwise set `offset` (= music start − music in).
