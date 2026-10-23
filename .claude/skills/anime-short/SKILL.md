---
name: anime-short
description: Make anime-style short films with 3D characters driven by motion capture - sports moments, fights, training montages, hype edits, "episode" shorts for TikTok/YouTube Shorts/Reels - with cel-shaded characters, cinematic shot lists, slow motion, ink impact frames (sakuga drawings with fisheye and flash), speed lines, anime opening/ending title cards, a song cut to the picture, anime sound design (power charges, cannon hits, time-freeze rings), a 9:16 version and proper credits. Use whenever the user wants an anime video, an anime fight/sports/action scene, impact frames, an "anime opening", or a 3D character animated from mocap.
---

# Anime shorts (3D characters + mocap → anime episode)

You are director, layout artist, animator, colourist and sound designer. The film is an **edit spec** (`edit.json`)
whose clips are three HTML scenes from this skill's kit, rendered by the vedit toolkit (`bin/vedit`, see the
`video-edit` and `motion-design` skills):

| scene | what |
|---|---|
| `anime_shot.html` | the action: a VRM / Mixamo character driven by BVH or GLB mocap, cut into a **shot list** (cameras around the character, slow motion and speed ramps, impact frames, speed lines, smears, memory grades) |
| `anime_pages.html` | `page: "op"`: the title card (kanji stamped on the beat over ink key art); `page: "ed"`: the end card (manga panel, vertical motto, つづく, credits strip) |

Sound and delivery are JSON plans run by the skill's tools: `sound.json` (sfx.py), `music.json` (music_fit.py),
`vertical.json` (vertical.py). Everything is a param, so the same kit makes a boxing short, a volleyball spike, a
sprint finish or a sword draw.

Skill folder: `.claude/skills/anime-short/` (`$S` below). Toolkit: `bin/vedit doctor` must pass; otherwise run
`scripts/setup.sh`. Without the toolkit at all (skill shared on its own): `git clone https://github.com/Ledsav/video-editing`
and work inside it.

## The rules that make it good (learned the hard way)

1. **Screenshots before renders, always.** Every change → `shot_stills.py` → Read the sheet → show the user. A full
   render takes minutes to an hour; render only when the user says so ("render"), never on your own initiative.
2. **Think before changing.** When something looks wrong, find the cause (look at the raw mocap, the calibration, the
   camera reference) before touching params. Change one thing, look again. Don't stack guesses.
3. **Check every licence before it goes in the film**, and credit it on the end card and the vertical credits
   ([references/assets-and-licensing.md](references/assets-and-licensing.md)). CC BY-NC material (Bandai Namco
   mocap, free-plan AI music) **blocks selling**: say so the moment the user mentions selling or monetising.
4. **Never commit footage, renders, characters, mocap, fonts or music.** Projects live in `projects/<name>/` (gitignored).

## Workflow

### 1. Pitch → episode structure (say it to the user in 4-6 lines)
Anime shorts work as a tiny episode: **OP title card (3-4 s) → setup (the stakes; a memory in grey) → rising
(close-ups: eyes, hands, breath) → the moment (the impact frame) → aftermath (the roar, the result) → ED card (3-4 s)**.
15-35 s total for TikTok. Name the moment that gets the impact frame; everything builds to it.

