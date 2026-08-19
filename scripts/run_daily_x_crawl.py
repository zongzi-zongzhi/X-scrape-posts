from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

from insforge_x_leads.runner import run_daily_crawl

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run X public-post lead crawl with dry-run by default.")
    parser.add_argument("--config", default=os.environ.get("X_LEADS_CONFIG", "config/x_lead_crawl.yaml"))
    parser.add_argument("--live", action="store_true", help="Use configured live provider. Still read-only.")
    parser.add_argument(
        "--commit-local-state",
        action="store_true",
        help="Update local dedupe state. Only honored with --live.",
    )
    args = parser.parse_args()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    result = run_daily_crawl(config_path, live=args.live, commit_local_state=args.commit_local_state)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
