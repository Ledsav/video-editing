"""Speech-to-text with word timestamps (faster-whisper), so cuts can follow what is said."""
from __future__ import annotations

import json
from pathlib import Path

from .util import VeditError, log


def transcribe(path: str | Path, out: Path, *, model: str = "small", language: str | None = None) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise VeditError("faster-whisper is not installed. Run: scripts/setup.sh --with-whisper "
                         "(the model downloads from huggingface.co on first use)") from e
    log(f"transcribing {path} with whisper '{model}' (cpu)")
    try:
        wm = WhisperModel(model, device="auto", compute_type="int8")
    except Exception as e:  # network blocked, unknown model...
        raise VeditError(f"could not load whisper model {model!r}: {e}. If the network blocks "
                         "huggingface.co, download the model elsewhere and pass its directory as --model.") from e
    segments, info = wm.transcribe(str(path), language=language, word_timestamps=True, vad_filter=True)
    data = {"file": str(path), "language": info.language, "segments": []}
    for s in segments:
        data["segments"].append({
            "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
            "words": [{"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word.strip()}
                      for w in (s.words or [])],
        })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return data


def as_text(data: dict) -> str:
    """Readable transcript with timecodes, one line per segment."""
    lines = []
    for s in data.get("segments", []):
        lines.append(f"[{s['start']:7.2f} - {s['end']:7.2f}] {s['text']}")
    return "\n".join(lines)
