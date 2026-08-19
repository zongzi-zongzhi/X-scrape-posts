from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

from insforge_x_leads.config import load_config, resolve_path
from insforge_x_leads.profile import build_profile, save_profile


def main() -> int:
    parser = argparse.ArgumentParser(description="Build dynamic no-reply profile from labeled local samples.")
    parser.add_argument("--config", default=os.environ.get("X_LEADS_CONFIG", "config/x_lead_crawl.yaml"))
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config = load_config(config_path)
    inputs = [resolve_path(ROOT, path) for path in config["no_reply_profile"].get("training_inputs", [])]
    profile = build_profile(inputs, int(config["no_reply_profile"].get("min_phrase_count", 2)))
    if args.dry_run:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
        return 0
    out_path = resolve_path(ROOT, config["no_reply_profile"]["path"])
    save_profile(out_path, profile)
    print(json.dumps({"written": str(out_path), "blocked_phrases": len(profile["blocked_phrases"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

