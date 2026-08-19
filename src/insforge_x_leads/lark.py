from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


LARK_BASE = "https://open.feishu.cn/open-apis"


class LarkError(RuntimeError):
    pass


def required_lark_env() -> dict[str, str]:
    values = {
        "LARK_APP_ID": os.environ.get("LARK_APP_ID", ""),
        "LARK_APP_SECRET": os.environ.get("LARK_APP_SECRET", ""),
        "LARK_BASE_APP_TOKEN": os.environ.get("LARK_BASE_APP_TOKEN", ""),
        "LARK_TABLE_ID": os.environ.get("LARK_TABLE_ID", ""),
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise LarkError(f"missing required Lark env vars: {', '.join(missing)}")
    return values


def _request(method: str, url: str, payload: dict[str, Any] | None = None, token: str | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LarkError(f"Lark HTTP {exc.code}: {detail}") from exc
    result = json.loads(body)
    if result.get("code", 0) != 0:
        raise LarkError(f"Lark API error: {result}")
    return result


def tenant_access_token(app_id: str, app_secret: str) -> str:
    result = _request(
        "POST",
        f"{LARK_BASE}/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    token = result.get("tenant_access_token")
    if not token:
        raise LarkError("tenant_access_token missing in Lark response")
    return str(token)


def list_table_fields(app_token: str, table_id: str, token: str) -> list[dict[str, Any]]:
    result = _request(
        "GET",
        f"{LARK_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/fields?page_size=100",
        token=token,
    )
    return list(result.get("data", {}).get("items", []))


def check_required_fields(fields: list[dict[str, Any]], required: list[str]) -> tuple[bool, list[str]]:
    names = {str(field.get("field_name", "")) for field in fields}
    missing = [field for field in required if field not in names]
    return not missing, missing


def append_records(app_token: str, table_id: str, token: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    records = [{"fields": row} for row in rows]
    return _request(
        "POST",
        f"{LARK_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
        {"records": records},
        token=token,
    )

