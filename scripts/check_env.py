from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

from insforge_x_leads.config import load_config, require_read_only, resolve_path
from insforge_x_leads.safety import FORBIDDEN_ENV_NAMES, find_installed_package_root, scan_package_text


def package_report(package: str) -> dict[str, object]:
    root = find_installed_package_root(package)
    if not root:
        return {"installed": False, "root": None, "suspicious_scan": "not_scanned"}
    findings = scan_package_text(root)
    return {
        "installed": True,
        "root": str(root),
        "suspicious_scan": findings,
        "note": "Text scan only; package was not imported or executed.",
    }


def main() -> int:
    config_path = Path(os.environ.get("X_LEADS_CONFIG", ROOT / "config" / "x_lead_crawl.yaml"))
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    report: dict[str, object] = {
        "project_root": str(ROOT),
        "config_path": str(config_path),
        "python": sys.version.split()[0],
        "checks": [],
        "missing_for_live": [],
        "forbidden_env_present": [],
    }
    config = load_config(config_path)
    require_read_only(config)
    report["checks"].append("config loaded")
    report["checks"].append("read_only=true and max_new_leads_per_run<=50")

    for rel in ["outputs", "logs", "data"]:
        (ROOT / rel).mkdir(parents=True, exist_ok=True)
    report["checks"].append("local output/log/data directories present")

    forbidden_present = [name for name in FORBIDDEN_ENV_NAMES if os.environ.get(name)]
    report["forbidden_env_present"] = forbidden_present

    provider = str(os.environ.get("X_PROVIDER") or config.get("run", {}).get("provider", "fixture")).lower()
    if provider in {"x_api", "official", "x-official"} and not os.environ.get("X_BEARER_TOKEN"):
        report["missing_for_live"].append("X_BEARER_TOKEN")
    if provider == "twscrape" and not os.environ.get("TWSCRAPE_ACCOUNTS_DB"):
        report["missing_for_live"].append("TWSCRAPE_ACCOUNTS_DB")
    if provider == "scweet" and not (os.environ.get("SCWEET_COOKIES_FILE") or os.environ.get("SCWEET_AUTH_TOKEN")):
        report["missing_for_live"].append("SCWEET_COOKIES_FILE or SCWEET_AUTH_TOKEN")
    if provider == "twikit" and not os.environ.get("TWIKIT_COOKIES_PATH"):
        report["missing_for_live"].append("TWIKIT_COOKIES_PATH")

    lark_required = ["LARK_APP_ID", "LARK_APP_SECRET", "LARK_BASE_APP_TOKEN", "LARK_TABLE_ID"]
    report["missing_lark"] = [name for name in lark_required if not os.environ.get(name)]
    report["providers"] = {
        "x_api": {
            "installed": True,
            "root": None,
            "note": "Uses official X API recent search over HTTPS; requires X_BEARER_TOKEN.",
        },
        "twscrape": package_report("twscrape"),
        "Scweet": package_report("Scweet"),
        "twikit": package_report("twikit"),
    }
    profile_path = resolve_path(ROOT, config["no_reply_profile"]["path"])
    report["no_reply_profile_exists"] = profile_path.exists()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if forbidden_present else 0


if __name__ == "__main__":
    raise SystemExit(main())
