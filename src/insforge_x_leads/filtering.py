from __future__ import annotations

import re
from typing import Any

from .models import LeadCandidate, XPost


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _contains_any(text: str, needles: list[str]) -> list[str]:
    normalized = normalize_text(text)
    return [needle for needle in needles if needle.lower() in normalized]


TRADITIONAL_ONLY_CHARS = set(
    "後網專權環變數據資料開發獨體驗學習熱課訓練實職歷"
    "這個麼為會讓與對於裡還雖點擊註冊登入頁應用問題"
    "關鍵選擇請教報錯複雜簡單連線儲存"
)
SIMPLIFIED_ONLY_CHARS = set(
    "后网专权环变数据资料开发独体验学习热课训练实职历"
    "这个么为会让与对于里还虽点击注册登录页应用问题"
    "关键选择请教报错复杂简单连线储存"
)


def chinese_script_counts(text: str) -> dict[str, int]:
    return {
        "cjk": len(re.findall(r"[\u3400-\u9fff]", text)),
        "simplified_markers": sum(1 for char in text if char in SIMPLIFIED_ONLY_CHARS),
        "traditional_markers": sum(1 for char in text if char in TRADITIONAL_ONLY_CHARS),
    }


def language_script_counts(text: str) -> dict[str, int]:
    latin_words = re.findall(r"\b[A-Za-z][A-Za-z0-9'_-]*\b", text)
    return {
        "latin_words": len(latin_words),
        "kana": len(re.findall(r"[\u3040-\u30ff]", text)),
        "hangul": len(re.findall(r"[\uac00-\ud7af]", text)),
        "cjk": len(re.findall(r"[\u3400-\u9fff]", text)),
    }


def language_rejection_reason(text: str, language_filter: dict[str, Any]) -> str:
    script = str(language_filter.get("script", "")).strip().lower()
    if not script:
        return ""
    if script in {"english", "en"}:
        counts = language_script_counts(text)
        min_latin_words = int(language_filter.get("min_latin_words", 8))
        max_cjk_chars = int(language_filter.get("max_cjk_chars", 2))
        if counts["latin_words"] < min_latin_words:
            return "language mismatch: not enough English text"
        if counts["kana"] or counts["hangul"] or counts["cjk"] > max_cjk_chars:
            return "language mismatch: expected English"
        return ""
    if script in {"japanese", "ja"}:
        counts = language_script_counts(text)
        min_japanese_chars = int(language_filter.get("min_japanese_chars", 6))
        if counts["kana"] + counts["cjk"] < min_japanese_chars or counts["kana"] == 0:
            return "language mismatch: expected Japanese"
        if counts["hangul"]:
            return "language mismatch: expected Japanese"
        return ""
    if script in {"korean", "ko"}:
        counts = language_script_counts(text)
        min_hangul_chars = int(language_filter.get("min_hangul_chars", 8))
        if counts["hangul"] < min_hangul_chars:
            return "language mismatch: expected Korean"
        if counts["kana"]:
            return "language mismatch: expected Korean"
        return ""
    min_chinese_chars = int(language_filter.get("min_chinese_chars", 8))
    min_script_markers = int(language_filter.get("min_script_markers", 1))
    counts = chinese_script_counts(text)
    if counts["cjk"] < min_chinese_chars:
        return "language mismatch: not enough Chinese text"
    simplified = counts["simplified_markers"]
    traditional = counts["traditional_markers"]
    if script in {"simplified", "zh-cn", "zh_cn"}:
        if simplified < min_script_markers or traditional > simplified:
            return "language mismatch: expected Simplified Chinese"
    elif script in {"traditional", "zh-tw", "zh_tw", "zh-hk", "zh_hk"}:
        if traditional < min_script_markers or simplified > traditional:
            return "language mismatch: expected Traditional Chinese"
    return ""


def should_skip_by_profile(post: XPost, profile: dict[str, Any]) -> tuple[bool, str]:
    handle = post.author_handle.lower().lstrip("@")
    if handle in {str(v).lower().lstrip("@") for v in profile.get("blocked_handles", [])}:
        return True, f"blocked handle: {handle}"
    text = normalize_text(post.text)
    for domain in profile.get("blocked_domains", []):
        if str(domain).lower() in text:
            return True, f"blocked domain: {domain}"
    for phrase in profile.get("blocked_phrases", []):
        if str(phrase).lower() in text:
            return True, f"blocked phrase: {phrase}"
    return False, ""


def _group_hits(text: str, groups: dict[str, list[str]]) -> dict[str, list[str]]:
    return {name: _contains_any(text, keywords) for name, keywords in groups.items()}


def score_post(
    post: XPost,
    include_keywords: list[str],
    high_priority_keywords: list[str] | None = None,
    required_group_hits: dict[str, list[str]] | None = None,
) -> tuple[int, list[str], list[str]]:
    matched = _contains_any(post.text, include_keywords)
    score = len(matched) * 2
    reasons = [f"matched keyword: {keyword}" for keyword in matched]
    high_priority_matched = _contains_any(post.text, high_priority_keywords or [])
    if high_priority_matched:
        score += len(high_priority_matched) * 3
        matched.extend(keyword for keyword in high_priority_matched if keyword not in matched)
        reasons.extend(f"matched high-priority keyword: {keyword}" for keyword in high_priority_matched)
    for group_name, hits in (required_group_hits or {}).items():
        if hits:
            score += 2
            reasons.append(f"matched profile group: {group_name}")
    likes = int(post.metrics.get("like_count", 0) or 0)
    replies = int(post.metrics.get("reply_count", 0) or 0)
    if replies > 0:
        score += 1
        reasons.append("has replies")
    if likes >= 5:
        score += 1
        reasons.append("has engagement")
    return score, matched, reasons


