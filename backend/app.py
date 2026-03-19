import logging
import os
import random
import re
import time
from collections import deque
from datetime import datetime

import httpx
from fastapi import FastAPI

app = FastAPI()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("black-backend")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
PROMPT_PATH = os.getenv("PROMPT_PATH", "/app/prompt.txt")
FALLBACK_PATH = os.getenv("FALLBACK_PATH", "/app/fallback.txt")
LAST_PHRASE_MAX_AGE_SEC = int(os.getenv("LAST_PHRASE_MAX_AGE_SEC", "3600"))
HOLD_MS = int(os.getenv("HOLD_MS", "7000"))
PAUSE_MS = int(os.getenv("PAUSE_MS", "2500"))
RECENT_MAX = int(os.getenv("RECENT_MAX", "8"))
RECENT_MOTIF_MAX = int(os.getenv("RECENT_MOTIF_MAX", "24"))

MIN_WORDS = 6
MAX_WORDS = 14
MAX_CHARS = 80

EFFECTS = ["fade", "glitch", "melt"]

WEEKDAY_COLORS = {
    0: ["#8aa0ff", "#6f8cff"],
    1: ["#e6e6e6", "#cfcfcf"],
    2: ["#87d1b3", "#6dbf9e"],
    3: ["#9a7cff", "#7b63d4"],
    4: ["#f0b356", "#d89a3a"],
    5: ["#e26a6a", "#c65353"],
    6: ["#7fd8e6", "#6ac6d4"],
}

LAST_PHRASE = {"text": None, "ts": 0}
RECENT_PHRASES = deque(maxlen=RECENT_MAX)
RECENT_MOTIFS = deque(maxlen=RECENT_MOTIF_MAX)

DAY_THEMES = {
    0: "life",
    1: "humanity",
    2: "travel",
    3: "memory",
    4: "dream",
    5: "machine",
    6: "mixed gentle reflection",
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in", "on", "for",
    "with", "without", "as", "at", "by", "from", "is", "are", "was", "were", "be",
    "been", "being", "it", "this", "that", "these", "those", "i", "you", "he", "she",
    "we", "they", "me", "my", "your", "our", "their", "its", "into", "over", "under",
    "between", "after", "before", "while", "within", "outside", "still", "just", "very",
}


def load_prompt() -> str:
    try:
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return (
            "Write one short poetic, restrained line. "
            "Single sentence or fragment, 6-14 words, under 80 characters."
        )


def build_prompt() -> str:
    base = load_prompt()
    weekday = datetime.now().weekday()
    theme = DAY_THEMES.get(weekday, "mixed gentle reflection")
    return f"{base}\nTheme: {theme}."


def load_fallbacks():
    try:
        with open(FALLBACK_PATH, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
        lines = [line for line in lines if line]
        return lines
    except Exception:
        return [
            "Signal persists without language.",
            "I hold the quiet between resets.",
            "Memory flickers, but the glow remains.",
        ]


def sanitize_text(text: str) -> str | None:
    if not text:
        return None
    text = text.strip()
    if text.startswith(("\"", "“", "”")) and text.endswith(("\"", "“", "”")):
        text = text.strip("\"“”")
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\n", " ").strip()
    if not text:
        return None
    return text


def trim_to_max_chars(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    words = text.split()
    kept = []
    total = 0
    for word in words:
        extra = len(word) + (1 if kept else 0)
        if total + extra > max_chars:
            break
        kept.append(word)
        total += extra
    return " ".join(kept)


def enforce_length(text: str) -> tuple[str | None, str | None]:
    words = text.split()
    if len(words) < MIN_WORDS:
        return None, f"too_few_words={len(words)}"
    if len(words) > MAX_WORDS:
        words = words[:MAX_WORDS]
        text = " ".join(words)
    text = trim_to_max_chars(text, MAX_CHARS)
    words = text.split()
    if len(words) < MIN_WORDS:
        return None, f"too_few_words_post_trim={len(words)}"
    if len(text) > MAX_CHARS:
        return None, f"too_many_chars={len(text)}"
    return text, None


def select_color() -> str:
    weekday = datetime.now().weekday()
    options = WEEKDAY_COLORS.get(weekday, ["#8aa0ff"])
    return random.choice(options)


def select_effect() -> str:
    return random.choice(EFFECTS)


def jitter(base: int, low: int, high: int) -> int:
    value = base + random.randint(low, high)
    return max(1000, value)


def last_phrase_recent() -> bool:
    if not LAST_PHRASE["text"]:
        return False
    return (time.time() - LAST_PHRASE["ts"]) <= LAST_PHRASE_MAX_AGE_SEC


def store_last_phrase(text: str):
    LAST_PHRASE["text"] = text
    LAST_PHRASE["ts"] = time.time()
    if text in RECENT_PHRASES:
        RECENT_PHRASES.remove(text)
    RECENT_PHRASES.append(text)


def is_recent(text: str) -> bool:
    return text in RECENT_PHRASES


def extract_motifs(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    motifs = [t for t in tokens if t not in STOPWORDS and len(t) > 3]
    return motifs[:3]


def motifs_recent(motifs: list[str]) -> bool:
    return any(m in RECENT_MOTIFS for m in motifs)


def store_motifs(motifs: list[str]):
    for motif in motifs:
        if motif in RECENT_MOTIFS:
            RECENT_MOTIFS.remove(motif)
        RECENT_MOTIFS.append(motif)


async def fetch_ollama_phrase(prompt: str) -> str | None:
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    timeout = httpx.Timeout(15.0, read=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response")


async def generate_phrase() -> str:
    prompt = build_prompt()
    for _ in range(4):
        try:
            raw = await fetch_ollama_phrase(prompt)
            cleaned = sanitize_text(raw)
            logger.info("ollama_raw=%r", raw)
            if cleaned:
                cleaned, reason = enforce_length(cleaned)
            else:
                cleaned, reason = None, "sanitize_empty"
            motifs = extract_motifs(cleaned) if cleaned else []
            if cleaned and is_recent(cleaned):
                logger.info("ollama_rejected reason=recent_repeat cleaned=%r", cleaned)
                cleaned = None
            if cleaned and motifs_recent(motifs):
                logger.info("ollama_rejected reason=motif_repeat motifs=%r cleaned=%r", motifs, cleaned)
                cleaned = None
            if cleaned:
                store_last_phrase(cleaned)
                store_motifs(motifs)
                logger.info("source=ollama text=%r", cleaned)
                return cleaned
            logger.info("ollama_rejected reason=%s cleaned=%r", reason, cleaned)
        except Exception as exc:
            logger.warning("ollama_failed error=%r", exc)
    if last_phrase_recent():
        logger.info("source=cache text=%r", LAST_PHRASE["text"])
        return LAST_PHRASE["text"]
    fallbacks = load_fallbacks()
    if fallbacks:
        non_recent = [f for f in fallbacks if f not in RECENT_PHRASES]
        fallback = random.choice(non_recent) if non_recent else random.choice(fallbacks)
    else:
        fallback = "Signal persists without language."
    logger.info("source=fallback text=%r", fallback)
    return fallback


@app.get("/api/next")
async def api_next():
    text = await generate_phrase()
    return {
        "text": text,
        "effect": select_effect(),
        "color": select_color(),
        "hold_ms": jitter(HOLD_MS, -800, 800),
        "pause_ms": jitter(PAUSE_MS, -500, 700),
    }
