from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
from typing import Any

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

DEFAULT_COOKIE_PATH = ROOT / "secrets" / "x_cookies.json"


def read_env_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def upsert_env(values: dict[str, str]) -> Path:
    path = ROOT / ".env"
    lines = read_env_file(path)
    seen: set[str] = set()
    updated: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            updated.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in values:
            updated.append(f'{key}="{values[key]}"')
            seen.add(key)
        else:
            updated.append(line)
    for key, value in values.items():
        if key not in seen:
            updated.append(f'{key}="{value}"')
    path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
    return path


def normalize_cookies(payload: Any) -> dict[str, str]:
    if isinstance(payload, dict):
        cookies = payload.get("cookies", payload)
        if isinstance(cookies, dict):
            return {str(k): str(v) for k, v in cookies.items() if v is not None}
    if isinstance(payload, list):
        out: dict[str, str] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            value = item.get("value")
            if name and value is not None:
                out[str(name)] = str(value)
        return out
    raise ValueError("cookies must be a dict, {'cookies': {...}}, or browser-exported list")


def load_cookie_file(path: Path) -> dict[str, str]:
    return normalize_cookies(json.loads(path.read_text(encoding="utf-8-sig")))


def validate_cookies(cookies: dict[str, str]) -> dict[str, Any]:
    missing = [name for name in ("auth_token", "ct0") if not cookies.get(name)]
    return {
        "ok": not missing,
        "missing": missing,
        "has_auth_token": bool(cookies.get("auth_token")),
        "has_ct0": bool(cookies.get("ct0")),
        "cookie_count": len(cookies),
    }


def write_cookies(path: Path, cookies: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up Scweet cookies for read-only X collection.")
    parser.add_argument("--cookie-file", default=os.environ.get("SCWEET_COOKIES_FILE", str(DEFAULT_COOKIE_PATH)))
    parser.add_argument("--prompt", action="store_true", help="Prompt for auth_token and ct0, then write cookie file.")
    parser.add_argument("--check", action="store_true", help="Check cookie file shape without printing secrets.")
    parser.add_argument("--write-env", action="store_true", help="Write X_PROVIDER=scweet and SCWEET_COOKIES_FILE to .env.")
    args = parser.parse_args()

    cookie_path = Path(args.cookie_file)
    if not cookie_path.is_absolute():
        cookie_path = ROOT / cookie_path

    if args.prompt:
        auth_token = getpass.getpass("X auth_token cookie: ").strip()
        ct0 = getpass.getpass("X ct0 cookie: ").strip()
        write_cookies(cookie_path, {"auth_token": auth_token, "ct0": ct0})

    if args.write_env:
        env_path = upsert_env(
            {
                "X_PROVIDER": "scweet",
                "SCWEET_COOKIES_FILE": str(cookie_path),
                "SCWEET_DB_PATH": str(ROOT / "data" / "scweet_state.db"),
            }
        )
    else:
        env_path = None

    if args.check or args.prompt or args.write_env:
        if not cookie_path.exists():
            raise RuntimeError(f"cookie file not found: {cookie_path}")
        status = validate_cookies(load_cookie_file(cookie_path))
        print(
            json.dumps(
                {
                    **status,
                    "cookie_file": str(cookie_path),
                    "env_file": str(env_path) if env_path else None,
                    "secrets_printed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if status["ok"] else 2

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
