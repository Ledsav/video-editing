# RISE AGAIN: a volleyball redemption story

**Logline.** A player loses on match point, nearly quits, grinds for a year, and wins the final from 19–24 down.
The **ball is the hero**: it's in every scene, and at the end it rises like the sun.

**Format.** 16:9, 1920×1080, 30 fps, ~48 s. All motion design (HTML scenes, no footage).

## Style frame

| | |
|---|---|
| Adjectives | cinematic, bold, kinetic |
| Palette | ink `#0a1020` (night, dominant) · cream `#f3ede2` · **orange `#ff6b2c` (accent = hope, the ball)** · gold `#ffb547` (victory) · red `#e8473a` (loss only) · steel `#8ea0c4` (doubt) |
| Type | **Anton** for display (tight leading) + **Montserrat** for text (light for inner voice, wide-tracked small caps for labels) |
| Grid | 7% / 9% safe margins, chapter tag top-left (`01 — THE DREAM`), centred hero |
| Shapes | the ball (circle), court lines, rings, skewed diagonal wipes, sunburst; grain + vignette on every scene |
| Colour arc | night blue → red (the loss) → cold steel (the doubt) → **orange takes over** (the grind) → gold sunrise (the lesson) |

## Music

| Act | Track | Feel |
|---|---|---|
| I: the fall (0–16 s) | `music/fall.wav`: sad, 68 bpm, minor, no drums | lonely, slow |
| II–III: the rise (16 s–end) | `music/rise.wav`: epic, 88 bpm (beat 0.682 s, bar 2.727 s) | drums enter on the cut to 05:00 |

Acts II–III are cut to the 88 bpm bar grid: each scene is 2 or 4 bars long, and the big hits land on downbeats.

## Scenes

| # | Time | Scene | Picture | Copy | Motion / sound |
|---|---|---|---|---|---|
| 1 | 0:00–0:06 | **The Dream** | Empty arena at night. One spotlight flickers on; court lines draw in perspective; the ball floats down into the light, dust in the beam. | EVERY ATHLETE / **HAS A DREAM** | slow push-in, per-letter mask rise · sad bed fades in |
| 2 | 0:05.5–0:10.5 | **The Fall** | Scoreboard *MATCH POINT 24:24*, then AWAY rolls to **25** in red with a red wash. The board sinks, the ball slams into the floor, the floor cracks, and the ball bounces and rolls to rest. | MATCH POINT · **LOST** (giant red outline) | dip to black in · squash on impact, shockwave rings, camera shake · tick + impact + boom |
| 3 | 0:10–0:15 | **The Doubt** | Cold rain on an empty court; the ball lies still, desaturated. Then its rim catches fire and orange returns. | *Some nights, you want to quit.* → **OR YOU COME BACK.** | grey dissolve in (the ball match-cuts) · words fade in through blur · ignition glow · reverse swell into the cut |
| 4 | 0:15–0:26 | **The Grind** (4 bars) | Bar 1: orange floods out of the ball; **04:59 → 05:00** on the beat. Bar 2: AGAIN. AGAIN. AGAIN. **AND AGAIN.**, one per beat, while the ball dribbles. Bar 3: ring counter **1,000 serves a day**, with the ball orbiting. Bar 4: **DAY 1 → 365** as a calendar of dots fills up. | AM · FIRST ONE IN / SERVES A DAY / No days off from the dream. | epic track hits on the cut · skewed wipes on each bar line · whooshes |
| 5 | 0:26–0:31 | **The Return** (2 bars) | The final, fifth set, down **19:24**. Side-view court: every beat a ball arcs over the net with a dotted trail and lands: 20, 21, 22, 23, **24:24**. | ONE POINT AT A TIME. | score pops orange on each landing, light shake |
| 6 | 0:31–0:37 | **The Spike** (2 bars) | Match point. The player rises from below in slow motion against dark rays and cocks the arm while speed lines converge on the ball. **Smash on the downbeat**: white flash, the world turns orange, and the ball rockets out. | MATCH POINT. → 25 : 24 · MATCH POINT / **REDEMPTION.** | riser → impact + boom, camera punch, sunburst |
| 7 | 0:37–0:48 | **The Lesson** (4 bars) | Dawn over the court. The ball rises from the horizon like the sun, warming the sky, with a glossy reflection on the floor. | *You will fall. You will lose.* / *Perseverance is* **GETTING BACK UP.** / **RISE AGAIN.** with EVERY SET · EVERY POINT · EVERY DAY | lockup on the downbeat, orange rule draws in, fade to black |

## Files

- `edit.json`: the assembled edit (scenes, transitions, music, sfx)
- `scenes/common.js`: shared design system (palette, the ball, grain, text reveals)
- `scenes/s1_dream.html` … `scenes/s7_lesson.html`: one page per scene (a pure function of time)
- Music is generated: `bin/vedit synth-music --mood sad --duration 20 --seed 7 --out music/fall.wav` and
  `bin/vedit synth-music --mood epic --duration 36 --seed 11 --out music/rise.wav`. Swap in a licensed track for release.

## Render