def _lead_from_post(
    post: XPost,
    matched: list[str],
    score: int,
    reasons: list[str],
) -> LeadCandidate:
    return LeadCandidate(
        source="x_public_post",
        post_url=post.post_url,
        post_id=post.post_id,
        author_handle=post.author_handle,
        author_name=post.author_name,
        post_text=post.text,
        created_at=post.created_at,
        matched_keywords=matched,
        score=score,
        reason="; ".join(reasons),
        metrics=post.metrics,
    )


def filter_posts_with_relaxed_pool(
    posts: list[XPost],
    filters: dict[str, Any],
    no_reply_profile: dict[str, Any],
) -> tuple[list[LeadCandidate], list[LeadCandidate], list[dict[str, Any]]]:
    include_keywords = [str(v) for v in filters.get("include_keywords", [])]
    high_priority_keywords = [str(v) for v in filters.get("high_priority_keywords", [])]
    exclude_keywords = [str(v) for v in filters.get("exclude_keywords", [])]
    language_filter = dict(filters.get("language_filter", {}))
    min_score = int(filters.get("min_score", 1))
    relaxed_min_score = int(filters.get("relaxed_min_score", 1))
    relaxed_must_match_groups = {str(v) for v in filters.get("relaxed_must_match_groups", [])}
    relaxed_must_match_any_group_sets = {
        tuple(str(group) for group in group_set)
        for group_set in filters.get("relaxed_must_match_any_group_sets", [])
    }
    required_groups = {
        str(name): [str(v) for v in keywords]
        for name, keywords in dict(filters.get("required_groups", {})).items()
    }
    must_match_groups = [str(v) for v in filters.get("must_match_groups", [])]
    any_group_sets = [
        [str(group) for group in group_set]
        for group_set in filters.get("must_match_any_group_sets", [])
    ]
    leads: list[LeadCandidate] = []
    relaxed_pool: list[LeadCandidate] = []
    rejected: list[dict[str, Any]] = []
    for post in posts:
        language_reason = language_rejection_reason(post.text, language_filter)
        if language_reason:
            rejected.append({"post_id": post.post_id, "reason": language_reason})
            continue
        excluded = _contains_any(post.text, exclude_keywords)
        if excluded:
            rejected.append({"post_id": post.post_id, "reason": f"excluded keyword: {excluded[0]}"})
            continue
        should_skip, reason = should_skip_by_profile(post, no_reply_profile)
        if should_skip:
            rejected.append({"post_id": post.post_id, "reason": reason})
            continue
        group_hits = _group_hits(post.text, required_groups)
        score, matched, reasons = score_post(post, include_keywords, high_priority_keywords, group_hits)
        if not matched:
            rejected.append({"post_id": post.post_id, "reason": "below score threshold"})
            continue
        missing_groups = [group for group in must_match_groups if not group_hits.get(group)]
        if missing_groups:
            if score >= relaxed_min_score and not any(group in relaxed_must_match_groups for group in missing_groups):
                relaxed_pool.append(
                    _lead_from_post(
                        post,
                        matched,
                        score,
                        [*reasons, f"relaxed fill candidate: missing profile group {missing_groups[0]}"],
                    )
                )
            rejected.append({"post_id": post.post_id, "reason": f"missing profile group: {missing_groups[0]}"})
            continue
        missing_any_group_set = next(
            (group_set for group_set in any_group_sets if not any(group_hits.get(group) for group in group_set)),
            None,
        )
        if missing_any_group_set:
            protected_missing_any_group = tuple(missing_any_group_set) in relaxed_must_match_any_group_sets
            if score >= relaxed_min_score and not protected_missing_any_group:
                relaxed_pool.append(
                    _lead_from_post(
                        post,
                        matched,
                        score,
                        [*reasons, f"relaxed fill candidate: missing one of profile groups {missing_any_group_set}"],
                    )
                )
            rejected.append({"post_id": post.post_id, "reason": f"missing one of profile groups: {missing_any_group_set}"})
            continue
        if score < min_score:
            if score >= relaxed_min_score:
                relaxed_pool.append(
                    _lead_from_post(
                        post,
                        matched,
                        score,
                        [*reasons, f"relaxed fill candidate: score {score} below normal threshold {min_score}"],
                    )
                )
            else:
                rejected.append({"post_id": post.post_id, "reason": "below score threshold"})
            continue
        leads.append(_lead_from_post(post, matched, score, reasons))
    relaxed_pool.sort(key=lambda lead: lead.score, reverse=True)
    return leads, relaxed_pool, rejected


def filter_posts(
    posts: list[XPost],
    filters: dict[str, Any],
    no_reply_profile: dict[str, Any],
) -> tuple[list[LeadCandidate], list[dict[str, Any]]]:
    leads, _relaxed_pool, rejected = filter_posts_with_relaxed_pool(posts, filters, no_reply_profile)
    return leads, rejected
