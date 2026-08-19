from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from insforge_x_leads.filtering import filter_posts, filter_posts_with_relaxed_pool
from insforge_x_leads.models import XPost
from insforge_x_leads.runner import _filter_posts_by_window


class FilteringTests(unittest.TestCase):
    def test_filters_posts_by_utc_date_window(self) -> None:
        posts = [
            XPost("1", "https://x.com/a/status/1", "a", "A", "one", "2026-08-16 23:59:59+00:00", {}),
            XPost("2", "https://x.com/b/status/2", "b", "B", "two", "2026-08-17 00:00:00+00:00", {}),
            XPost("3", "https://x.com/c/status/3", "c", "C", "three", "2026-08-18 00:00:00+00:00", {}),
        ]
        filtered = _filter_posts_by_window(posts, "2026-08-17", "2026-08-18")
        self.assertEqual([post.post_id for post in filtered], ["2"])

    def test_filters_relevant_post_and_rejects_no_reply(self) -> None:
        posts = [
            XPost("1", "https://x.com/a/status/1", "a", "A", "Need open source backend as a service", "now", {"like_count": 5}),
            XPost("2", "https://x.com/b/status/2", "b", "B", "Retweet to win a giveaway", "now", {}),
        ]
        leads, rejected = filter_posts(
            posts,
            {"include_keywords": ["backend as a service"], "exclude_keywords": ["giveaway"], "min_score": 3},
            {"blocked_handles": [], "blocked_domains": [], "blocked_phrases": ["retweet to win"]},
        )
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].post_id, "1")
        self.assertEqual(len(rejected), 1)

    def test_requires_project_backend_and_intent_groups(self) -> None:
        posts = [
            XPost("1", "https://x.com/a/status/1", "a", "A", "我用 AI 做了个 SaaS，前端好了，Supabase RLS 权限一直报错，求助怎么办", "now", {}),
            XPost("2", "https://x.com/b/status/2", "b", "B", "Cursor 教程：零基础认识 AI 编程工具", "now", {}),
            XPost("3", "https://x.com/c/status/3", "c", "C", "Vercel Supabase API Key 配置真的很麻烦，不想自己干", "now", {}),
        ]
        filters = {
            "include_keywords": ["Supabase", "RLS", "Vercel", "API Key"],
            "exclude_keywords": ["教程", "零基础"],
            "min_score": 4,
            "required_groups": {
                "project_context": ["App", "网站", "SaaS", "MVP", "项目"],
                "backend_pain": ["后端", "数据库", "Supabase", "RLS", "API Key", "Vercel"],
                "intent": ["求助", "怎么办", "报错", "麻烦", "不想自己干"],
            },
            "must_match_groups": ["backend_pain"],
            "must_match_any_group_sets": [["project_context", "intent"]],
        }
        leads, rejected = filter_posts(posts, filters, {"blocked_handles": [], "blocked_domains": [], "blocked_phrases": []})
        self.assertEqual([lead.post_id for lead in leads], ["1", "3"])
        self.assertEqual(len(rejected), 1)

    def test_requires_simplified_chinese_body_when_configured(self) -> None:
        posts = [
            XPost("1", "https://x.com/a/status/1", "a", "A", "我做了一个网站，Supabase 数据库保存失败，求助怎么处理", "now", {}),
            XPost("2", "https://x.com/b/status/2", "b", "B", "我做了一個網站，Supabase 資料庫保存失敗，求助怎麼處理", "now", {}),
            XPost("3", "https://x.com/c/status/3", "c", "C", "I built an app and Supabase auth is broken", "now", {}),
        ]
        filters = {
            "include_keywords": ["Supabase", "数据库", "网站", "求助"],
            "min_score": 1,
            "language_filter": {"script": "simplified", "min_chinese_chars": 8},
        }
        leads, rejected = filter_posts(posts, filters, {"blocked_handles": [], "blocked_domains": [], "blocked_phrases": []})
        self.assertEqual([lead.post_id for lead in leads], ["1"])
        self.assertEqual(len(rejected), 2)

    def test_requires_traditional_chinese_body_when_configured(self) -> None:
        posts = [
            XPost("1", "https://x.com/a/status/1", "a", "A", "我做了一个网站，Supabase 数据库保存失败，求助怎么处理", "now", {}),
            XPost("2", "https://x.com/b/status/2", "b", "B", "我做了一個網站，Supabase 資料庫保存失敗，求助怎麼處理", "now", {}),
        ]
        filters = {
            "include_keywords": ["Supabase", "資料庫", "網站", "求助"],
            "min_score": 1,
            "language_filter": {"script": "traditional", "min_chinese_chars": 8},
        }
        leads, rejected = filter_posts(posts, filters, {"blocked_handles": [], "blocked_domains": [], "blocked_phrases": []})
        self.assertEqual([lead.post_id for lead in leads], ["2"])
        self.assertEqual(len(rejected), 1)

    def test_low_score_matches_enter_relaxed_pool_without_bypassing_excludes(self) -> None:
        posts = [
            XPost("1", "https://x.com/a/status/1", "a", "A", "My MVP backend setup is tedious", "now", {}),
            XPost("2", "https://x.com/b/status/2", "b", "B", "My MVP backend setup tutorial", "now", {}),
        ]
        filters = {
            "include_keywords": ["backend"],
            "exclude_keywords": ["tutorial"],
            "min_score": 6,
            "relaxed_min_score": 1,
        }
        leads, relaxed_pool, rejected = filter_posts_with_relaxed_pool(
            posts,
            filters,
            {"blocked_handles": [], "blocked_domains": [], "blocked_phrases": []},
        )
        self.assertEqual(leads, [])
        self.assertEqual([lead.post_id for lead in relaxed_pool], ["1"])
        self.assertEqual([item["post_id"] for item in rejected], ["2"])

    def test_missing_soft_groups_can_enter_relaxed_pool(self) -> None:
        posts = [
            XPost("1", "https://x.com/a/status/1", "a", "A", "My app keeps failing on Supabase", "now", {}),
            XPost("2", "https://x.com/b/status/2", "b", "B", "My app Supabase tutorial", "now", {}),
        ]
        filters = {
            "include_keywords": ["app", "Supabase"],
            "exclude_keywords": ["tutorial"],
            "min_score": 6,
            "relaxed_min_score": 1,
            "required_groups": {"backend_pain": ["database", "auth"]},
            "must_match_groups": ["backend_pain"],
        }
        leads, relaxed_pool, rejected = filter_posts_with_relaxed_pool(
            posts,
            filters,
            {"blocked_handles": [], "blocked_domains": [], "blocked_phrases": []},
        )
        self.assertEqual(leads, [])
        self.assertEqual([lead.post_id for lead in relaxed_pool], ["1"])
        self.assertEqual([item["post_id"] for item in rejected], ["1", "2"])

    def test_relaxed_pool_can_require_core_groups(self) -> None:
        posts = [
            XPost("1", "https://x.com/a/status/1", "a", "A", "My app setup is annoying", "now", {}),
        ]
        filters = {
            "include_keywords": ["app"],
            "min_score": 6,
            "relaxed_min_score": 1,
            "required_groups": {"backend_pain": ["database", "auth"]},
            "must_match_groups": ["backend_pain"],
            "relaxed_must_match_groups": ["backend_pain"],
        }
        leads, relaxed_pool, rejected = filter_posts_with_relaxed_pool(
            posts,
            filters,
            {"blocked_handles": [], "blocked_domains": [], "blocked_phrases": []},
        )
        self.assertEqual(leads, [])
        self.assertEqual(relaxed_pool, [])
        self.assertEqual([item["post_id"] for item in rejected], ["1"])

    def test_relaxed_pool_can_require_any_group_sets(self) -> None:
        posts = [
            XPost("1", "https://x.com/a/status/1", "a", "A", "Supabase database setup", "now", {}),
        ]
        filters = {
            "include_keywords": ["Supabase", "database"],
            "min_score": 6,
            "relaxed_min_score": 1,
            "required_groups": {"intent": ["stuck", "help"]},
            "must_match_any_group_sets": [["intent"]],
            "relaxed_must_match_any_group_sets": [["intent"]],
        }
        leads, relaxed_pool, rejected = filter_posts_with_relaxed_pool(
            posts,
            filters,
            {"blocked_handles": [], "blocked_domains": [], "blocked_phrases": []},
        )
        self.assertEqual(leads, [])
        self.assertEqual(relaxed_pool, [])
        self.assertEqual([item["post_id"] for item in rejected], ["1"])


if __name__ == "__main__":
    unittest.main()
