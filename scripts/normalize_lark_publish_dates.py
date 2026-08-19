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

BASE_TOKEN = ""
PUBLISH_FIELD = "\u53d1\u5e03\u65f6\u95f4"
SHANGHAI_TZ = timezone(timedelta(hours=8))


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
    raise RuntimeError("lark-cli not found")


def run_cli(args: list[str]) -> dict[str, Any]:
    command = [lark_cli_path()]
    profile = os.environ.get("LARK_CLI_PROFILE", "").strip()
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
    return json.loads(completed.stdout)


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


def format_publish_date(value: Any) -> str:
    text = normalize_cell(value).strip()
    if not text:
        return ""
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            local = parsed.astimezone(SHANGHAI_TZ)
            return f"{local.year}.{local.month}.{local.day}"
        except ValueError:
            pass
    match = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if match:
        return f"{int(match.group(1))}.{int(match.group(2))}.{int(match.group(3))}"
    return text


def row_fields(record: Any, field_names: list[str]) -> dict[str, Any]:
    if isinstance(record, list):
        return {name: record[index] if index < len(record) else "" for index, name in enumerate(field_names)}
    if isinstance(record, dict):
        fields = record.get("fields")
        return fields if isinstance(fields, dict) else record
    return {}


def normalize_table(base_token: str, table_id: str, *, dry_run: bool) -> dict[str, Any]:
    records_result = run_cli(["base", "+record-list", "--base-token", base_token, "--table-id", table_id, "--limit", "500", "--format", "json"])
    data = records_result.get("data", {})
    field_names = [str(name) for name in data.get("fields", [])]
    record_ids = [str(record_id) for record_id in data.get("record_id_list", [])]
    records = list(data.get("data", []))
    updates = []
    for index, record in enumerate(records):
        fields = row_fields(record, field_names)
        old_value = normalize_cell(fields.get(PUBLISH_FIELD))
        new_value = format_publish_date(old_value)
        if old_value and new_value and old_value != new_value:
            updates.append({"record_id": record_ids[index], "old": old_value, "new": new_value})

    update_results = []
    if not dry_run:
        for update in updates:
            result = run_cli(
                [
                    "base",
                    "+record-upsert",
                    "--base-token",
                    base_token,
                    "--table-id",
                    table_id,
                    "--record-id",
                    update["record_id"],
                    "--json",
                    json.dumps({PUBLISH_FIELD: update["new"]}, ensure_ascii=False),
                    "--format",
                    "json",
                ]
            )
            update_results.append({"record_id": update["record_id"], "result": result.get("ok", False)})

    return {
        "table_id": table_id,
        "record_count": len(records),
        "update_count": len(updates),
        "updates": updates,
        "update_results": update_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize Feishu X table publish dates to YYYY.M.D.")
    parser.add_argument("--base-token", default=os.environ.get("LARK_BASE_APP_TOKEN", BASE_TOKEN))
    parser.add_argument("--table-id", action="append", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.base_token:
        raise RuntimeError("Missing Lark base token. Pass --base-token or set LARK_BASE_APP_TOKEN.")

    reports = [normalize_table(args.base_token, table_id, dry_run=args.dry_run) for table_id in args.table_id]
    run_dir = ROOT / "outputs" / f"lark-date-normalize-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "mode": "dry-run" if args.dry_run else "update",
        "base_token": args.base_token,
        "reports": reports,
        "files": {"run_dir": str(run_dir), "report": str(run_dir / "date_normalize_report.json")},
    }
    (run_dir / "date_normalize_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
