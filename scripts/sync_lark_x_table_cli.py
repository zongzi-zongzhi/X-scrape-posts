from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_BASE_TOKEN = ""
REQUIRED_FIELDS = ["发布时间", "帖子名字", "帖子链接", "状态", "评论", "匹配关键词", "后续帖主回复", "回复情况", "二次评论", "其他"]
WRITABLE_AUTO_FIELDS = ["发布时间", "帖子名字", "帖子链接", "匹配关键词"]
HUMAN_ONLY_FIELDS = ["状态", "评论", "后续帖主回复", "回复情况", "二次评论", "其他"]
NO_REPLY_STATUS = "不需要回"


def lark_cli_path() -> str:
    configured = os.environ.get("LARK_CLI_PATH")
    if configured:
        return configured
    found = shutil.which("lark-cli")
    if found:
        return found
    default = Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "@larksuite" / "cli" / "bin" / "lark-cli.exe"
    if default.exists():
        return str(default)
    raise RuntimeError("lark-cli not found; install @larksuite/cli or set LARK_CLI_PATH")


def run_cli(args: list[str]) -> dict[str, Any]:
    profile = os.environ.get("LARK_CLI_PROFILE", "").strip()
    command = [lark_cli_path()]
    if profile:
        command.extend(["--profile", profile])
    command.extend(args)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout.strip() or completed.stderr.strip())
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"lark-cli returned non-JSON output: {completed.stdout[:500]}") from exc


