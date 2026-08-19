from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

from ..models import XPost
from .base import ReadOnlyProvider


class ScweetReadOnlyProvider(ReadOnlyProvider):
    name = "scweet"

    def __init__(
        self,
        cookies_file: Path | None = None,
        auth_token: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        cookies_value = str(cookies_file or os.environ.get("SCWEET_COOKIES_FILE", "")).strip()
        token_value = str(auth_token or os.environ.get("SCWEET_AUTH_TOKEN", "")).strip()
        db_path = str(os.environ.get("SCWEET_DB_PATH", "data/scweet_state.db")).strip()
        if not cookies_value and not token_value:
            raise RuntimeError("SCWEET_COOKIES_FILE or SCWEET_AUTH_TOKEN is required for live Scweet use")
        self.cookies_file = cookies_value or None
        self.auth_token = token_value or None
        self.db_path = db_path
        self.proxy = str(os.environ.get("SCWEET_PROXY", "")).strip() or None
        x_config = (config or {}).get("x", {})
        scweet_config = (config or {}).get("scweet", {})
        self.since = str(x_config.get("since", "")).strip() or None
        self.until = str(x_config.get("until", "")).strip() or None
        self.lang = str(x_config.get("lang", "")).strip() or None
        self.display_type = str(x_config.get("result_type", "Latest") or "Latest")
        self.scweet_config = dict(scweet_config) if isinstance(scweet_config, dict) else {}

    def search_public_posts(self, queries: list[str], limit: int) -> list[XPost]:
        module = importlib.import_module("Scweet.client")
        config_module = importlib.import_module("Scweet.config")
        scweet_runtime_config = config_module.ScweetConfig(
            daily_requests_limit=int(self.scweet_config.get("daily_requests_limit", 30)),
            daily_tweets_limit=int(self.scweet_config.get("daily_tweets_limit", 600)),
            concurrency=int(self.scweet_config.get("concurrency", 1)),
            n_splits=int(self.scweet_config.get("n_splits", 1)),
            requests_per_min=int(self.scweet_config.get("requests_per_min", 6)),
            min_delay_s=float(self.scweet_config.get("min_delay_s", 5.0)),
            max_empty_pages=int(self.scweet_config.get("max_empty_pages", 1)),
            api_page_size=int(self.scweet_config.get("api_page_size", 20)),
        )
        client = module.Scweet(
            cookies_file=self.cookies_file,
            auth_token=self.auth_token,
            db_path=self.db_path,
            proxy=self.proxy,
            provision=True,
            manifest_scrape_on_init=False,
            config=scweet_runtime_config,
        )
        posts: list[XPost] = []
        per_query_limit = max(1, limit // max(len(queries), 1))
        for query in queries:
            rows = client.search(
                query=query,
                display_type=self.display_type,
                since=self.since,
                until=self.until,
                lang=self.lang,
                limit=per_query_limit,
                save=False,
            )
            for row in rows:
                posts.append(_scweet_row_to_post(row, query=query))
                if len(posts) >= limit:
                    return posts
        return posts


def _scweet_row_to_post(row: dict[str, Any], query: str = "") -> XPost:
    user = row.get("user") if isinstance(row.get("user"), dict) else {}
    tweet_id = str(row.get("tweet_id", "") or row.get("id", ""))
    username = str(user.get("screen_name", "") or row.get("screen_name", ""))
    return XPost(
        post_id=tweet_id,
        post_url=str(row.get("tweet_url", "")) or (f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else ""),
        author_handle=username,
        author_name=str(user.get("name", "") or row.get("name", "")),
        text=str(row.get("text", "") or row.get("embedded_text", "")),
        created_at=str(row.get("timestamp", "")),
        metrics={
            "reply_count": row.get("comments", 0),
            "retweet_count": row.get("retweets", 0),
            "like_count": row.get("likes", 0),
        },
        raw={"provider": "scweet", "id": tweet_id, "query": query},
    )
