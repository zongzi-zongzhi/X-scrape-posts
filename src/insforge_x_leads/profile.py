from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BLOCKED_PHRASES = {
    "airdrop",
    "giveaway",
    "retweet to win",
    "follow me",
    "dm for promo",
}


def tokenize_phrases(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9][a-z0-9+#.-]*", lowered)
    phrases: list[str] = []
    phrases.extend(words)
    phrases.extend(" ".join(words[i : i + 2]) for i in range(max(len(words) - 1, 0)))
    phrases.extend(" ".join(words[i : i + 3]) for i in range(max(len(words) - 2, 0)))
    return phrases


def load_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": 1,
            "generated_at": None,
            "blocked_handles": [],
            "blocked_domains": ["t.me", "discord.gg", "bit.ly"],
            "blocked_phrases": sorted(DEFAULT_BLOCKED_PHRASES),
        }
    return json.loads(path.read_text(encoding="utf-8"))


def build_profile(sample_paths: list[Path], min_phrase_count: int = 2) -> dict[str, Any]:
    phrase_counts: Counter[str] = Counter()
    blocked_handles: set[str] = set()
    for sample_path in sample_paths:
        if not sample_path.exists():
            continue
        for line in sample_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("label") != "no_reply":
                continue
            text = str(item.get("text", ""))
            phrase_counts.update(tokenize_phrases(text))
            handle = str(item.get("author_handle", "")).strip().lower().lstrip("@")
            if handle:
                blocked_handles.add(handle)
    phrases = {
        phrase
        for phrase, count in phrase_counts.items()
        if count >= min_phrase_count and len(phrase) >= 4
    }
    phrases.update(DEFAULT_BLOCKED_PHRASES)
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "blocked_handles": sorted(blocked_handles),
        "blocked_domains": ["t.me", "discord.gg", "bit.ly"],
        "blocked_phrases": sorted(phrases),
    }


def save_profile(path: Path, profile: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

