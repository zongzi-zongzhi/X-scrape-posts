from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from .config import ConfigError


DEFAULT_RULES_DOC_PATH = Path(r"D:\zhishiku-010204\InsForge_X线索抓取规则.md")

LANGUAGE_TABLE_KEYS = {
    "简体中文": "simplified",
    "繁体中文": "traditional",
    "英语": "english",
    "日语": "japanese",
    "韩语": "korean",
}

REQUIRED_HARD_RULE_MARKERS = [
    "只读采集边界",
    "InsForge 关键词硬规则",
    "不得把 `insforge`",
    "正文中出现 `insforge`",
    "状态=不需要回",
    "覆盖旧",
    "人工字段必须留空",
]


def default_rules_doc_path() -> Path:
    return Path(os.environ.get("X_LEADS_RULES_DOC", str(DEFAULT_RULES_DOC_PATH)))


def _extract_required(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        raise ConfigError(f"rules doc missing {label}")
    return match.group(1).strip()


def _extract_int(pattern: str, text: str, label: str) -> int:
    value = _extract_required(pattern, text, label)
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"rules doc {label} must be an integer") from exc


def _parse_tables(text: str) -> dict[str, dict[str, str]]:
    tables: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "table_id" in stripped or "---" in stripped:
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) < 3:
            continue
        language, table_name, table_id = parts[:3]
        table_key = LANGUAGE_TABLE_KEYS.get(language)
        if not table_key:
            continue
        tables[table_key] = {
            "language": language,
            "name": table_name,
            "table_id": table_id,
        }
    return tables


def load_rules_doc(path: str | Path | None = None) -> dict[str, Any]:
    rules_path = Path(path) if path else default_rules_doc_path()
    if not rules_path.exists():
        raise ConfigError(f"rules doc not found: {rules_path}")

    text = rules_path.read_text(encoding="utf-8")
    missing_markers = [marker for marker in REQUIRED_HARD_RULE_MARKERS if marker not in text]
    if missing_markers:
        raise ConfigError(f"rules doc missing hard-rule markers: {', '.join(missing_markers)}")

    daily_min = _extract_int(r"最少：\s*(\d+)\s*条", text, "daily minimum")
    daily_max = _extract_int(r"最多：\s*(\d+)\s*条", text, "daily maximum")
    if daily_min < 0 or daily_max < daily_min or daily_max > 50:
        raise ConfigError("rules doc quantity rule must satisfy 0 <= min <= max <= 50")

    tables = _parse_tables(text)
    missing_tables = [key for key in LANGUAGE_TABLE_KEYS.values() if key not in tables]
    if missing_tables:
        raise ConfigError(f"rules doc missing table mappings: {', '.join(missing_tables)}")
    invalid_table_ids = [info["table_id"] for info in tables.values() if not info["table_id"].startswith("tbl")]
    if invalid_table_ids:
        raise ConfigError(f"rules doc has invalid table ids: {', '.join(invalid_table_ids)}")

    base_token = _extract_required(r"飞书 base token：[\s\S]*?```text\s*([A-Za-z0-9]+)\s*```", text, "Feishu base token")
    lark_cli_profile = _extract_required(r"飞书 CLI profile：[\s\S]*?```text\s*([A-Za-z0-9_-]+)\s*```", text, "Feishu CLI profile")
    updated_at = _extract_required(r"更新时间：\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, "updated date")

    return {
        "path": str(rules_path),
        "updated_at": updated_at,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "base_token": base_token,
        "lark_cli_profile": lark_cli_profile,
        "daily_min_per_language": daily_min,
        "daily_max_per_language": daily_max,
        "tables": tables,
        "hard_rules": {
            "read_only_x": True,
            "no_x_interactions": True,
            "no_insforge_keyword": True,
            "dry_run_before_append": True,
            "do_not_overwrite_records": True,
            "human_fields_left_blank": True,
        },
    }
