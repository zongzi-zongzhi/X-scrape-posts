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
TABLES_PATH = ROOT / "config" / "lark_x_tables.json"
FIELD_TEMPLATE = [
    {"name": "帖子名字", "type": "text"},
    {"name": "发布时间", "type": "text"},
    {"name": "帖子链接", "type": "text"},
    {"name": "状态", "type": "select", "multiple": False, "options": [{"name": "已回"}, {"name": "不需要回"}]},
    {"name": "评论", "type": "text"},
    {"name": "匹配关键词", "type": "text"},
    {"name": "后续帖主回复", "type": "text"},
    {"name": "回复情况", "type": "text"},
    {"name": "二次评论", "type": "text"},
    {"name": "其他", "type": "text"},
]
TARGETS = {
    "english": {"name": "X-英语", "config_key": "english"},
    "japanese": {"name": "X-日语", "config_key": "japanese"},
    "korean": {"name": "X-韩语", "config_key": "korean"},
}


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


def table_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    data = result.get("data", {})
    items = data.get("items") or data.get("tables") or data.get("data") or []
    return [item for item in items if isinstance(item, dict)]


def table_id_from_create(result: dict[str, Any]) -> str:
    data = result.get("data", {})
    return str(
        data.get("table_id")
        or data.get("id")
        or data.get("table", {}).get("table_id")
        or data.get("table", {}).get("id")
        or ""
    )


def load_tables_config() -> dict[str, Any]:
    if TABLES_PATH.exists():
        return json.loads(TABLES_PATH.read_text(encoding="utf-8"))
    return {"base_token": BASE_TOKEN}


def main() -> int:
    if not BASE_TOKEN:
        raise RuntimeError("Missing LARK_BASE_APP_TOKEN.")

    tables_result = run_cli(["base", "+table-list", "--base-token", BASE_TOKEN, "--format", "json"])
    existing = {
        str(table.get("name", "")): str(table.get("table_id", "") or table.get("id", ""))
        for table in table_items(tables_result)
    }
    config = load_tables_config()
    config["base_token"] = BASE_TOKEN
    actions: list[dict[str, Any]] = []

    for target in TARGETS.values():
        name = target["name"]
        table_id = existing.get(name, "")
        create_result = None
        if not table_id:
            create_result = run_cli(
                [
                    "base",
                    "+table-create",
                    "--base-token",
                    BASE_TOKEN,
                    "--name",
                    name,
                    "--fields",
                    json.dumps(FIELD_TEMPLATE, ensure_ascii=False),
                    "--format",
                    "json",
                ]
            )
            table_id = table_id_from_create(create_result)
            if not table_id:
                raise RuntimeError(f"created table {name}, but table id was not returned")
        config[target["config_key"]] = {"name": name, "table_id": table_id}
        actions.append({"name": name, "table_id": table_id, "created": create_result is not None, "create_result": create_result})

    TABLES_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"base_token": BASE_TOKEN, "actions": actions, "tables_config": str(TABLES_PATH)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
