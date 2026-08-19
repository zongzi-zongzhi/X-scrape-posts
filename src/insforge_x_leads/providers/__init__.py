from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import ReadOnlyProvider
from .fixture import FixtureProvider


def build_provider(config: dict[str, Any], root: Path, live: bool) -> ReadOnlyProvider:
    provider_name = str(config.get("run", {}).get("provider", "fixture")).lower()
    if provider_name == "fixture":
        fixture_path = root / str(config.get("run", {}).get("fixture_path", "fixtures/sample_posts.json"))
        return FixtureProvider(fixture_path)
    if not live:
        raise RuntimeError(f"provider={provider_name} requires --live; dry-run only uses fixture data")
    if provider_name in {"x_api", "official", "x-official"}:
        from .x_api_provider import XApiReadOnlyProvider

        return XApiReadOnlyProvider()
    if provider_name == "twscrape":
        from .twscrape_provider import TwscrapeReadOnlyProvider

        return TwscrapeReadOnlyProvider(config=config)
    if provider_name == "scweet":
        from .scweet_provider import ScweetReadOnlyProvider

        return ScweetReadOnlyProvider(config=config)
    if provider_name == "twikit":
        from .twikit_provider import TwikitReadOnlyProvider

        return TwikitReadOnlyProvider()
    raise RuntimeError(f"unknown provider: {provider_name}")