```bash
bin/vedit new volleyball_redemption            # or copy this folder into projects/
cp -r examples/volleyball_redemption/* projects/volleyball_redemption/
cd projects/volleyball_redemption
../../bin/vedit synth-music --mood sad  --duration 20 --seed 7  --out music/fall.wav
../../bin/vedit synth-music --mood epic --duration 36 --seed 11 --out music/rise.wav
../../bin/vedit render edit.json                # -> out/final.mp4 (~48 s)
```

---

# Final cut: THE SAME POINT (anime spike, ~26 s)

`story_full.json` replaces the first version above. It uses one 3D arena and one character
(the anime male, retargeted Motion Cast captures) all the way through. Then is grey, now is in colour.
The scoring follows volleyball rules: sets 1–4 go to 25 with a two-point lead, so last year's set 4 ended 24:26 and this year's ends 26:24.

| # | Time | Shot | Picture | Copy | Sound |
|---|---|---|---|---|---|
| 1 | 0:00–0:00.7 | Title | black | ONE YEAR AGO | muffled `fall.wav` (lowpass) |
| 2 | 0:00.7–0:03 | The dig (grey) | wide broadcast angle; he waits in the back court, the opponent's spike lands a hand beyond his reach as he drops to a knee; inverted impact frame on the floor | ONE YEAR AGO · FINAL · SET 4 · 24 : 25 | reverse swell + impact |
| 3 | 0:03–0:04.35 | Floor (grey) | low on the floor: kneeling, the ball bouncing away | **24 : 26** · FINAL LOST | boom |
| 4 | 0:04.35–0:05.5 | Kneel (grey) | his face, hand to his chest | *He never forgot that point.* | |
| 5 | 0:05.5–0:06.95 | Eyes (colour) | white flash to colour, extreme close-up on his eyes | TODAY · FINAL · SET 4 → **MATCH POINT 25 : 24** | riser + impact into `rise.wav` |
| 6 | 0:06.95–0:08.2 | The set | the ball rising from the setter into the lights | **THIS TIME, HE ATTACKS.** | whoosh + boom |
| 7 | 0:08.2–0:18 | The spike | `spike_seq.html`: run-up, ground-level liftoff with an impact frame, rise (the bow drawn: elbow back), comic impact frame (held drawn bow, whip, contact, arm all the way down), ball flight, floor hit-stop + BAM, roar with arms in a V | 26 : 24 | riser, impact/boom on takeoff, contact and floor (contact on a downbeat) |
| 8 | 0:18–0:20 | Last year (grey) | low on the floor: last year's ball rolls to a stop in front of the kneeling player | *He lost this point once.* | muffled `fall.wav` |
| 9 | 0:20–0:22.2 | Today (colour) | match cut, same lens: today's ball in the cracked floor, then a tilt up to him roaring | *He never stopped coming back.* | impact + boom, `rise.wav` returns |
| 10 | 0:22.2–0:25.6 | End card | the Mikasa ball turning on navy | **NEVER GIVE UP.** / EVERY SET · EVERY POINT · EVERY DAY / credits | reverse swell + boom, fade to black |

Files: `impact/story.html` (`part`: `intro` | `outro`), `impact/spike_seq.html`, shared `impact/stage.js` (arena + anime post pass),
`impact/mocap.js` (retarget), `tools/c4d_anim.py` (C4D → glTF). Licensed assets (mocap, ball model, character) are not committed.

Music: the user's own tracks (Suno), cut to the picture by `tools/user_music.py` from `user_audio/` (not committed):
- 終わったなら (86 bpm) for the past: its loud opening over the dig, its quiet bass-less passage from the moment last year's ball lands;
  the same passage returns under last year's ball in the outro.
- 打ち返せ (136 bpm) for today: its drop on THIS TIME, HE ATTACKS. (the break before it under the eyes), a cut to silence on the rage
  close-up, its loudest section slamming in on the floor impact (BAM) under the roar, and its ending under the end card.
- The scream on the rage close-up comes from Waaaaah! (its rising "WAAAAH" at 8.45 s), cut off by the gunshot at contact.

Sound design: `tools/anime_sound.py` writes the sound effects and the crowd as stems locked to the picture (and an original synthesized
score, `music/anime_score.wav`, which the film used before the user's tracks).
- Synthesized score:
  - a lonely muffled piano in D minor for the past
  - an orchestra hit on the flash and a string ostinato build
  - an anime-rock drop on THIS TIME, HE ATTACKS. (141.7 bpm, so the contact lands on a downbeat)
  - near silence in the comic frame (a heartbeat and one tense note)
  - the full chorus after the hit, a piano callback in grey, and a final D major chord
- Sound effects: one per action: run-up squeaks, the ground cracking on takeoff, the arm whip, the palm on leather with a sub drop and a time-freeze ring,
  the ball's doppler pass, the BAM with debris, last year's ball rolling to a stop, and a sparkle on the eyes.
- Crowd: muffled in the past, alive today, erupting on 26:24.

```bash
cd projects/volleyball_redemption
python3 tools/anime_sound.py                 # -> music/anime_score.wav, sfx/anime_sfx.wav, sfx/anime_crowd.wav
python3 tools/user_music.py                  # -> music/user_score.wav, sfx/user_scream.wav, sfx/user_cannon.wav, sfx/anime_sfx_duck.wav (from user_audio/)
../../bin/vedit render story_full.json       # -> out/volleyball_redemption_final.mp4
```
