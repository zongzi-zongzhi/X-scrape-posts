from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

from insforge_x_leads.config import load_config
from insforge_x_leads.lark import append_records, check_required_fields, list_table_fields, required_lark_env, tenant_access_token


def load_rows(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("leads JSON must contain rows array")
    return [dict(row) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Append approved generated rows to the fixed Feishu/Lark master table.")
    parser.add_argument("--config", default=os.environ.get("X_LEADS_CONFIG", "config/x_lead_crawl.yaml"))
    parser.add_argument("--input", help="Path to leads.json. Defaults to latest pointer.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print rows without writing to Lark.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config = load_config(config_path)

    if args.input:
        leads_path = Path(args.input)
        if not leads_path.is_absolute():
            leads_path = ROOT / leads_path
    else:
        pointer_path = ROOT / config["outputs"]["pointer_path"]
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        if not pointer.get("latest_leads_json"):
            raise RuntimeError("pointer has no latest_leads_json; run dry-run crawl first")
        leads_path = Path(pointer["latest_leads_json"])

    rows = load_rows(leads_path)[:50]
    human_only_fields = [str(field) for field in config["lark"].get("human_only_fields", [])]
    for row in rows:
        for field in human_only_fields:
            row[field] = ""

    if args.dry_run:
        print(json.dumps({"dry_run": True, "input": str(leads_path), "count": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
        return 0

    env = required_lark_env()
    token = tenant_access_token(env["LARK_APP_ID"], env["LARK_APP_SECRET"])
    fields = list_table_fields(env["LARK_BASE_APP_TOKEN"], env["LARK_TABLE_ID"], token)
    ok, missing = check_required_fields(fields, [str(v) for v in config["lark"]["required_fields"]])
    if not ok:
        raise RuntimeError(f"Lark master table missing required fields: {', '.join(missing)}")
    result = append_records(env["LARK_BASE_APP_TOKEN"], env["LARK_TABLE_ID"], token, rows)
    print(json.dumps({"appended": len(rows), "lark": result.get("data", {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