### 2. Scaffold and cast
```bash
$S/tools/new_project.sh <name> [--character HairSample_Female] [--cmu 13_17,02_05]
$S/tools/cmu_index.sh "box|kick|jump"            # find takes (CMU: free incl. commercial)
$S/tools/fetch_assets.sh projects/<name> --cmu 10_01 --character Vita
python3 $S/tools/vrm_meta.py projects/<name>/assets/characters/*.vrm   # the character's own licence terms
```
The project gets the kit (copied: re-run `new_project.sh` to refresh it), starter `edit.json` / `sound.json` /
`music.json` / `vertical.json` (a complete 13 s demo: a boxer's punch), a CC0 VRoid character, CMU takes and the page fonts.

### 3. Scout the mocap (find the frames that matter)
```bash
python3 $S/tools/shot_stills.py projects/<name> <clip id> --mocap assets/mocap/cmu/13_17.bvh --from 0 --to 30 --every 2.5
python3 $S/tools/shot_stills.py projects/<name> <clip id> --mocap ... --from 21.2 --to 22.4 --every 0.1 --orbit 70
```
The log lists each take's **strikes** (arm/leg snapping to full extension: punches, kicks, spikes), takeoff,
landing and contact times. Pick the moment, its run-up and its aftermath in take time.

### 4. Write the shot list
Shot list syntax, cameras, impacts and every param: [references/shot-spec.md](references/shot-spec.md).
Shot grammar that reads as anime:
- **Close-up before the action** (eyes / fist / feet), slow (¼-½ speed), push in. Use `cam.target: "Head"`.
- **The wind-up** wide or side-on, speed lines rising, `speed: [0.2, 0.6]`.
- **The moment**: `impact` on the strike (`"at": {"clip": t}` or `"contact"`), `hold` 0.6-1.0 s, 3-4 drawings
  (`step` 0.25), `angles: true` (each drawing from a new angle), target the striking hand/foot/ball.
- **The release**: the action resumes with a smear, zoom blur and shake (automatic), then a wide shot at speed.
- **Aftermath** slow, low angle, the face (`face: {"angry": 0.8, "a": 1}` = the shout).
- Cut on action; 0.6-2.5 s per shot; never more than ~3 s without a new angle.

### 5. Look at it
```bash
python3 $S/tools/shot_stills.py projects/<name> fight                 # 6 stills across the clip
python3 $S/tools/shot_stills.py projects/<name> fight 2.9,3.1,3.35,3.6 --size 1920x1080
```
Read the sheet and judge it like an animation director: pose readable? limbs natural (no broken wrists, hands through
the body, elbows backwards)? face visible in close-ups? the impact centred on the hit? Then show the user.
Checklist and the fixes that worked: [references/look.md](references/look.md) and [references/pitfalls.md](references/pitfalls.md).

### 6. Pages (key art from the film itself)
Render key art without overlays: `shot_stills.py ... <t> --size 1920x1080 --set art=1`, copy the stills to
`assets/art/op_key.png` (an impact drawing), `op_key_neg.png` (the next, negative drawing), `ed_panel.png` (a face
close-up). Set the title (kanji per stamp), romaji, English, episode, motto, credits in the page params; set `bpm` and
`down` from the song so the stamps land on its beats. Stills of the pages: `shot_stills.py projects/<name> op`.

### 7. Sound and music ([references/sound-and-music.md](references/sound-and-music.md))
- The song: the user's own or one made with Suno/Udio (prompt template in the reference; Japanese lyrics, timed to the
  edit). `music.json` aligns its drop to the impact, **dips it -10 dB under the action (never stop it)**, cuts the title
  card's bars, and can clean the AI sheen off the vocal (`"clean": true`).
- `sound.json`: cues referenced to the picture (`"fight:impact0"`, `"fight:shot2+0.3"`), so they follow re-timing.
  The hit = **charge → 50 ms of silence → cannon** (+ punch), a ring under the hold, a taiko per new drawing.
- `python3 $S/tools/sfx.py projects/<name>/sound.json && python3 $S/tools/music_fit.py projects/<name>/music.json`
  (times come from `work/anime_times/<clip>.json`, written by shot_stills: run it after every re-timing).

### 8. Render (only when the user says so) and deliver
```bash
bin/vedit validate projects/<name>/edit.json && bin/vedit render projects/<name>/edit.json --preview   # half-res check
bin/vedit render projects/<name>/edit.json                                                              # the master
python3 $S/tools/vertical.py projects/<name>/vertical.json                                              # 9:16 for TikTok
```
Look at frames of the output (`bin/vedit frames out/x.mp4 --times ...`) before calling it done. Masters: -14 LUFS.

## Sharing this skill
The skill is `.claude/skills/anime-short/` of the public repo github.com/Ledsav/video-editing: anyone who clones the
repo (or copies the folder into their own `.claude/skills/` next to the toolkit) gets it. `$S/tools/package.sh` zips the
folder for upload; it needs the toolkit to run (step 0 above).
