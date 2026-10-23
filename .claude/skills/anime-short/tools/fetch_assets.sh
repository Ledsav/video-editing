#!/usr/bin/env bash
# Fetch free assets into an anime-short project (all from GitHub; nothing here is committed).
#   fetch_assets.sh <project> [--character NAME] [--cmu 02_05,13_17,...] [--bandai FILE,...] [--fonts]
#
#   --character  a VRoid sample from github.com/madjin/vrm-samples (vroid/beta), CC0 per the model's own metadata:
#                HairSample_Male (default), HairSample_Female, Sendagaya_Shibu, Sendagaya_Shino, Sakurada_Fumiriya,
#                Darkness_Shibu, Victoria_Rubin, Vita, Vivi. Repeat the flag for several.
#   --cmu        CMU motion capture takes (cgspeed BVH conversion, mirror github.com/una-dinosauria/cmu-mocap):
#                free for research and commercial use. Ids from the index (tools/cmu_index.sh SEARCH).
#   --bandai     Bandai Namco Research Motiondataset takes (CC BY-NC 4.0: NON-COMMERCIAL ONLY, credit required),
#                e.g. dataset-2_raise-up-both-hands_masculine_002.bvh
#   --fonts      Dela Gothic One + Yuji Boku (SIL OFL) for the anime pages (fetched by default with a new project)
set -euo pipefail
[[ $# -ge 1 ]] || { sed -n '2,14p' "$0"; exit 2; }
PROJ="$1"; shift
CHARS=(); CMU=""; BANDAI=""; FONTS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --character) CHARS+=("$2"); shift 2 ;;
    --cmu) CMU="$2"; shift 2 ;;
    --bandai) BANDAI="$2"; shift 2 ;;
    --fonts) FONTS=1; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
A="$PROJ/assets"; mkdir -p "$A/characters" "$A/mocap/cmu" "$A/mocap/bandai" "$A/fonts" "$A/art" "$A/props"
log() { printf '\033[1;35m[anime-short]\033[0m %s\n' "$*"; }
get() {   # url dest: retried download
  local url="$1" dst="$2" i
  [[ -s "$dst" ]] && return 0
  for i in 1 2 3 4; do curl -fsSL --retry 2 -o "$dst.part" "$url" && mv "$dst.part" "$dst" && return 0; sleep $((2 ** i)); done
  echo "download failed: $url" >&2; rm -f "$dst.part"; return 1
}

for c in "${CHARS[@]}"; do
  log "character $c (VRoid sample, CC0)"
  get "https://raw.githubusercontent.com/madjin/vrm-samples/master/vroid/beta/$c.vrm" "$A/characters/$c.vrm"
done

if [[ -n "$CMU" ]]; then
  IFS=',' read -ra IDS <<< "$CMU"
  for id in "${IDS[@]}"; do
    subj="${id%%_*}"; subj=$(printf '%03d' "$((10#$subj))")
    log "CMU take $id"
    get "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data/$subj/$id.bvh" "$A/mocap/cmu/$id.bvh"
  done
fi

if [[ -n "$BANDAI" ]]; then
  log "Bandai Namco Research Motiondataset: CC BY-NC 4.0, NON-COMMERCIAL ONLY (credit: Bandai Namco Research Inc.)"
  IFS=',' read -ra FS <<< "$BANDAI"
  for f in "${FS[@]}"; do
    case "$f" in dataset-1_*) ds="Bandai-Namco-Research-Motiondataset-1" ;; *) ds="Bandai-Namco-Research-Motiondataset-2" ;; esac
    get "https://raw.githubusercontent.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset/master/dataset/$ds/data/$f" "$A/mocap/bandai/$f" \
      || get "https://media.githubusercontent.com/media/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset/master/dataset/$ds/data/$f" "$A/mocap/bandai/$f"
  done
fi

if [[ $FONTS -eq 1 ]]; then
  log "fonts: Dela Gothic One, Yuji Boku (SIL Open Font License)"
  get https://raw.githubusercontent.com/google/fonts/main/ofl/delagothicone/DelaGothicOne-Regular.ttf "$A/fonts/DelaGothicOne-Regular.ttf"
  get https://raw.githubusercontent.com/google/fonts/main/ofl/yujiboku/YujiBoku-Regular.ttf "$A/fonts/YujiBoku-Regular.ttf"
  get https://raw.githubusercontent.com/google/fonts/main/ofl/delagothicone/OFL.txt "$A/fonts/OFL-DelaGothicOne.txt" || true
  get https://raw.githubusercontent.com/google/fonts/main/ofl/yujiboku/OFL.txt "$A/fonts/OFL-YujiBoku.txt" || true
fi
log "assets in $A"
