from __future__ import annotations

import unittest

from insforge_x_leads.providers.scweet_provider import _scweet_row_to_post


class ScweetProviderTests(unittest.TestCase):
    def test_maps_scweet_row(self) -> None:
        row = {
            "tweet_id": "123",
            "tweet_url": "https://x.com/builder/status/123",
            "timestamp": "2026-08-11T00:00:00Z",
            "text": "Need an open source backend",
            "likes": 8,
            "retweets": 2,
            "comments": 1,
            "user": {"screen_name": "builder", "name": "Builder"},
        }

        post = _scweet_row_to_post(row)

        self.assertEqual(post.post_id, "123")
        self.assertEqual(post.author_handle, "builder")
        self.assertEqual(post.metrics["like_count"], 8)


if __name__ == "__main__":
    unittest.main()
