from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_TOKEN = os.environ.get("LARK_BASE_APP_TOKEN", "").strip()
SIMPLIFIED_TABLE_ID = "tbld7aGIobbJNv2t"
SIMPLIFIED_TABLE_NAME = "X-简中"
TRADITIONAL_TABLE_NAME = "X-繁中"
FIELDS = [
    {"name": "帖子名字", "type": "text"},
    {"name": "发布时间", "type": "text"},
    {"name": "帖子链接", "type": "text"},
    {"name": "状态", "type": "select", "multiple": False, "options": [{"name": "已回"}, {"name": "不需要回"}]},
    {"name": "评论", "type": "text"},
    {"name": "匹配关键词", "type": "text"},
    {"name": "后续帖主回复", "type": "text"},
    {"name": "回复情况", "type": "text"},
    {"name": "二次评论", "type": "text"},
    {"name": "其他", "type": "text"}
]


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
    return json.loads(completed.stdout)


def main() -> int:
    if not BASE_TOKEN:
        raise RuntimeError("Missing LARK_BASE_APP_TOKEN.")

    tables_result = run_cli(["base", "+table-list", "--base-token", BASE_TOKEN, "--format", "json"])
    tables = tables_result.get("data", {}).get("items") or tables_result.get("data", {}).get("tables", [])
    name_to_id = {
        str(table.get("name", "")): str(table.get("table_id", "") or table.get("id", ""))
        for table in tables
    }

    rename_result = run_cli(
        [
            "base",
            "+table-update",
            "--base-token",
            BASE_TOKEN,
            "--table-id",
            SIMPLIFIED_TABLE_ID,
            "--name",
            SIMPLIFIED_TABLE_NAME,
            "--format",
            "json",
        ]
    )
    traditional_table_id = name_to_id.get(TRADITIONAL_TABLE_NAME, "")
    create_result = None
    if not traditional_table_id:
        create_result = run_cli(
            [
                "base",
                "+table-create",
                "--base-token",
                BASE_TOKEN,
                "--name",
                TRADITIONAL_TABLE_NAME,
                "--fields",
                json.dumps(FIELDS, ensure_ascii=False),
                "--format",
                "json",
            ]
        )
        traditional_table_id = str(
            create_result.get("data", {}).get("table_id", "")
            or create_result.get("data", {}).get("table", {}).get("id", "")
        )

    tables_config = {
        "base_token": BASE_TOKEN,
        "simplified": {"name": SIMPLIFIED_TABLE_NAME, "table_id": SIMPLIFIED_TABLE_ID},
        "traditional": {"name": TRADITIONAL_TABLE_NAME, "table_id": traditional_table_id},
    }
    (ROOT / "config" / "lark_x_tables.json").write_text(json.dumps(tables_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"rename_result": rename_result, "create_result": create_result, "tables": tables_config}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
