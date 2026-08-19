from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from insforge_x_leads.profile import build_profile


class ProfileTests(unittest.TestCase):
    def test_builds_profile_from_no_reply_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "samples.jsonl"
            path.write_text(
                '{"label":"no_reply","text":"follow me for promo","author_handle":"bot"}\n'
                '{"label":"no_reply","text":"follow me for giveaway","author_handle":"bot"}\n',
                encoding="utf-8",
            )
            profile = build_profile([path], min_phrase_count=2)
            self.assertIn("bot", profile["blocked_handles"])
            self.assertIn("follow me", profile["blocked_phrases"])


if __name__ == "__main__":
    unittest.main()

