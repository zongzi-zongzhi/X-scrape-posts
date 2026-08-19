from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from insforge_x_leads.dedupe import dedupe_leads, lead_keys
from insforge_x_leads.models import LeadCandidate


def lead(post_id: str, text: str = "hello") -> LeadCandidate:
    return LeadCandidate("x_public_post", f"https://x.com/a/status/{post_id}", post_id, "a", "A", text, "now", ["hello"], 3, "matched")


class DedupeTests(unittest.TestCase):
    def test_dedupes_existing_seen_key(self) -> None:
        existing = lead("1")
        fresh, duplicates = dedupe_leads([existing, lead("2", "different need")], lead_keys(existing))
        self.assertEqual([item.post_id for item in fresh], ["2"])
        self.assertEqual(duplicates[0]["post_id"], "1")


if __name__ == "__main__":
    unittest.main()
