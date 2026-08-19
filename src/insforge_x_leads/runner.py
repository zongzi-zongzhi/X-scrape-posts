from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_config, project_root_from, require_read_only, resolve_path
from .dedupe import dedupe_leads, lead_keys, load_seen, save_seen
from .filtering import filter_posts_with_relaxed_pool
from .outputs import make_run_dir, update_pointer, write_json, write_leads_json, write_leads_markdown, write_raw_jsonl
from .profile import load_profile
from .providers import build_provider


def _parse_post_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%a %b %d %H:%M:%S %z %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _filter_posts_by_window(posts: list[Any], since: str, until: str) -> list[Any]:
    if not since and not until:
        return posts
    since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc) if since else None
    until_dt = datetime.fromisoformat(until).replace(tzinfo=timezone.utc) if until else None
    filtered = []
    for post in posts:
        created = _parse_post_datetime(getattr(post, "created_at", ""))
        if created is None:
            filtered.append(post)
            continue
        created_utc = created.astimezone(timezone.utc)
        if since_dt and created_utc < since_dt:
            continue
        if until_dt and created_utc >= until_dt:
            continue
        filtered.append(post)
    return filtered


def run_daily_crawl(
    config_path: Path,
    *,
    live: bool = False,
    commit_local_state: bool = False,
) -> dict[str, Any]:
    config = load_config(config_path)
    require_read_only(config)
    root = project_root_from(config_path)
    limit = min(int(config["run"].get("max_new_leads_per_run", 50)), 50)
    target_min = max(int(config["run"].get("min_new_leads_per_run", 0) or 0), 0)
    env_target_min = os.environ.get("X_LEADS_DAILY_MIN", "").strip()
    if env_target_min:
        target_min = max(int(env_target_min), 0)
    raw_fetch_limit = max(limit, int(config["run"].get("raw_fetch_limit", limit)))
    env_provider = os.environ.get("X_PROVIDER")
    if env_provider:
        config["run"]["provider"] = env_provider
    config.setdefault("x", {})
    for env_name, config_key in {
        "X_SEARCH_SINCE": "since",
        "X_SEARCH_UNTIL": "until",
        "X_SEARCH_LANG": "lang",
    }.items():
        env_value = os.environ.get(env_name)
        if env_value:
            config["x"][config_key] = env_value
    if not live and str(config["run"].get("provider", "fixture")).lower() != "fixture":
        config["run"]["provider"] = "fixture"
    provider = build_provider(config, root, live=live)
    queries = [str(item) for item in config.get("x", {}).get("queries", [])]
    posts = provider.search_public_posts(queries, limit=raw_fetch_limit)
    posts = _filter_posts_by_window(posts, str(config.get("x", {}).get("since", "")), str(config.get("x", {}).get("until", "")))

    profile_path = resolve_path(root, config["no_reply_profile"]["path"])
    no_reply_profile = load_profile(profile_path)
    candidates, relaxed_candidates, rejected = filter_posts_with_relaxed_pool(posts, config.get("filters", {}), no_reply_profile)

    seen_path = resolve_path(root, config["dedupe"]["state_path"])
    seen = load_seen(seen_path)
    fresh, duplicates = dedupe_leads(candidates, seen)
    relaxed_fresh: list[Any] = []
    relaxed_duplicates: list[dict[str, str]] = []
    relaxed_fill_count = 0
    if target_min and len(fresh) < target_min and relaxed_candidates:
        accepted_seen = set(seen)
        for lead in fresh:
            accepted_seen.update(lead_keys(lead))
        relaxed_fresh, relaxed_duplicates = dedupe_leads(relaxed_candidates, accepted_seen)
        fill_count = max(target_min - len(fresh), 0)
        selected_relaxed_fresh = relaxed_fresh[:fill_count]
        relaxed_fill_count = len(selected_relaxed_fresh)
        fresh.extend(selected_relaxed_fresh)
    fresh = fresh[:limit]

    if commit_local_state and live:
        updated_seen = set(seen)
        for lead in fresh:
            updated_seen.update(lead_keys(lead))
        save_seen(seen_path, updated_seen)

    outputs_root = resolve_path(root, config["outputs"]["root"])
    run_dir = make_run_dir(outputs_root)
    files = {
        "raw_jsonl": run_dir / "raw_posts.jsonl",
        "leads_json": run_dir / "leads.json",
        "leads_markdown": run_dir / "leads.md",
        "log_json": run_dir / "run_log.json",
    }
    human_only_fields = [str(item) for item in config.get("lark", {}).get("human_only_fields", [])]
    write_raw_jsonl(files["raw_jsonl"], posts)
    write_leads_json(files["leads_json"], fresh, human_only_fields)
    write_leads_markdown(files["leads_markdown"], fresh)
    log = {
        "mode": "live" if live else "dry-run",
        "provider": provider.name,
        "queries": queries,
        "raw_count": len(posts),
        "candidate_count": len(candidates),
        "relaxed_candidate_count": len(relaxed_candidates),
        "relaxed_fill_count": relaxed_fill_count,
        "fresh_count": len(fresh),
        "rejected": rejected,
        "duplicates": [*duplicates, *relaxed_duplicates],
        "state_updated": bool(commit_local_state and live),
        "constraints": {
            "read_only": True,
            "max_new_leads_per_run": limit,
            "target_min_new_leads_per_run": target_min,
            "no_real_interactions": True,
            "human_only_fields_left_blank": human_only_fields,
        },
    }
    write_json(files["log_json"], log)
    notes = ["No external write performed." if not live else "Live read-only X collection completed."]
    if not live:
        notes.append("Dry-run used fixture data unless config provider is fixture.")
    pointer_path = resolve_path(root, config["outputs"]["pointer_path"])
    update_pointer(pointer_path, run_dir, log["mode"], files, notes)
    return {"run_dir": str(run_dir), "files": {k: str(v) for k, v in files.items()}, "log": log}
