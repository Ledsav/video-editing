# Creative direction: from a prompt to editing decisions

## 1. Turn the prompt into an arc

Every edit, even a 15 s reel, has a shape. Write 3–5 beats, each with a feeling, a
relative position and an energy level (1–5):

| structure | beats | good for |
|---|---|---|
| Classic | setup 0% → rising 35% → climax 75% → resolution 100% | short films, docs, brand stories |
| Trailer | world 0% → disruption 25% → escalation 50–85% (faster and faster) → title/sting 90% | trailers, teasers |
| Hook-first | payoff 0% → context 15% → build 40% → payoff again 85% | social, reels, ads |
| Journey / montage | place A → transition → place B → ... → home | travel, events, recaps |
| Before → after | problem (cold, desat) → turn → solution (warm, vivid) | product, transformation, fitness |

Feelings → tones (`bin/vedit tones --mood <word>`):

| feeling | tone | intensity hint |
|---|---|---|
| calm, honest, everyday | natural, documentary | 0.6–0.8 |
| wonder, dream, innocence | dreamy_pastel, high_key_bright | 0.7–0.9 |
| nostalgia, memory, flashback | vintage_film, sepia (strong flashback) | 0.8–1.0 |
| tension, suspense, isolation | cold_thriller, moody_desat | 0.8–1.0 |
| danger, villain, climax | low_key_dramatic, bleach_bypass | 0.9–1.0 |
| fear, dread | horror_green | 0.8–1.0 |
| grit, struggle, sport | bleach_bypass, desert_heat | 0.7–0.9 |
| epic, heroic, adventure | teal_orange | 0.8–1.0 |
| hope, warmth, resolution, love | golden_hour, romantic_soft | 0.8–1.0 |
| energy, fun, hype, product | vibrant_pop, cyberpunk_neon (night/tech) | 0.8–1.0 |
| timeless, stark, crime | noir | 1.0 |

Contrast drives meaning: a resolution feels warm because what came before was cold. Plan the
color journey as a whole (look at the storyboard), not shot by shot. Big tone jumps belong at
story turns, ideally hidden under a transition or a hard cut on a beat (`"ease": "snap"`).

## 2. Pacing

| energy | average shot length | cutting |
|---|---|---|
| 1 contemplative | 4–8 s | dissolves, long holds, slow push-ins |
| 2 calm | 3–5 s | cuts on action, gentle motion |
| 3 engaged | 2–3 s | cuts on beats every 2nd beat |
| 4 tense | 1–2 s | cuts on every beat, shake/drift, glitch accents |
| 5 climax | 0.3–1 s | cuts on every beat or half-beat, punch-ins, flashes, then HOLD the payoff shot |

- Accelerate into the climax, then give the payoff room (2–4 s) to land.
- Cut on action (movement continues across the cut) and on sound (a beat, a word ending).
- Open strong: first 1–2 s must hook (social) or establish (film).
- End deliberately: hold, title card, dip to black, music resolves (fade_out 2–4 s).
- Use `in`/`out` to trim inside shots: skip the camera settling and the drift at the end.

## 3. Transition vocabulary

| intent | use |
|---|---|
| continuous time, same scene | `cut` (90% of all edits) |
| time passes, softness, memory | `crossfade`, `dissolve`, `dip_black`, `light_leak` |
| chapter / location change | `dip_black` + `chapter-marker`, `ink-spread`, `bars-stagger` |
| energy, momentum, travel | `whip_*`, `slide_*`, `zoom_in`, `shape-wipe` |
| impact, drop, reveal | `zoom_punch`, `flash`, + `shape-burst` / `speed-lines` graphics |
| tech, error, unease | `glitch`, `pixelate`, `slice`, `glitch-title` |
| nostalgia, analog | `film_burn`, `light_leak`, `vintage_film` tone |
| brand / playful | `circle-reveal`, `bars-stagger`, `shape-wipe` with brand colors |

Rules: one transition family per piece (plus cuts); stylized transitions only at structural
moments; match direction to on-screen motion (subject moves right → `whip_right`).

## 4. Typography

| tone | title font | support font | animation |
|---|---|---|---|
| cinematic/epic | Bebas Neue, Anton | Montserrat (tracked caps) | tracking_in, title-card |
| elegant/doc | Playfair Display, DM Serif Display | Montserrat | blur_in, fade |
| tech/modern | Space Grotesk, Archivo Black | Inter | typewriter, glitch-title |
| social/hype | Anton, Archivo Black | Montserrat Bold | words, pop, kinetic-type |
| personal/playful | Permanent Marker | Montserrat | pop |

- One display font + one support font. Accent color from the grade's highlight tint.
- Safe areas: keep text inside 7% horizontal / 9% vertical margins (styles do this); for
  vertical social video keep captions above the bottom 20% (UI overlays).
- Reading time ≈ 0.3 s/word + 1 s. Kinetic words: one per beat (`beat` param = beat period).

## 5. Music and sound

- Pick or place music to match the arc: enter on a downbeat, put the drop at the climax
  (use `in` to skip intros; `beats` output shows energy rises).
- Cut to the music: `sync.every: 2` for calm, `1` for energetic sections; give hero shots `"beats": 4/8`.
- Duck under dialogue (`duck: true`), mute b-roll audio unless its natural sound helps.
- Sound design sells transitions: `whoosh` on whips, `impact`/`boom` on punches and title hits,
  `riser` into a drop (ends on it), `reverse_swell` into a big cut, `glitch` on glitches.
  Keep sfx 3–6 dB under music unless it is the hit.
- Loudness: -14 LUFS (web/social), -16 (podcast-like), -23/-24 (broadcast).
