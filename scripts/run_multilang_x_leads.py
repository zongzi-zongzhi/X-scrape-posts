from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

from insforge_x_leads.config import load_config, resolve_path
from insforge_x_leads.dedupe import lead_keys, load_seen, save_seen
from insforge_x_leads.models import LeadCandidate
from insforge_x_leads.rules_doc import default_rules_doc_path, load_rules_doc

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SHANGHAI_TZ = timezone(timedelta(hours=8))
LANG_BUCKETS = {
    "en": {"label": "en", "config_path": "config/x_lead_crawl.en.json", "table_key": "english"},
    "ja": {"label": "ja", "config_path": "config/x_lead_crawl.ja.json", "table_key": "japanese"},
    "ko": {"label": "ko", "config_path": "config/x_lead_crawl.ko.json", "table_key": "korean"},
}


def month_window(today: date | None = None) -> tuple[str, str]:
    current = today or datetime.now(SHANGHAI_TZ).date()
    since = current - timedelta(days=30)
    until = current + timedelta(days=1)
    return since.isoformat(), until.isoformat()


def run_python(args: list[str], env: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout.strip() or completed.stderr.strip())
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"subprocess returned non-JSON output: {completed.stdout[:500]}") from exc


def row_to_lead(row: dict[str, Any]) -> LeadCandidate:
    return LeadCandidate(
        source=str(row.get("source", "x_public_post")),
        post_url=str(row.get("post_url", "")),
        post_id=str(row.get("post_id", "")),
        author_handle=str(row.get("author_handle", "")),
        author_name=str(row.get("author_name", "")),
        post_text=str(row.get("post_text", "")),
        created_at=str(row.get("created_at", "")),
        matched_keywords=[item for item in str(row.get("matched_keywords", "")).split(", ") if item],
        score=int(row.get("score", 0) or 0),
        reason=str(row.get("reason", "")),
        metrics={},
    )


def commit_seen_state(config_path: str, leads_json_path: str) -> int:
    config = load_config(ROOT / config_path)
    seen_path = resolve_path(ROOT, config["dedupe"]["state_path"])
    payload = json.loads(Path(leads_json_path).read_text(encoding="utf-8"))
    rows = [dict(row) for row in payload.get("rows", []) if isinstance(row, dict)]
    seen = load_seen(seen_path)
    before = len(seen)
    for row in rows:
        seen.update(lead_keys(row_to_lead(row)))
    save_seen(seen_path, seen)
    return len(seen) - before


def run_bucket(
    *,
    label: str,
    config_path: str,
    base_token: str,
    table_id: str,
    since: str,
    until: str,
    append: bool,
    commit_local_state: bool,
    daily_min: int,
    daily_max: int,
    lark_cli_profile: str,
) -> dict[str, Any]:
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "X_SEARCH_SINCE": since,
        "X_SEARCH_UNTIL": until,
        "X_LEADS_DAILY_MIN": str(daily_min),
    }
    if lark_cli_profile:
        env["LARK_CLI_PROFILE"] = lark_cli_profile
    crawl_result = run_python(["scripts/run_daily_x_crawl.py", "--config", config_path, "--live"], env)
    sync_args = [
        "scripts/sync_lark_x_table_cli.py",
        "--input",
        crawl_result["files"]["leads_json"],
        "--base-token",
        base_token,
        "--table-id",
        table_id,
        "--label",
        label,
        "--limit",
        str(daily_max),
        "--min-count",
        str(daily_min),
    ]
    dry_sync_result = run_python(sync_args, env)
    append_result = None
    if append and not dry_sync_result.get("blocked_reason") and int(dry_sync_result.get("fresh_count", 0)) > 0:
        append_result = run_python([*sync_args, "--append"], env)

    effective_sync = append_result or dry_sync_result
    state_committed_count = 0
    if commit_local_state and append and not dry_sync_result.get("blocked_reason"):
        if append_result or int(dry_sync_result.get("fresh_count", 0)) == 0:
            state_committed_count = commit_seen_state(config_path, crawl_result["files"]["leads_json"])

    return {
        "label": label,
        "table_id": table_id,
        "crawl": crawl_result,
        "sync_dry_run": dry_sync_result,
        "sync_append": append_result,
        "stats": {
            "raw_count": crawl_result["log"]["raw_count"],
            "candidate_count": crawl_result["log"]["candidate_count"],
            "fresh_count": crawl_result["log"]["fresh_count"],
            "rejected_count": len(crawl_result["log"]["rejected"]),
            "local_duplicate_count": len(crawl_result["log"]["duplicates"]),
            "feishu_duplicate_count": effective_sync.get("duplicate_count", 0),
            "append_count": effective_sync.get("append_count", 0),
            "blocked_reason": effective_sync.get("blocked_reason", ""),
            "state_committed_count": state_committed_count,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run English/Japanese/Korean X lead crawl and Feishu sync.")
    parser.add_argument("--append", action="store_true", help="Append to Feishu after dry-run validation.")
    parser.add_argument("--commit-local-state", action="store_true", help="Commit local dedupe state after successful Feishu validation.")
    parser.add_argument("--since", help="X search since date, YYYY-MM-DD. Defaults to 30 days ago in Asia/Shanghai.")
    parser.add_argument("--until", help="X search until date, YYYY-MM-DD. Defaults to tomorrow in Asia/Shanghai.")
    parser.add_argument("--langs", nargs="+", choices=sorted(LANG_BUCKETS), default=sorted(LANG_BUCKETS))
    parser.add_argument("--rules-doc", default=str(default_rules_doc_path()), help="Markdown rules document to read before execution.")
    args = parser.parse_args()

    rules = load_rules_doc(args.rules_doc)
    since, until = month_window()
    since = args.since or since
    until = args.until or until
    tables = rules["tables"]

    results = []
    for lang in args.langs:
        bucket = LANG_BUCKETS[lang]
        table_info = tables.get(bucket["table_key"], {})
        table_id = str(table_info.get("table_id", ""))
        if not table_id:
            raise RuntimeError(f"rules doc is missing {table_info.get('name', bucket['table_key'])} table id")
        results.append(
            run_bucket(
                label=bucket["label"],
                config_path=bucket["config_path"],
                base_token=rules["base_token"],
                table_id=table_id,
                since=since,
                until=until,
                append=args.append,
                commit_local_state=args.commit_local_state,
                daily_min=rules["daily_min_per_language"],
                daily_max=rules["daily_max_per_language"],
                lark_cli_profile=rules["lark_cli_profile"],
            )
        )

    run_dir = ROOT / "outputs" / f"multilang-{datetime.now(SHANGHAI_TZ).strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "mode": "append" if args.append else "dry-run",
        "window": {"since": since, "until": until, "timezone": "Asia/Shanghai"},
        "rules_doc": {
            "path": rules["path"],
            "updated_at": rules["updated_at"],
            "sha256": rules["sha256"],
            "lark_cli_profile": rules["lark_cli_profile"],
        },
        "read_only_x": rules["hard_rules"]["read_only_x"],
        "no_x_interactions": rules["hard_rules"]["no_x_interactions"],
        "daily_min_per_table": rules["daily_min_per_language"],
        "max_append_per_table": rules["daily_max_per_language"],
        "results": results,
        "files": {"run_dir": str(run_dir), "report": str(run_dir / "daily_report.json")},
    }
    (run_dir / "daily_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
