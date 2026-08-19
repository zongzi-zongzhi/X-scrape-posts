from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)


DEFAULT_BASE_TOKEN = ""
DEFAULT_TABLE_ID = "tbld7aGIobbJNv2t"
DEFAULT_VIEW_ID = "vewSzt8Zus"
REQUIRED_FIELDS = ["发布时间", "帖子名字", "帖子链接", "状态", "评论", "匹配关键词", "后续帖主回复", "回复情况", "二次评论", "其他"]
WRITABLE_AUTO_FIELDS = ["发布时间", "帖子名字", "帖子链接", "匹配关键词"]
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
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [lark_cli_path(), *args],
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


def record_fields(record: Any) -> dict[str, Any]:
    if isinstance(record, dict):
        fields = record.get("fields")
        if isinstance(fields, dict):
            return fields
        return record
    return {}


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


def post_id_from_url(url: str) -> str:
    match = re.search(r"/status/([^/?#]+)", url)
    return match.group(1) if match else ""


def compact_title(row: dict[str, Any]) -> str:
    handle = str(row.get("author_handle", "")).strip()
    text = str(row.get("post_text", "")).strip().replace("\n", " ")
    prefix = f"@{handle} | " if handle else ""
    value = f"{prefix}{text}"
    return value[:300]


def lead_to_lark_values(row: dict[str, Any]) -> list[Any]:
    return [
        str(row.get("created_at", "")),
        compact_title(row),
        str(row.get("post_url", "")),
        str(row.get("matched_keywords", "")),
    ]


def build_no_reply_profile(no_reply_records: list[dict[str, Any]]) -> dict[str, Any]:
    samples = []
    for record in no_reply_records:
        fields = record_fields(record)
        samples.append(
            {
                "post_url": normalize_cell(fields.get("帖子链接")),
                "post_id": post_id_from_url(normalize_cell(fields.get("帖子链接"))),
                "title": normalize_cell(fields.get("帖子名字")),
                "matched_keywords": normalize_cell(fields.get("匹配关键词")),
            }
        )
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "feishu_cli_master_table",
        "status": NO_REPLY_STATUS,
        "sample_count": len(samples),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and optionally append to the fixed Feishu/Lark X master table via lark-cli.")
    parser.add_argument("--input", help="Path to leads.json. Defaults to latest pointer.")
    parser.add_argument("--base-token", default=os.environ.get("LARK_BASE_APP_TOKEN", DEFAULT_BASE_TOKEN))
    parser.add_argument("--table-id", default=os.environ.get("LARK_TABLE_ID", DEFAULT_TABLE_ID))
    parser.add_argument("--view-id", default=os.environ.get("LARK_VIEW_ID", DEFAULT_VIEW_ID))
    parser.add_argument("--append", action="store_true", help="Actually append fresh rows. Omit for dry-run.")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    if not args.base_token:
        raise RuntimeError("Missing Lark base token. Pass --base-token or set LARK_BASE_APP_TOKEN.")

    limit = min(max(args.limit, 0), 50)
    fields_result = run_cli(["base", "+field-list", "--base-token", args.base_token, "--table-id", args.table_id, "--limit", "100", "--format", "json"])
    field_names = [str(field.get("name", "")) for field in fields_result.get("data", {}).get("fields", [])]
    missing_fields = [field for field in REQUIRED_FIELDS if field not in field_names]

    records_result = run_cli(["base", "+record-list", "--base-token", args.base_token, "--table-id", args.table_id, "--limit", "200", "--format", "json"])
    records = list(records_result.get("data", {}).get("data", []))
    existing_urls = {normalize_cell(record_fields(record).get("帖子链接")) for record in records}
    existing_urls.discard("")
    existing_post_ids = {post_id_from_url(url) for url in existing_urls if post_id_from_url(url)}

    no_reply_records = [
        record for record in records if normalize_cell(record_fields(record).get("状态")) == NO_REPLY_STATUS
    ]
    no_reply_profile = build_no_reply_profile(no_reply_records)

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

    run_dir = ROOT / "outputs" / f"lark-sync-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    write_payload = {
        "fields": WRITABLE_AUTO_FIELDS,
        "rows": [lead_to_lark_values(row) for row in fresh_rows],
    }
    (run_dir / "fields.json").write_text(json.dumps(fields_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "records.json").write_text(json.dumps(records_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "no_reply_profile_from_master.json").write_text(json.dumps(no_reply_profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "append_payload.json").write_text(json.dumps(write_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    append_result: dict[str, Any] | None = None
    blocked_reason = ""
    if missing_fields:
        blocked_reason = "master table missing required fields"
    elif args.append and fresh_rows:
        append_result = run_cli(
            [
                "base",
                "+record-batch-create",
                "--base-token",
                args.base_token,
                "--table-id",
                args.table_id,
                "--json",
                json.dumps(write_payload, ensure_ascii=False),
                "--format",
                "json",
            ]
        )

    report = {
        "mode": "append" if args.append else "dry-run",
        "base_token": args.base_token,
        "table_id": args.table_id,
        "view_id": args.view_id,
        "input": str(leads_path),
        "field_count": len(field_names),
        "missing_fields": missing_fields,
        "existing_record_count": len(records),
        "existing_url_count": len(existing_urls),
        "existing_post_id_count": len(existing_post_ids),
        "no_reply_sample_count": len(no_reply_records),
        "input_count": len(lead_rows),
        "fresh_count": len(fresh_rows),
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
        "append_count": len(fresh_rows) if args.append and append_result else 0,
        "blocked_reason": blocked_reason,
        "append_result": append_result,
        "files": {
            "run_dir": str(run_dir),
            "fields": str(run_dir / "fields.json"),
            "records": str(run_dir / "records.json"),
            "no_reply_profile": str(run_dir / "no_reply_profile_from_master.json"),
            "append_payload": str(run_dir / "append_payload.json"),
            "report": str(run_dir / "sync_report.json"),
        },
        "constraints": {
            "max_append": limit,
            "human_fields_not_written": ["状态", "评论", "后续帖主回复", "回复情况", "二次评论", "其他"],
            "writable_auto_fields": WRITABLE_AUTO_FIELDS,
        },
    }
    (run_dir / "sync_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if missing_fields else 0


if __name__ == "__main__":
    raise SystemExit(main())
