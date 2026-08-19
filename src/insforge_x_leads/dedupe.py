from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import LeadCandidate


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(item) for item in data.get("keys", [])}


def save_seen(path: Path, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"keys": sorted(seen)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lead_keys(lead: LeadCandidate) -> set[str]:
    normalized = " ".join(lead.post_text.lower().split())
    digest = hashlib.sha256(f"{lead.author_handle.lower()}:{normalized}".encode("utf-8")).hexdigest()
    return {
        f"url:{lead.post_url}",
        f"id:{lead.post_id}",
        f"author_text:{digest}",
    }


def dedupe_leads(leads: list[LeadCandidate], seen: set[str]) -> tuple[list[LeadCandidate], list[dict[str, str]]]:
    fresh: list[LeadCandidate] = []
    duplicates: list[dict[str, str]] = []
    batch_seen = set(seen)
    for lead in leads:
        keys = lead_keys(lead)
        if keys & batch_seen:
            duplicates.append({"post_id": lead.post_id, "post_url": lead.post_url, "reason": "duplicate"})
            continue
        fresh.append(lead)
        batch_seen.update(keys)
    return fresh, duplicates

