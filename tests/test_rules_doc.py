from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from insforge_x_leads.rules_doc import DEFAULT_RULES_DOC_PATH, load_rules_doc


RULES_FIXTURE = """# InsForge X 线索抓取规则

更新时间：2026-08-18

## 2. 只读采集边界

不得覆盖旧记录。人工字段必须留空。

## 6. InsForge 关键词硬规则

不得把 `insforge` 作为 X 搜索关键词。正文中出现 `insforge` 的帖子必须过滤。

## 7. 语言与分表规则

| 正文语言 | 飞书表名 | table_id |
|---|---|---|
| 简体中文 | X-简中 | tbld7aGIobbJNv2t |
| 繁体中文 | X-繁中 | tblgzlJjSEthFWmr |
| 英语 | X-英语 | tblpfhRNtf6YPTtS |
| 日语 | X-日语 | tblXN1qYIL0qfohf |
| 韩语 | X-韩语 | tblkbceeQtIOI0ng |

## 10. 数量规则

- 最少：10 条。
- 最多：25 条。

## 11. 飞书配置

飞书 base token：

```text
testbasetoken123
```

飞书 CLI profile：

```text
feishu-other-org
```

## 14. “不需要回”动态画像

每次同步前读取飞书表中 `状态=不需要回` 的样本。
"""


class RulesDocTests(unittest.TestCase):
    def test_loads_execution_values_from_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            rules_path = Path(temp_dir) / "rules.md"
            rules_path.write_text(RULES_FIXTURE, encoding="utf-8")

            rules = load_rules_doc(rules_path)

        self.assertEqual(rules["updated_at"], "2026-08-18")
        self.assertEqual(rules["base_token"], "testbasetoken123")
        self.assertEqual(rules["lark_cli_profile"], "feishu-other-org")
        self.assertEqual(rules["daily_min_per_language"], 10)
        self.assertEqual(rules["daily_max_per_language"], 25)
        self.assertEqual(rules["tables"]["simplified"]["table_id"], "tbld7aGIobbJNv2t")
        self.assertEqual(rules["tables"]["korean"]["name"], "X-韩语")
        self.assertTrue(rules["hard_rules"]["read_only_x"])
        self.assertTrue(rules["hard_rules"]["no_insforge_keyword"])

    def test_current_knowledge_base_rules_doc_is_readable(self) -> None:
        if not DEFAULT_RULES_DOC_PATH.exists():
            self.skipTest(f"rules doc not found: {DEFAULT_RULES_DOC_PATH}")

        rules = load_rules_doc(DEFAULT_RULES_DOC_PATH)

        self.assertEqual(rules["daily_min_per_language"], 10)
        self.assertEqual(rules["daily_max_per_language"], 25)
        self.assertEqual(rules["tables"]["english"]["table_id"], "tblpfhRNtf6YPTtS")


if __name__ == "__main__":
    unittest.main()
