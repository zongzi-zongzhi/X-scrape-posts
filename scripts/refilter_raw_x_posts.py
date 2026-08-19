from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

from insforge_x_leads.config import load_config, resolve_path
from insforge_x_leads.dedupe import dedupe_leads, lead_keys, load_seen, save_seen
from insforge_x_leads.filtering import filter_posts
from insforge_x_leads.models import XPost
from insforge_x_leads.outputs import make_run_dir, update_pointer, write_json, write_leads_json, write_leads_markdown, write_raw_jsonl
from insforge_x_leads.profile import load_profile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def row_to_post(row: dict[str, Any]) -> XPost:
    return XPost(
        post_id=str(row.get("post_id", "")),
        post_url=str(row.get("post_url", "")),
        author_handle=str(row.get("author_handle", "")),
        author_name=str(row.get("author_name", "")),
        text=str(row.get("text", "")),
        created_at=str(row.get("created_at", "")),
        metrics=dict(row.get("metrics", {})) if isinstance(row.get("metrics"), dict) else {},
        raw=dict(row.get("raw", {})) if isinstance(row.get("raw"), dict) else {},
    )


def load_raw(path: Path) -> list[XPost]:
    posts: list[XPost] = []
    buffer = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() and not buffer:
            continue
        if line.startswith('{"post_id"') and buffer:
            try:
                posts.append(row_to_post(json.loads(buffer)))
            except json.JSONDecodeError:
                pass
            buffer = line
        else:
            buffer = line if not buffer else buffer + "\n" + line
        try:
            posts.append(row_to_post(json.loads(buffer)))
            buffer = ""
        except json.JSONDecodeError:
            continue
    if buffer:
        try:
            posts.append(row_to_post(json.loads(buffer)))
        except json.JSONDecodeError:
            pass
    return posts


def main() -> int:
    parser = argparse.ArgumentParser(description="Refilter saved raw X posts with an updated config.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--commit-local-state", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    raw_path = Path(args.raw)
    if not raw_path.is_absolute():
        raw_path = ROOT / raw_path

    config = load_config(config_path)
    limit = min(int(config["run"].get("max_new_leads_per_run", 50)), 50)
    posts = load_raw(raw_path)
    profile_path = resolve_path(ROOT, config["no_reply_profile"]["path"])
    no_reply_profile = load_profile(profile_path)
    candidates, rejected = filter_posts(posts, config.get("filters", {}), no_reply_profile)

    seen_path = resolve_path(ROOT, config["dedupe"]["state_path"])
    seen = load_seen(seen_path)
    fresh, duplicates = dedupe_leads(candidates, seen)
    fresh = fresh[:limit]

    if args.commit_local_state:
        updated_seen = set(seen)
        for lead in fresh:
            updated_seen.update(lead_keys(lead))
        save_seen(seen_path, updated_seen)

    outputs_root = resolve_path(ROOT, config["outputs"]["root"])
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
        "mode": "refilter",
        "provider": "saved_raw",
        "source_raw": str(raw_path),
        "queries": sorted({str(post.raw.get("query", "")) for post in posts if post.raw.get("query")}),
        "raw_count": len(posts),
        "candidate_count": len(candidates),
        "fresh_count": len(fresh),
        "rejected": rejected,
        "duplicates": duplicates,
        "state_updated": bool(args.commit_local_state),
        "constraints": {
            "read_only": True,
            "max_new_leads_per_run": limit,
            "no_real_interactions": True,
            "human_only_fields_left_blank": human_only_fields,
        },
    }
    write_json(files["log_json"], log)
    pointer_path = resolve_path(ROOT, config["outputs"]["pointer_path"])
    update_pointer(pointer_path, run_dir, "refilter", files, ["Refiltered from saved raw X posts; no X request performed."])
    result = {"run_dir": str(run_dir), "files": {k: str(v) for k, v in files.items()}, "log": log}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
