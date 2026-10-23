# Assets, licences, credits, selling

Check each asset's own licence before it goes in; write the credit as you add it (end card `credit` + `vertical.json`
`credits`). Attribution in the TASL form: **T**itle, **A**uthor, **S**ource, **L**icence (+ changes made).
Licences change: re-check the source page before selling anything.

## Characters
| source | licence | notes |
|---|---|---|
| VRoid samples via `fetch_assets.sh --character`: HairSample_Male/Female, Sendagaya_Shibu/Shino, Sakurada_Fumiriya, Darkness_Shibu, Victoria_Rubin, Vita, Vivi (github.com/madjin/vrm-samples, `vroid/beta`) | CC0 per each model's metadata (commercial and violent use allowed) | credit pixiv/VRoid anyway; `vrm_meta.py` prints the terms |
| VRoid AvatarSample_A/B/C | VRoid's own terms ("Other") | read the terms before commercial use |
| VRoid Hub models | per model (the VRM metadata + the Hub page) | many forbid violence or commercial use |
| your own VRoid Studio character | yours (VRoid Studio's guidelines allow commercial use of models you make; check the current guidelines) | |
| Mixamo characters | Adobe Mixamo terms (royalty-free in projects; can't redistribute the raw files) | needs an Adobe login: the user downloads them |

Ready-made outfits are VRoid's; recolour with `materials`. Brand logos and real products (a ball model, a jersey
brand) are trademarks: fine for practice, risky for a product you sell.

## Motion capture
| source | licence | notes |
|---|---|---|
| CMU Graphics Lab Motion Capture Database (BVH conversion by B. Hahne, mirror github.com/una-dinosauria/cmu-mocap) | free for research and commercial use (the data itself may not be resold) | 2,500+ takes: boxing, kicks, jumps, sports, dance; first frame is a T-pose (handled). Credit: "Motion capture data from mocap.cs.cmu.edu (created with funding from NSF EIA-0196217)" |
| Bandai Namco Research Motiondataset (github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset) | **CC BY-NC 4.0: non-commercial only** | stylised actions with emotions (dataset-2: "raise up both hands" cheers...). Blocks selling: replace before monetising |
| Mixamo animations | Adobe terms (royalty-free in projects) | FBX: convert to GLB (Blender) |
| bought packs (e.g. Motion Cast on CGTrader/ArtStation) | the store's licence (usually royalty-free use, no redistribution) | `.c4d` files: `tools/c4d_anim.py in.c4d out.glb` converts the joint animation to GLB |
| your own capture (phone apps, Rokoko, Move.ai) | yours | export BVH or FBX → GLB |

## Fonts, music
- Page fonts Dela Gothic One, Yuji Boku: SIL Open Font License (commercial use OK; credit appreciated).
- Songs made with Suno/Udio: the **plan at creation time** decides ownership; free-plan songs are non-commercial.
- Your own recordings (screams, shouts): yours. Synthesised sound design from `sfx.py`: yours.

## Selling and posting checklist
1. Every asset's licence allows commercial use (no CC BY-NC mocap, no free-plan AI songs, no trademarks you can't use).
2. The credits are on the end card and in the vertical version's credits card (TikTok captions crop credits).
3. TikTok/Shorts: 9:16 1080x1920 (`vertical.py`, or a true 9:16 render: the scenes use vw/vh), ≤ 60 s, title and
   credits inside the safe zone (not the top 150 px, bottom 380 px, right 140 px); disclose AI-generated content where
   the platform asks (Suno music counts).
4. Keep the project folder (and the asset sources in a note): renders can be rebuilt; licences must be provable.
