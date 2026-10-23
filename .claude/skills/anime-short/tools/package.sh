#!/usr/bin/env bash
# Zip the skill for sharing: anime-short.zip (the skill folder only: kit, tools, templates, references; no assets).
# The recipient needs the vedit toolkit to run it: github.com/Ledsav/video-editing (scripts/setup.sh), or unzip into
# that repo's .claude/skills/.   package.sh [out_dir]
set -euo pipefail
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$(cd "${1:-.}" && pwd)/anime-short.zip"
rm -f "$OUT"
( cd "$SKILL/.." && zip -qr "$OUT" anime-short -x '*/__pycache__/*' '*.pyc' )
echo "$OUT ($(du -h "$OUT" | cut -f1))"
