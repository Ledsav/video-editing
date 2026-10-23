# Sound and music

Three stems, all in edit time (sample 0 = the first frame), mixed by `edit.json`'s `music` list at -14 LUFS:
`music/op.wav` (the title card's bars), `music/score.wav` (the song cut to the picture), `sfx/sfx.wav` (sound design),
plus optional `sfx/voice.wav` (a shout). Re-run `shot_stills.py` on the shot clip after any re-timing, then both tools:
the plans reference the picture (`"fight:impact0"`), so the sound follows.

## What reads as anime (lessons from user feedback)
- **The hit is a cannon, not a gunshot**: a power **charge** (rising whine, accelerating pulse, crackle, swelling rumble)
  that cuts to **50 ms of silence**, then the blast. The silence is what makes it land.
- **Bright and sharp, not sub-heavy.** A long dark rumble or pitch-falling boom under the hit reads as slow motion
  ("too opaque and low"): keep the low end to a short kick, put the weight in the crack and the mid punch.
- **The music never stops under the action**: dip it ~10 dB from the close-up before the hit to the release, and bring
  it back on the release (its loudest section can slam in on the aftermath).
- During an ink hold: a high ring (time freeze) and one short taiko per new drawing; no other music events.
- Title stamps: one `stamp` per kanji, on the song's beats (`down + k * 60 / bpm`).
- A shout/scream: a boy's voice from a grown man's recording: +4 semitones with formants shifted (`voice.pitch: 4`).
- Masters: peaks ≤ 0.9 in each stem (AAC/MP3 previews overshoot near full scale); `audio.loudness: -14`.

## sound.json cue types
`punch` (fist landing), `cannon` (blast + echoes + debris), `charge` (`end` = the hit; `dur`, `gap` 0.05),
`whoosh` (`dur`, `f0`, `f1`), `swish` (a fast limb), `ring` (time freeze, `dur`, `f`), `taiko` (`f`), `crash`,
`sub_drop`, `debris`, `rumble`, `vwoom` (slow-mo drop), `reverse_swell` / `riser` (`end` = the moment they lead into),
`sparkle` (kira), `heartbeat`, `footstep`, `stamp`, `file` (`path`). Every cue: `at` (or a list), `gain`, `pan`, `seed`.
`duck`: `[{"from", "to", "db", "release"}]` dips the whole stem (e.g. under a voice).

A typical impact:
```json
{"type": "charge", "end": "fight:impact0", "dur": 1.0, "gain": 0.8},
{"type": "swish", "at": "fight:impact0-0.12", "gain": 0.6},
{"type": "cannon", "at": "fight:impact0"},
{"type": "punch", "at": "fight:impact0", "gain": 0.7},
{"type": "ring", "at": "fight:impact0", "dur": 1.0, "gain": 0.35},
{"type": "taiko", "at": ["fight:impact0+0.25", "fight:impact0+0.5", "fight:impact0+0.75"], "gain": 0.3}
```

## music.json
Find the song's beats and sections first: `bin/vedit beats assets/audio/song.mp3` (tempo, beats, downbeats, energy
rises). Then:
- `align`: one piece, the song's `song` time (a drop or chorus downbeat) on the picture's `at` (the release of the hit).
- or `pieces`: explicit cuts, **downbeat to downbeat** (a jump of whole bars), with 10-30 ms fades. Typical: the song
  from its start, then a jump of N bars so its final chord lands on the end card.
- `start: "op:end"`: silent under the title card, which gets its own `stems` cut (2 bars of the chorus, its downbeat
  on the page's `down`).
- `dips`, `muffle` (a memory: low-passed and quieter), `clean`, `voice`: see the tool's docstring.

`clean: true` takes the AI sheen off a generated vocal with filters: the stereo side halved from 1.5 to 9 kHz (where
the phasey artefacts sit), de-essing, -2.5 dB at 320 Hz and 6.5 kHz, +2 dB at 2.8 kHz, -3 dB above 11 kHz, light
compression. It can't change an auto-tuned tone: for that, export the vocal stem (Suno Pro) and treat it alone.

## A song made with Suno (template)
Suno doesn't follow timestamps; ask for a tempo whose bars fit the picture and clearly separated sections, then cut
it with music_fit. At B bpm one bar = 240 / B s: choose B so the big moments fall on bar lines (e.g. 137 bpm: 1.75 s
bars). Newer Suno versions have a **duration slider** (a target, not exact): set the film length + 4 s and keep the
lyrics short; long lyrics in a short song get rushed.

Custom mode, Instrumental off. **Style:**
```
Japanese anime <sports|battle> opening, shonen J-rock orchestral hybrid, Japanese lyrics, powerful male J-rock vocalist,
gang shouts, <B> BPM, <key> minor resolving to major. <intro colour, e.g. lonely muffled piano intro>, taiko and heartbeat
build, explosive drop with distorted guitars, fast drums, string ostinato, brass stabs, huge choir, dramatic full stops
and silences, triumphant final chorus, emotional, high energy
```
**Exclude:** `lo-fi, EDM, dubstep, trap, English lyrics`. **Lyrics** (sections map to the film; short for ≤ 35 s):
```
[Intro: solo piano, soft sad male vocal]
<one line: the loss / the stakes>
[Build: taiko, heartbeat, rising]
<one line: now it's my turn>
[Drop: full band explodes, shouted]
<two-word shout: 跳べ！ 打ち抜け！>
[Break: instrumental, sudden full stop, only heartbeat]
[Chorus: choir, brass, triumphant, biggest moment]
<the title phrase + 何度でも> / 諦めない
[Outro: final big chord]
<English shout: ネバーギブアップ！>
[End]
```
Leave the Break and Impact without words (the charge, cannon and shout go there). If Suno mispronounces a word, write
it in hiragana. Make 4-6 versions; keep the ones with a clean stop before the impact and a strong chorus. Say that the
lyrics are machine-written: a native speaker should check them before publishing.

**Licensing:** songs from Suno's free plan are non-commercial; a paid plan at creation time is needed to sell or
monetise (see assets-and-licensing.md). Credit "Song made with Suno" either way.
