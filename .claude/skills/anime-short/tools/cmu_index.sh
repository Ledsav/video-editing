#!/usr/bin/env bash
# Search the CMU motion capture index (2,500+ takes; free for research and commercial use):
#   cmu_index.sh boxing        ->  13_17  boxing ...
#   cmu_index.sh "jump|kick"
# The index is downloaded once to ~/.cache/anime-short/cmu-index.txt. Fetch takes with fetch_assets.sh --cmu ID,ID.
set -euo pipefail
IDX="${XDG_CACHE_HOME:-$HOME/.cache}/anime-short/cmu-index.txt"
mkdir -p "$(dirname "$IDX")"
[[ -s "$IDX" ]] || curl -fsSL -o "$IDX" https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/cmu-mocap-index-text.txt
grep -E -i "${1:-.}" "$IDX" | grep -E '^[0-9]+_[0-9]+' || echo "no take matches '${1:-}'"
