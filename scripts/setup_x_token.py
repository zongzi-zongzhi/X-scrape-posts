from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from _bootstrap import add_src_to_path, load_dotenv

ROOT = add_src_to_path()
load_dotenv(ROOT)

TOKEN_URLS = [
    "https://api.x.com/oauth2/token",
    "https://api.twitter.com/oauth2/token",
]
VALIDATION_URL = "https://api.x.com/2/users/by/username/XDevelopers"


def _request_json(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def current_token() -> str:
    return str(os.environ.get("X_BEARER_TOKEN", "")).strip()


def validate_token(token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        VALIDATION_URL,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "insforge-x-leads/1.0 token-check"},
        method="GET",
    )
    payload = _request_json(request)
    return {"ok": True, "endpoint": VALIDATION_URL, "user": payload.get("data", {})}


def generate_bearer_token(api_key: str, api_secret: str) -> str:
    encoded_key = urllib.parse.quote(api_key, safe="")
    encoded_secret = urllib.parse.quote(api_secret, safe="")
    credentials = base64.b64encode(f"{encoded_key}:{encoded_secret}".encode("utf-8")).decode("ascii")
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    last_error: Exception | None = None
    for url in TOKEN_URLS:
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "User-Agent": "insforge-x-leads/1.0 token-setup",
            },
            method="POST",
        )
        try:
            payload = _request_json(request)
            token = str(payload.get("access_token", "")).strip()
            if not token:
                raise RuntimeError(f"Bearer token missing in response from {url}")
            return token
        except RuntimeError as exc:
            last_error = exc
            continue
    raise RuntimeError(f"Could not generate bearer token: {last_error}") from last_error


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up and validate an official X API Bearer Token.")
    parser.add_argument("--check", action="store_true", help="Validate X_BEARER_TOKEN from env/.env.")
    parser.add_argument("--from-api-keys", action="store_true", help="Generate a Bearer Token from API Key and API Secret.")
    parser.add_argument("--prompt-token", action="store_true", help="Prompt for an existing Bearer Token.")
    parser.add_argument("--write-env", action="store_true", help="Write X_PROVIDER=x_api and X_BEARER_TOKEN to .env.")
    args = parser.parse_args()

    token = current_token()
    if args.from_api_keys:
        api_key = os.environ.get("X_API_KEY") or input("X API Key: ").strip()
        api_secret = os.environ.get("X_API_SECRET") or getpass.getpass("X API Secret: ").strip()
        token = generate_bearer_token(api_key, api_secret)
    elif args.prompt_token:
        token = getpass.getpass("X Bearer Token: ").strip()

    if args.write_env:
        if not token:
            raise RuntimeError("No token available to write. Use --prompt-token or --from-api-keys.")
        env_path = upsert_env({"X_PROVIDER": "x_api", "X_BEARER_TOKEN": token})
        print(json.dumps({"ok": True, "wrote": str(env_path), "token_printed": False}, ensure_ascii=False, indent=2))

    if args.check or args.from_api_keys or args.prompt_token:
        if not token:
            raise RuntimeError("X_BEARER_TOKEN is missing. Use --prompt-token or --from-api-keys.")
        result = validate_token(token)
        print(json.dumps({**result, "token_printed": False}, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