def load_latest_rows(input_path: str | None) -> tuple[Path, list[dict[str, Any]]]:
    if input_path:
        path = Path(input_path)
        if not path.is_absolute():
            path = ROOT / path
    else:
        pointer = json.loads((ROOT / "outputs" / "x_insforge_master_pointer.json").read_text(encoding="utf-8"))
        path = Path(pointer["latest_leads_json"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("leads JSON must contain a rows array")
    return path, [dict(row) for row in rows]


def normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(normalize_cell(item) for item in value)
    if isinstance(value, dict):
        for key in ("text", "name", "value"):
            if key in value:
                return normalize_cell(value[key])
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def record_fields(record: Any, field_names: list[str]) -> dict[str, Any]:
    if isinstance(record, dict):
        fields = record.get("fields")
        if isinstance(fields, dict):
            return fields
        return record
    if isinstance(record, list):
        return {name: record[index] if index < len(record) else "" for index, name in enumerate(field_names)}
    return {}


def post_id_from_url(url: str) -> str:
    match = re.search(r"/status/([^/?#]+)", url)
    return match.group(1) if match else ""


def normalize_url_cell(value: Any) -> str:
    text = normalize_cell(value).strip()
    markdown_match = re.match(r"^\[[^\]]+\]\((https?://[^)]+)\)$", text)
    if markdown_match:
        return markdown_match.group(1).strip()
    return text


def compact_title(row: dict[str, Any]) -> str:
    handle = str(row.get("author_handle", "")).strip().lstrip("@")
    text = str(row.get("post_text", "")).strip().replace("\n", " ")
    prefix = f"@{handle} | " if handle else ""
    return f"{prefix}{text}"[:300]


def format_publish_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            local = parsed.astimezone(timezone(timedelta(hours=8)))
            return f"{local.year}.{local.month}.{local.day}"
        except ValueError:
            pass
    match = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if match:
        return f"{int(match.group(1))}.{int(match.group(2))}.{int(match.group(3))}"
    return text


def lead_to_lark_values(row: dict[str, Any]) -> list[Any]:
    return [
        format_publish_date(row.get("created_at", "")),
        compact_title(row),
        str(row.get("post_url", "")),
        str(row.get("matched_keywords", "")),
    ]


def build_no_reply_profile(records: list[Any], record_field_names: list[str]) -> dict[str, Any]:
    samples = []
    for record in records:
        fields = record_fields(record, record_field_names)
        if normalize_cell(fields.get("状态")) != NO_REPLY_STATUS:
            continue
        url = normalize_url_cell(fields.get("帖子链接"))
        samples.append(
            {
                "post_url": url,
                "post_id": post_id_from_url(url),
                "title": normalize_cell(fields.get("帖子名字")),
                "matched_keywords": normalize_cell(fields.get("匹配关键词")),
            }
        )
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "feishu_cli_x_table",
        "status": NO_REPLY_STATUS,
        "sample_count": len(samples),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and optionally append X leads to one Feishu/Lark table.")
    parser.add_argument("--input", required=True, help="Path to leads.json.")
    parser.add_argument("--base-token", default=os.environ.get("LARK_BASE_APP_TOKEN", DEFAULT_BASE_TOKEN))
    parser.add_argument("--table-id", required=True)
    parser.add_argument("--append", action="store_true", help="Actually append fresh rows. Omit for dry-run.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--min-count",
        type=int,
        default=0,
        help="Target fresh row count for reporting. Shortfalls are reported but do not block append.",
    )
    parser.add_argument("--label", default="x")
    args = parser.parse_args()

    if not args.base_token:
        raise RuntimeError("Missing Lark base token. Pass --base-token or set LARK_BASE_APP_TOKEN.")

    limit = min(max(args.limit, 0), 50)
    min_count = max(args.min_count, 0)
    fields_result = run_cli(["base", "+field-list", "--base-token", args.base_token, "--table-id", args.table_id, "--limit", "100", "--format", "json"])
    field_names = [str(field.get("name", "")) for field in fields_result.get("data", {}).get("fields", [])]
    missing_fields = [field for field in REQUIRED_FIELDS if field not in field_names]

    records_result = run_cli(["base", "+record-list", "--base-token", args.base_token, "--table-id", args.table_id, "--limit", "500", "--format", "json"])
    record_field_names = [str(name) for name in records_result.get("data", {}).get("fields", field_names)]
    records = list(records_result.get("data", {}).get("data", []))
    existing_urls = {normalize_url_cell(record_fields(record, record_field_names).get("帖子链接")) for record in records}
    existing_urls.discard("")
    existing_post_ids = {post_id_from_url(url) for url in existing_urls if post_id_from_url(url)}
    no_reply_profile = build_no_reply_profile(records, record_field_names)

    leads_path, lead_rows = load_latest_rows(args.input)
    fresh_rows = []
    duplicates = []
    for row in lead_rows:
        url = str(row.get("post_url", ""))
        post_id = str(row.get("post_id", "")) or post_id_from_url(url)
        if url in existing_urls or (post_id and post_id in existing_post_ids):
            duplicates.append({"post_url": url, "post_id": post_id})
            continue
        fresh_rows.append(row)
    fresh_rows = fresh_rows[:limit]

    run_dir = ROOT / "outputs" / f"lark-sync-{args.label}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    append_payload = {
        "fields": WRITABLE_AUTO_FIELDS,
        "rows": [lead_to_lark_values(row) for row in fresh_rows],
    }
    (run_dir / "fields.json").write_text(json.dumps(fields_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "records.json").write_text(json.dumps(records_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "no_reply_profile_from_table.json").write_text(json.dumps(no_reply_profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "append_payload.json").write_text(json.dumps(append_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    append_result: dict[str, Any] | None = None
    blocked_reason = ""
    quantity_shortfall = ""
    if missing_fields:
        blocked_reason = "target table missing required fields"
    if not blocked_reason and min_count and len(fresh_rows) < min_count:
        quantity_shortfall = f"fresh_count below target minimum: {len(fresh_rows)} < {min_count}"
    if not blocked_reason and args.append and fresh_rows:
        append_result = run_cli(
            [
                "base",
                "+record-batch-create",
                "--base-token",
                args.base_token,
                "--table-id",
                args.table_id,
                "--json",
                json.dumps(append_payload, ensure_ascii=False),
                "--format",
                "json",
            ]
        )

    report = {
        "mode": "append" if args.append else "dry-run",
        "label": args.label,
        "base_token": args.base_token,
        "table_id": args.table_id,
        "input": str(leads_path),
        "field_count": len(field_names),
        "missing_fields": missing_fields,
        "existing_record_count": len(records),
        "existing_url_count": len(existing_urls),
        "existing_post_id_count": len(existing_post_ids),
        "no_reply_sample_count": no_reply_profile["sample_count"],
        "input_count": len(lead_rows),
        "fresh_count": len(fresh_rows),
        "duplicate_count": len(duplicates),
        "append_count": len(fresh_rows) if args.append and append_result else 0,
        "blocked_reason": blocked_reason,
        "quantity_shortfall": quantity_shortfall,
        "append_result": append_result,
        "files": {
            "run_dir": str(run_dir),
            "fields": str(run_dir / "fields.json"),
            "records": str(run_dir / "records.json"),
            "no_reply_profile": str(run_dir / "no_reply_profile_from_table.json"),
            "append_payload": str(run_dir / "append_payload.json"),
            "report": str(run_dir / "sync_report.json"),
        },
        "constraints": {
            "max_append": limit,
            "min_append": min_count,
            "human_fields_not_written": HUMAN_ONLY_FIELDS,
            "writable_auto_fields": WRITABLE_AUTO_FIELDS,
        },
    }
    (run_dir / "sync_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if missing_fields else 0


if __name__ == "__main__":
    raise SystemExit(main())
