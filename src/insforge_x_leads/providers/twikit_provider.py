from __future__ import annotations

import importlib
import os
import asyncio
from pathlib import Path
from typing import Any

from ..models import XPost
from .base import ReadOnlyProvider


class TwikitReadOnlyProvider(ReadOnlyProvider):
    name = "twikit"

    def __init__(self, cookies_path: Path | None = None) -> None:
        cookie_value = str(cookies_path or os.environ.get("TWIKIT_COOKIES_PATH", "")).strip()
        if not cookie_value:
            raise RuntimeError("TWIKIT_COOKIES_PATH is required for live twikit use")
        self.cookies_path = Path(cookie_value)

    def search_public_posts(self, queries: list[str], limit: int) -> list[XPost]:
        return asyncio.run(self._search_public_posts(queries, limit))

    async def _search_public_posts(self, queries: list[str], limit: int) -> list[XPost]:
        module = importlib.import_module("twikit")
        client = module.Client("en-US")
        client.load_cookies(str(self.cookies_path))
        posts: list[XPost] = []
        per_query_limit = max(1, limit // max(len(queries), 1))
        for query in queries:
            result = await client.search_tweet(query, "Latest", count=per_query_limit)
            for tweet in result:
                posts.append(_tweet_to_post(tweet))
                if len(posts) >= limit:
                    return posts
        return posts


def _tweet_to_post(tweet: Any) -> XPost:
    user = getattr(tweet, "user", None)
    tweet_id = str(getattr(tweet, "id", ""))
    username = str(getattr(user, "screen_name", "") or getattr(user, "name", ""))
    return XPost(
        post_id=tweet_id,
        post_url=f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else "",
        author_handle=username,
        author_name=str(getattr(user, "name", "")),
        text=str(getattr(tweet, "text", "")),
        created_at=str(getattr(tweet, "created_at", "")),
        metrics={
            "reply_count": getattr(tweet, "reply_count", 0),
            "retweet_count": getattr(tweet, "retweet_count", 0),
            "like_count": getattr(tweet, "favorite_count", 0),
        },
        raw={"provider": "twikit", "id": tweet_id},
    )
