#!/usr/bin/env bash
# Installs vedit's tools (ffmpeg, Python deps, Playwright renderer, fonts, sfx) when a
# Claude Code session starts. Idempotent and fast once everything is in place.
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"
if ! scripts/setup.sh >/tmp/vedit-setup.log 2>&1; then
  echo "vedit setup failed; see /tmp/vedit-setup.log (run scripts/setup.sh manually)"
  exit 0
fi
echo "vedit ready: bin/vedit doctor | skill: .claude/skills/video-edit"
