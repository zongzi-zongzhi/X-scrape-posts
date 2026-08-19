from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import LeadCandidate, XPost


def make_run_dir(outputs_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = outputs_root / f"run-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_raw_jsonl(path: Path, posts: list[XPost]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for post in posts:
            handle.write(json.dumps(asdict(post), ensure_ascii=False) + "\n")


def write_leads_json(path: Path, leads: list[LeadCandidate], human_only_fields: list[str]) -> None:
    rows = [lead.to_master_row(human_only_fields) for lead in leads]
    write_json(path, {"count": len(rows), "rows": rows})


def write_leads_markdown(path: Path, leads: list[LeadCandidate]) -> None:
    lines = ["# X InsForge Lead Candidates", ""]
    if not leads:
        lines.append("No lead candidates passed filters in this run.")
    for idx, lead in enumerate(leads, start=1):
        lines.extend(
            [
                f"## {idx}. @{lead.author_handle}",
                "",
                f"- URL: {lead.post_url}",
                f"- Created: {lead.created_at}",
                f"- Score: {lead.score}",
                f"- Matched: {', '.join(lead.matched_keywords)}",
                f"- Reason: {lead.reason}",
                "",
                lead.post_text,
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_pointer(pointer_path: Path, run_dir: Path, mode: str, files: dict[str, Path], notes: list[str]) -> None:
    payload = {
        "project": "insforge-x-leads",
        "latest_run_dir": str(run_dir),
        "latest_leads_json": str(files["leads_json"]),
        "latest_leads_markdown": str(files["leads_markdown"]),
        "latest_raw_jsonl": str(files["raw_jsonl"]),
        "latest_log_json": str(files["log_json"]),
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "notes": notes,
    }
    write_json(pointer_path, payload)

