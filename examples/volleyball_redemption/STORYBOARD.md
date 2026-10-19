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
