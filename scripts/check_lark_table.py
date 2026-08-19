from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

from insforge_x_leads.config import load_config
from insforge_x_leads.lark import check_required_fields, list_table_fields, required_lark_env, tenant_access_token


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the fixed Feishu/Lark master table schema.")
    parser.add_argument("--config", default=os.environ.get("X_LEADS_CONFIG", "config/x_lead_crawl.yaml"))
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config = load_config(config_path)
    env = required_lark_env()
    token = tenant_access_token(env["LARK_APP_ID"], env["LARK_APP_SECRET"])
    fields = list_table_fields(env["LARK_BASE_APP_TOKEN"], env["LARK_TABLE_ID"], token)
    required = [str(field) for field in config["lark"]["required_fields"]]
    ok, missing = check_required_fields(fields, required)
    report = {"ok": ok, "missing_fields": missing, "field_count": len(fields)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

