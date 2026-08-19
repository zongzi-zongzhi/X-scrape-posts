from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_lark_x_table_cli


class LarkSyncQuantityGateTests(unittest.TestCase):
    def test_append_reports_shortfall_but_continues_when_fresh_rows_are_below_min_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            leads_path = temp_root / "leads.json"
            leads_path.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "post_id": "1",
                                "post_url": "https://x.com/a/status/1",
                                "author_handle": "a",
                                "post_text": "I built an app and Supabase auth is failing",
                                "created_at": "2026-08-18T00:00:00+0000",
                                "matched_keywords": "Supabase auth",
                            },
                            {
                                "post_id": "2",
                                "post_url": "https://x.com/b/status/2",
                                "author_handle": "b",
                                "post_text": "Vercel API Key config is tedious for my MVP",
                                "created_at": "2026-08-18T00:00:00+0000",
                                "matched_keywords": "Vercel API Key",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            cli_calls: list[list[str]] = []

            def fake_run_cli(args: list[str]) -> dict:
                cli_calls.append(args)
                if "+field-list" in args:
                    return {
                        "data": {
                            "fields": [
                                {"name": "发布时间"},
                                {"name": "帖子名字"},
                                {"name": "帖子链接"},
                                {"name": "状态"},
                                {"name": "评论"},
                                {"name": "匹配关键词"},
                                {"name": "后续帖主回复"},
                                {"name": "回复情况"},
                                {"name": "二次评论"},
                                {"name": "其他"},
                            ]
                        }
                    }
                if "+record-list" in args:
                    return {"data": {"fields": ["帖子链接", "状态"], "data": []}}
                if "+record-batch-create" in args:
                    return {"data": {"records": [{"record_id": "rec1"}, {"record_id": "rec2"}]}}
                raise AssertionError(f"unexpected lark-cli call: {args}")

            argv = [
                "sync_lark_x_table_cli.py",
                "--input",
                str(leads_path),
                "--table-id",
                "tbl-test",
                "--base-token",
                "testbasetoken123",
                "--append",
                "--limit",
                "25",
                "--min-count",
                "10",
                "--label",
                "quantity-test",
            ]

            with (
                patch.object(sync_lark_x_table_cli, "ROOT", temp_root),
                patch.object(sync_lark_x_table_cli, "run_cli", side_effect=fake_run_cli),
                patch.object(sys, "argv", argv),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = sync_lark_x_table_cli.main()

            self.assertEqual(exit_code, 0)
            self.assertTrue(any("+record-batch-create" in call for call in cli_calls))

            reports = list((temp_root / "outputs").glob("lark-sync-quantity-test-*/sync_report.json"))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertEqual(report["fresh_count"], 2)
            self.assertEqual(report["append_count"], 2)
            self.assertEqual(report["blocked_reason"], "")
            self.assertEqual(report["quantity_shortfall"], "fresh_count below target minimum: 2 < 10")
            self.assertEqual(report["constraints"]["min_append"], 10)
            self.assertEqual(report["constraints"]["max_append"], 25)


if __name__ == "__main__":
    unittest.main()
