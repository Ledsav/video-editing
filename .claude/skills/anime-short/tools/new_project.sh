#!/usr/bin/env bash
# Scaffold an anime short: projects/<name>/ with the kit (scenes + libraries), a starter edit.json / shots, sound and
# music plans, and free assets (a CC0 VRoid character, two CMU takes, the page fonts).
#   new_project.sh <name> [--character HairSample_Male] [--cmu 10_01,02_05] [--no-assets]
# Re-running it refreshes the kit files and keeps everything else.
set -euo pipefail
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# the vedit toolkit: $VEDIT_REPO, else the current directory, else the repo this skill sits in (.claude/skills/<skill>)
REPO="${VEDIT_REPO:-}"
[[ -z "$REPO" && -x "$PWD/bin/vedit" ]] && REPO="$PWD"
[[ -z "$REPO" ]] && REPO="$(cd "$SKILL/../../.." && pwd)"
[[ -x "$REPO/bin/vedit" ]] || { echo "vedit toolkit not found: run this inside a clone of github.com/Ledsav/video-editing (or set VEDIT_REPO)" >&2; exit 1; }
[[ $# -ge 1 ]] || { sed -n '2,6p' "$0"; exit 2; }
NAME="$1"; shift
CHAR="HairSample_Male"; CMU=""; ASSETS=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --character) CHAR="$2"; shift 2 ;;
    --cmu) CMU="$2"; shift 2 ;;
    --no-assets) ASSETS=0; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
P="$REPO/projects/$NAME"
"$REPO/bin/vedit" new "$NAME" >/dev/null
mkdir -p "$P/sfx" "$P/music" "$P/assets"
cp "$SKILL"/kit/anime.js "$SKILL"/kit/mocap.js "$SKILL"/kit/anime_shot.html "$SKILL"/kit/anime_pages.html "$P/"
for f in edit.json sound.json music.json vertical.json; do
  if [[ ! -s "$P/$f" ]] || { [[ $f == edit.json ]] && grep -q '"timeline": \[\]' "$P/$f"; }; then
    sed -e "s/HairSample_Male/$CHAR/g" "$SKILL/template/$f" > "$P/$f"
  fi
done
if [[ $ASSETS -eq 1 ]]; then
  "$SKILL/tools/fetch_assets.sh" "$P" --character "$CHAR" --cmu "13_17${CMU:+,$CMU}" --fonts   # 13_17: the starter edit's boxing take
fi
cat <<EOF
anime short ready: $P
  scenes:  anime_shot.html (shots), anime_pages.html (opening / ending pages)  -- params in edit.json
  sound:   sound.json (python3 $SKILL/tools/sfx.py $P/sound.json)
  music:   music.json (python3 $SKILL/tools/music_fit.py $P/music.json)
  stills:  python3 $SKILL/tools/shot_stills.py $P <clip id> [times]
EOF
