from __future__ import annotations

import importlib.util
from pathlib import Path


FORBIDDEN_ENV_NAMES = {
    "X_PASSWORD",
    "TWITTER_PASSWORD",
    "X_ACCOUNT_POOL",
    "CAPTCHA_API_KEY",
    "CAPTCHA_SOLVER_KEY",
}

SUSPICIOUS_TOKENS = [
    "subprocess",
    "os.system",
    "eval(",
    "exec(",
    "selenium",
    "playwright",
    "captcha",
    "password",
]


def find_installed_package_root(package: str) -> Path | None:
    spec = importlib.util.find_spec(package)
    if not spec:
        return None
    locations = spec.submodule_search_locations
    if locations:
        return Path(next(iter(locations)))
    if spec.origin:
        return Path(spec.origin).parent
    return None


def scan_package_text(package_root: Path, max_files: int = 200) -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {}
    files = list(package_root.rglob("*.py"))[:max_files]
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        hits = [token for token in SUSPICIOUS_TOKENS if token.lower() in text]
        if hits:
            findings[str(path)] = hits
    return findings

