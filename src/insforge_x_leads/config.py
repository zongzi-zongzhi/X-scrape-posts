from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


def project_root_from(path: str | Path) -> Path:
    config_path = Path(path).resolve()
    if config_path.parent.name == "config":
        return config_path.parent.parent
    return Path.cwd()


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional dep
            raise ConfigError(
                f"{config_path} is not JSON-compatible YAML and PyYAML is unavailable"
            ) from exc
        loaded = yaml.safe_load(text)
        if not isinstance(loaded, dict):
            raise ConfigError(f"{config_path} must load to an object")
        return loaded


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def get_config_path(default: str = "config/x_lead_crawl.yaml") -> Path:
    return Path(os.environ.get("X_LEADS_CONFIG", default))


def require_read_only(config: dict[str, Any]) -> None:
    if config.get("x", {}).get("read_only") is not True:
        raise ConfigError("config.x.read_only must be true")
    if int(config.get("run", {}).get("max_new_leads_per_run", 0)) > 50:
        raise ConfigError("run.max_new_leads_per_run must be <= 50")

