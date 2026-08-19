from __future__ import annotations

import unittest

from insforge_x_leads.providers.x_api_provider import _payload_to_posts


class XApiProviderTests(unittest.TestCase):
    def test_maps_recent_search_payload(self) -> None:
        payload = {
            "data": [
                {
                    "id": "123",
                    "author_id": "u1",
                    "text": "Need an open source backend as a service",
                    "created_at": "2026-08-11T00:00:00.000Z",
                    "public_metrics": {"reply_count": 2, "retweet_count": 1, "like_count": 7},
                }
            ],
            "includes": {"users": [{"id": "u1", "username": "builder", "name": "Builder"}]},
        }

        posts = _payload_to_posts(payload)

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].post_id, "123")
        self.assertEqual(posts[0].post_url, "https://x.com/builder/status/123")
        self.assertEqual(posts[0].metrics["like_count"], 7)


if __name__ == "__main__":
    unittest.main()
