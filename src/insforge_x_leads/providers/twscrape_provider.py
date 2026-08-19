from __future__ import annotations

import asyncio
import importlib
import os
from pathlib import Path
from typing import Any

from ..models import XPost
from .base import ReadOnlyProvider


class TwscrapeReadOnlyProvider(ReadOnlyProvider):
    name = "twscrape"

    def __init__(self, accounts_db: Path | None = None, config: dict[str, Any] | None = None) -> None:
        db_value = str(accounts_db or os.environ.get("TWSCRAPE_ACCOUNTS_DB", "")).strip()
        if not db_value:
            raise RuntimeError("TWSCRAPE_ACCOUNTS_DB is required for live twscrape use")
        self.accounts_db = Path(db_value)
        self.proxy = str(os.environ.get("TWSCRAPE_PROXY") or os.environ.get("SCWEET_PROXY") or "").strip() or None
        x_config = (config or {}).get("x", {})
        self.since = str(os.environ.get("X_SEARCH_SINCE") or x_config.get("since", "")).strip()
        self.until = str(os.environ.get("X_SEARCH_UNTIL") or x_config.get("until", "")).strip()
        self.lang = str(os.environ.get("X_SEARCH_LANG") or x_config.get("lang", "")).strip()

    def search_public_posts(self, queries: list[str], limit: int) -> list[XPost]:
        return asyncio.run(self._search_public_posts(queries, limit))

    async def _search_public_posts(self, queries: list[str], limit: int) -> list[XPost]:
        module = importlib.import_module("twscrape")
        api = module.API(str(self.accounts_db), proxy=self.proxy)
        posts: list[XPost] = []
        per_query_limit = max(1, limit // max(len(queries), 1))
        for query in queries:
            async for tweet in api.search(self._query_with_window(query), limit=per_query_limit):
                posts.append(_tweet_to_post(tweet))
                if len(posts) >= limit:
                    return posts
        return posts

    def _query_with_window(self, query: str) -> str:
        parts = [query]
        if self.since and "since:" not in query:
            parts.append(f"since:{self.since}")
        if self.until and "until:" not in query:
            parts.append(f"until:{self.until}")
        if self.lang and "lang:" not in query:
            parts.append(f"lang:{self.lang}")
        return " ".join(parts)


def _tweet_to_post(tweet: Any) -> XPost:
    user = getattr(tweet, "user", None)
    tweet_id = str(getattr(tweet, "id", ""))
    username = str(getattr(user, "username", "") or getattr(tweet, "username", ""))
    return XPost(
        post_id=tweet_id,
        post_url=f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else "",
        author_handle=username,
        author_name=str(getattr(user, "displayname", "") or getattr(user, "rawDescription", "")),
        text=str(getattr(tweet, "rawContent", "") or getattr(tweet, "text", "")),
        created_at=str(getattr(tweet, "date", "")),
        metrics={
            "reply_count": getattr(tweet, "replyCount", 0),
            "retweet_count": getattr(tweet, "retweetCount", 0),
            "like_count": getattr(tweet, "likeCount", 0),
        },
        raw={"provider": "twscrape", "id": tweet_id},
    )
