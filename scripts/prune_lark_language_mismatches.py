from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

from insforge_x_leads.filtering import language_rejection_reason

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_TOKEN = ""
TITLE_FIELD = "\u5e16\u5b50\u540d\u5b57"
URL_FIELD = "\u5e16\u5b50\u94fe\u63a5"


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


def row_fields(record: Any, field_names: list[str]) -> dict[str, Any]:
    if isinstance(record, list):
        return {name: record[index] if index < len(record) else "" for index, name in enumerate(field_names)}
    if isinstance(record, dict):
        fields = record.get("fields")
        return fields if isinstance(fields, dict) else record
    return {}


def prune_table(base_token: str, table_id: str, script: str, *, dry_run: bool) -> dict[str, Any]:
    records_result = run_cli(["base", "+record-list", "--base-token", base_token, "--table-id", table_id, "--limit", "500", "--format", "json"])
    data = records_result.get("data", {})
    field_names = [str(name) for name in data.get("fields", [])]
    record_ids = [str(record_id) for record_id in data.get("record_id_list", [])]
    records = list(data.get("data", []))
    delete_candidates = []
    for index, record in enumerate(records):
        fields = row_fields(record, field_names)
        title = normalize_cell(fields.get(TITLE_FIELD))
        url = normalize_cell(fields.get(URL_FIELD))
        reason = language_rejection_reason(
            title,
            {"script": script, "min_chinese_chars": 8, "min_script_markers": 1},
        )
        if "insforge" in title.lower():
            reason = "excluded keyword: insforge"
        if reason:
            delete_candidates.append(
                {
                    "record_id": record_ids[index],
                    "reason": reason,
                    "post_url": url,
                    "title_preview": title[:160],
                }
            )

    delete_result = None
    if delete_candidates and not dry_run:
        delete_result = run_cli(
            [
                "base",
                "+record-delete",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--json",
                json.dumps({"record_id_list": [item["record_id"] for item in delete_candidates]}, ensure_ascii=False),
                "--yes",
                "--format",
                "json",
            ]
        )
    return {
        "table_id": table_id,
        "script": script,
        "record_count": len(records),
        "delete_count": len(delete_candidates),
        "delete_candidates": delete_candidates,
        "delete_result": delete_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune Feishu X table records whose body language does not match the table.")
    parser.add_argument("--base-token", default=os.environ.get("LARK_BASE_APP_TOKEN", BASE_TOKEN))
    parser.add_argument("--simplified-table-id", default="tbld7aGIobbJNv2t")
    parser.add_argument("--traditional-table-id", default="tblgzlJjSEthFWmr")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.base_token:
        raise RuntimeError("Missing Lark base token. Pass --base-token or set LARK_BASE_APP_TOKEN.")
    reports = [
        prune_table(args.base_token, args.simplified_table_id, "simplified", dry_run=args.dry_run),
        prune_table(args.base_token, args.traditional_table_id, "traditional", dry_run=args.dry_run),
    ]
    run_dir = ROOT / "outputs" / f"lark-language-prune-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "mode": "dry-run" if args.dry_run else "delete",
        "reports": reports,
        "files": {"run_dir": str(run_dir), "report": str(run_dir / "language_prune_report.json")},
    }
    (run_dir / "language_prune_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
