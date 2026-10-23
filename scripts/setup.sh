#!/usr/bin/env bash
# Installs everything vedit needs. Safe to re-run: finished steps are skipped.
#   scripts/setup.sh                 core install
#   scripts/setup.sh --with-whisper  also install faster-whisper (speech-to-text)
#   scripts/setup.sh --force         redo every step
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP_DIR="$ROOT/.setup"
WITH_WHISPER="${VEDIT_INSTALL_WHISPER:-0}"
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --with-whisper) WITH_WHISPER=1 ;;
    --force) FORCE=1 ;;
  esac
done
mkdir -p "$STAMP_DIR"

log() { printf '\033[1;36m[vedit setup]\033[0m %s\n' "$*"; }
done_step() { [[ $FORCE -eq 0 && -f "$STAMP_DIR/$1" ]]; }
mark() { touch "$STAMP_DIR/$1"; }

as_root() { if [[ $(id -u) -eq 0 ]]; then "$@"; elif command -v sudo >/dev/null; then sudo "$@"; else return 1; fi; }

# 1. ffmpeg -------------------------------------------------------------------
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  log "installing ffmpeg"
  if command -v apt-get >/dev/null; then
    as_root apt-get update -qq && as_root apt-get install -y -qq ffmpeg fontconfig
  elif command -v brew >/dev/null; then
    brew install ffmpeg
  elif command -v dnf >/dev/null; then
    as_root dnf install -y ffmpeg
  else
    echo "Please install ffmpeg (>= 5.1, with libass, libfreetype and libx264) and re-run." >&2
    exit 1
  fi
fi

# 2. Python dependencies ------------------------------------------------------
pip_install() {
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    python3 -m pip install -q "$@"
  else
    python3 -m pip install -q "$@" 2>/dev/null \
      || python3 -m pip install -q --break-system-packages "$@" 2>/dev/null \
      || python3 -m pip install -q --user "$@"
  fi
}
if ! done_step python-deps; then
  log "installing python dependencies"
  pip_install -r "$ROOT/requirements.txt"
  mark python-deps
fi
if [[ "$WITH_WHISPER" == "1" ]] && ! done_step whisper; then
  log "installing faster-whisper"
  pip_install -r "$ROOT/requirements-optional.txt" && mark whisper
fi

# 3. Node: HyperFrames (designed scenes, overlays, transitions) + fonts -----
# HyperFrames needs Node >= 22 and renders with its own headless Chrome.
if command -v npm >/dev/null && [[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 22 ]]; then
  if ! done_step node-deps || [[ ! -x "$ROOT/mograph/node_modules/.bin/hyperframes" ]]; then
    log "installing HyperFrames, gsap/lottie/three and fonts"
    (cd "$ROOT/mograph" && npm install --silent --no-audit --no-fund)
    mark node-deps
  fi
  if ! done_step hf-browser; then
    log "fetching the HyperFrames render browser"
    "$ROOT/bin/hyperframes" telemetry disable >/dev/null 2>&1 || true
    "$ROOT/bin/hyperframes" browser ensure && mark hf-browser || log "browser download failed: HyperFrames disabled"
  fi
else
  log "Node.js >= 22 not found: HyperFrames scenes/graphics and extra fonts are disabled"
fi

# 4. Fonts: convert fontsource woff2 -> ttf so libass (ffmpeg) and Chromium share them
if ! done_step fonts || ! ls "$ROOT"/assets/fonts/*.ttf >/dev/null 2>&1; then
  log "installing fonts"
  python3 "$ROOT/scripts/install_fonts.py" && mark fonts || log "font install skipped"
fi

# 5. Sound design assets (procedurally generated whooshes, impacts, risers) ---
if ! done_step sfx || ! ls "$ROOT"/assets/sfx/*.wav >/dev/null 2>&1; then
  log "generating sound effects"
  (cd "$ROOT" && python3 -m vedit synth-sfx --out assets/sfx >/dev/null) && mark sfx
fi

log "ready. Run: bin/vedit doctor"
