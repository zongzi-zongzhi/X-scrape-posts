from __future__ import annotations

import json
from pathlib import Path

from ..models import XPost
from .base import ReadOnlyProvider


class FixtureProvider(ReadOnlyProvider):
    name = "fixture"

    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def search_public_posts(self, queries: list[str], limit: int) -> list[XPost]:
        del queries
        data = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        posts = [
            XPost(
                post_id=str(item.get("post_id", "")),
                post_url=str(item.get("post_url", "")),
                author_handle=str(item.get("author_handle", "")),
                author_name=str(item.get("author_name", "")),
                text=str(item.get("text", "")),
                created_at=str(item.get("created_at", "")),
                metrics=dict(item.get("metrics", {})),
                raw=dict(item),
            )
            for item in data
        ]
        return posts[:limit]

