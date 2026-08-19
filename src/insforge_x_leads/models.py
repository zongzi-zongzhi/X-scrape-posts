from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class XPost:
    post_id: str
    post_url: str
    author_handle: str
    author_name: str
    text: str
    created_at: str
    metrics: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LeadCandidate:
    source: str
    post_url: str
    post_id: str
    author_handle: str
    author_name: str
    post_text: str
    created_at: str
    matched_keywords: list[str]
    score: int
    reason: str
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_master_row(self, human_only_fields: list[str] | None = None) -> dict[str, Any]:
        row: dict[str, Any] = {
            "source": self.source,
            "post_url": self.post_url,
            "post_id": self.post_id,
            "author_handle": self.author_handle,
            "author_name": self.author_name,
            "post_text": self.post_text,
            "created_at": self.created_at,
            "matched_keywords": ", ".join(self.matched_keywords),
            "score": self.score,
            "reason": self.reason,
        }
        for field_name in human_only_fields or []:
            row[field_name] = ""
        return row

