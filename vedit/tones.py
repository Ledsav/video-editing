"""Tone presets: named looks that a story arc can move between.

Each preset is a partial set of grade parameters (see grade.NEUTRAL for the full
list and ranges). `moods` lists the words a brief would use for that feeling, so the
editor can map "tense, isolating, cold" to a look without guessing.
"""
from __future__ import annotations

TONES: dict[str, dict] = {
    "neutral": {
        "description": "No look. Technical baseline.",
        "moods": ["neutral", "raw"],
        "params": {},
    },
    "natural": {
        "description": "Clean, true-to-life with a touch of contrast and vibrance.",
        "moods": ["honest", "everyday", "clean", "calm"],
        "params": {"contrast": 0.08, "vibrance": 0.12, "highlight_rolloff": 0.2},
    },
    "documentary": {
        "description": "Neutral, slightly crisp, restrained saturation. Lets the subject speak.",
        "moods": ["factual", "serious", "journalistic", "interview"],
        "params": {"contrast": 0.1, "saturation": 0.92, "sharpen": 0.2, "highlight_rolloff": 0.3},
    },
    "teal_orange": {
        "description": "Blockbuster complementary look: teal shadows, warm skin and highlights.",
        "moods": ["epic", "cinematic", "action", "heroic", "adventure", "bold"],
        "params": {"contrast": 0.28, "saturation": 1.05, "vibrance": 0.1,
                   "shadow_tint": {"color": "#008b8b", "amount": 0.2},
                   "highlight_tint": {"color": "#ff9a3c", "amount": 0.13},
                   "highlight_rolloff": 0.35, "vignette": 0.2},
    },
    "golden_hour": {
        "description": "Low warm sun: amber highlights, soft glow, gentle contrast.",
        "moods": ["hopeful", "warm", "uplifting", "nostalgic", "summer", "resolution", "love"],
        "params": {"temperature": 0.45, "tint": 0.05, "contrast": 0.12, "saturation": 1.08,
                   "highlight_tint": {"color": "#ffb347", "amount": 0.12},
                   "black_point": 0.02, "bloom": 0.25, "highlight_rolloff": 0.45},
    },
    "vintage_film": {
        "description": "Faded 70s/80s print: lifted blacks, creamy highlights, grain.",
        "moods": ["nostalgic", "memory", "retro", "flashback", "home-video", "bittersweet"],
        "params": {"temperature": 0.25, "saturation": 0.82, "contrast": 0.05,
                   "black_point": 0.07, "highlight_rolloff": 0.55,
                   "shadow_tint": {"color": "#4b3a6b", "amount": 0.1},
                   "highlight_tint": {"color": "#ffd9a0", "amount": 0.12},
                   "grain": 0.45, "vignette": 0.35},
    },
    "cold_thriller": {
        "description": "Steel-blue, desaturated and contrasty. Isolation and threat.",
        "moods": ["tense", "suspense", "thriller", "isolated", "cold", "conflict", "danger", "mystery"],
        "params": {"temperature": -0.4, "saturation": 0.72, "contrast": 0.32, "exposure": -0.15,
                   "shadow_tint": {"color": "#0b4a5e", "amount": 0.22},
                   "vignette": 0.4, "grain": 0.18, "highlight_rolloff": 0.3},
    },
    "noir": {
        "description": "High-contrast black and white with deep shadows.",
        "moods": ["noir", "crime", "timeless", "stark", "dramatic", "mystery"],
        "params": {"mono": 1.0, "contrast": 0.45, "black_point": -0.03, "vignette": 0.55,
                   "grain": 0.4, "highlight_rolloff": 0.3},
    },
    "sepia": {
        "description": "Warm monochrome, old photograph.",
        "moods": ["history", "archival", "old", "past", "memory"],
        "params": {"mono": 0.9, "contrast": 0.15, "black_point": 0.05,
                   "highlight_tint": {"color": "#e0a060", "amount": 0.35},
                   "shadow_tint": {"color": "#5a3a1a", "amount": 0.3},
                   "grain": 0.5, "vignette": 0.45, "highlight_rolloff": 0.5},
    },
    "bleach_bypass": {
        "description": "Silver-retention: gritty, metallic, low saturation, hard contrast.",
        "moods": ["gritty", "war", "brutal", "raw", "intense", "struggle", "sport"],
        "params": {"bleach": 0.7, "saturation": 0.75, "contrast": 0.3, "sharpen": 0.35,
                   "grain": 0.3, "vignette": 0.3},
    },
    "moody_desat": {
        "description": "Muted, cool-leaning, heavy. Melancholy without going full cold.",
        "moods": ["sad", "melancholy", "lonely", "grief", "reflective", "rain", "loss"],
        "params": {"saturation": 0.62, "contrast": 0.15, "exposure": -0.1, "temperature": -0.12,
                   "shadow_tint": {"color": "#1c3a5a", "amount": 0.15},
                   "black_point": 0.03, "vignette": 0.3, "highlight_rolloff": 0.4},
    },
    "low_key_dramatic": {
        "description": "Dark, deep blacks, punchy highlights. Weight and gravity.",
        "moods": ["dramatic", "powerful", "climax", "intense", "dark", "villain", "confrontation"],
        "params": {"exposure": -0.3, "contrast": 0.42, "saturation": 0.9, "black_point": -0.02,
                   "vignette": 0.5, "highlight_rolloff": 0.25},
    },
    "high_key_bright": {
        "description": "Airy and bright, clean whites. Optimism, lifestyle, corporate.",
        "moods": ["happy", "optimistic", "fresh", "corporate", "lifestyle", "light", "joy"],
        "params": {"exposure": 0.25, "contrast": -0.05, "saturation": 1.05, "vibrance": 0.15,
                   "black_point": 0.02, "highlight_rolloff": 0.45},
    },
    "dreamy_pastel": {
        "description": "Soft, hazy, pastel. Dreams, fantasy, tenderness.",
        "moods": ["dream", "fantasy", "tender", "innocent", "ethereal", "wonder"],
        "params": {"exposure": 0.15, "contrast": -0.2, "saturation": 0.85, "black_point": 0.08,
                   "highlight_tint": {"color": "#ffd6e8", "amount": 0.12},
                   "shadow_tint": {"color": "#a8b8ff", "amount": 0.1},
                   "bloom": 0.45, "highlight_rolloff": 0.6},
    },
    "romantic_soft": {
        "description": "Warm-pink skin, soft glow, gentle contrast.",
        "moods": ["romantic", "intimate", "wedding", "love", "gentle"],
        "params": {"temperature": 0.2, "tint": 0.12, "contrast": -0.06, "saturation": 0.95,
                   "highlight_tint": {"color": "#ffc4b0", "amount": 0.12},
                   "black_point": 0.03, "bloom": 0.35, "highlight_rolloff": 0.5},
    },
    "vibrant_pop": {
        "description": "Saturated, punchy, social-first. Energy and fun.",
        "moods": ["energetic", "fun", "playful", "hype", "party", "youth", "product"],
        "params": {"saturation": 1.35, "vibrance": 0.3, "contrast": 0.2, "exposure": 0.05,
                   "highlight_rolloff": 0.25},
    },
    "cyberpunk_neon": {
        "description": "Magenta/cyan neon, deep blue shadows, glow and lens fringing.",
        "moods": ["futuristic", "night", "neon", "tech", "electronic", "rebellion", "urban"],
        "params": {"temperature": -0.2, "tint": 0.3, "saturation": 1.3, "contrast": 0.3,
                   "shadow_tint": {"color": "#3a00ff", "amount": 0.2},
                   "highlight_tint": {"color": "#00e5ff", "amount": 0.1},
                   "bloom": 0.4, "chroma_shift": 0.4, "vignette": 0.3},
    },
    "horror_green": {
        "description": "Sickly green-cyan, underexposed, oppressive.",
        "moods": ["horror", "dread", "sick", "unsettling", "decay", "fear"],
        "params": {"tint": -0.35, "saturation": 0.7, "contrast": 0.35, "exposure": -0.25,
                   "shadow_tint": {"color": "#0f4a2a", "amount": 0.22},
                   "vignette": 0.55, "grain": 0.3},
    },
    "desert_heat": {
        "description": "Bleached orange-yellow heat, crushed contrast. Westerns, survival.",
        "moods": ["heat", "western", "survival", "harsh", "desert", "exhaustion"],
        "params": {"temperature": 0.55, "tint": -0.05, "saturation": 0.9, "contrast": 0.25,
                   "highlight_tint": {"color": "#ffcc66", "amount": 0.15},
                   "bleach": 0.2, "highlight_rolloff": 0.3, "grain": 0.2},
    },
}


def tone_names() -> list[str]:
    return list(TONES)


def find_tones_for_mood(word: str) -> list[str]:
    w = word.lower().strip()
    return [name for name, t in TONES.items() if any(w in m or m in w for m in t["moods"])]
