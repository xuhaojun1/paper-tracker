# -*- coding: utf-8 -*-
"""
HuggingFace Daily Papers / Trending 论文抓取。
并发请求 HF API，提取论文元数据，按本地关键词 + upvotes 加权打分。
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..utils.logging import log_info, log_warn, log_debug

# ── HuggingFace API ──────────────────────────────────────────────────
HF_DAILY_API = "https://huggingface.co/api/daily_papers"
HF_TIMEOUT = 30
HF_UA = "paper-tracker/0.4 (+https://github.com/xuhaojun1/paper-tracker)"

_session = requests.Session()
_session.headers.update({"User-Agent": HF_UA, "Accept": "application/json"})


# ── 抓取 ─────────────────────────────────────────────────────────────

def _fetch_hf_daily(limit: int = 100) -> List[Dict[str, Any]]:
    """
    拉取 HuggingFace Daily Papers API。
    返回原始 JSON 列表。
    """
    try:
        resp = _session.get(
            HF_DAILY_API,
            params={"limit": str(limit)},
            timeout=HF_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log_warn(f"[HF] Daily Papers 请求失败: {e}")
        return []


def fetch_hf_papers(
    limit: int = 100,
    since_days: int = 7,
) -> List[Dict[str, Any]]:
    """
    并发请求 HF Daily Papers，合并去重，转换为统一 item 格式。

    返回的 item 字典与原 arXiv parser 输出兼容，额外增加：
      - hf_upvotes: int        HF 社区投票数
      - hf_source: str         来源标记 ("daily" / "trending")
      - github_repo: str       GitHub 仓库地址
      - github_stars: int      GitHub star 数
      - thumbnail: str         缩略图 URL
      - ai_summary: str        HF 生成的 AI 摘要
      - ai_keywords: list      HF 生成的关键词列表
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days) if since_days > 0 else None

    raw_daily = _fetch_hf_daily(limit=limit)
    log_info(f"[HF] Daily Papers 返回 {len(raw_daily)} 篇")

    # 去重 + 转换
    seen_ids: Set[str] = set()
    items: List[Dict[str, Any]] = []

    for raw in raw_daily:
        item = _normalize_hf_item(raw, source="daily")
        if not item:
            continue
        aid = item["id"]
        if aid in seen_ids:
            continue

        # 时间窗过滤
        if cutoff:
            pub = _parse_iso(item.get("published"))
            if pub and pub < cutoff:
                continue

        seen_ids.add(aid)
        items.append(item)

    log_info(f"[HF] 合并去重后 {len(items)} 篇候选")
    return items


# ── 格式转换 ─────────────────────────────────────────────────────────

def _normalize_hf_item(raw: Dict[str, Any], source: str = "daily") -> Optional[Dict[str, Any]]:
    """
    将 HF API 返回的单条数据转换为与 arXiv parser 兼容的 item 字典。
    """
    paper = raw.get("paper") or {}
    arxiv_id = paper.get("id") or ""
    if not arxiv_id:
        return None

    title = (paper.get("title") or raw.get("title") or "").replace("\n", " ").strip()
    summary = (paper.get("summary") or raw.get("summary") or "").strip()
    authors = [a.get("name", "") for a in (paper.get("authors") or []) if a.get("name")]

    # 时间
    published = raw.get("publishedAt") or paper.get("publishedAt") or ""
    submitted_daily = paper.get("submittedOnDailyAt") or ""

    # URL
    abs_url = f"https://arxiv.org/abs/{arxiv_id}"
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    html_url = abs_url

    # HF 独有字段
    upvotes = paper.get("upvotes") or 0
    github_repo = paper.get("githubRepo") or ""
    github_stars = paper.get("githubStars") or 0
    project_page = paper.get("projectPage") or ""
    thumbnail = raw.get("thumbnail") or ""
    ai_summary = paper.get("ai_summary") or ""
    ai_keywords = paper.get("ai_keywords") or []
    num_comments = raw.get("numComments") or 0

    # 构建 code_urls / project_urls
    code_urls = []
    project_urls = []
    if github_repo:
        code_urls.append(github_repo)
    if project_page:
        project_urls.append(project_page)

    return {
        "id": abs_url,
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": authors,
        "primary_category": None,
        "categories": [],
        "published": published,
        "updated": submitted_daily or published,
        "comments": "",
        "journal_ref": None,
        "venue_inferred": None,
        "summary": summary,
        "html_url": html_url,
        "pdf_url": pdf_url,
        "code_urls": code_urls,
        "project_urls": project_urls,
        "other_urls": [],
        # HF 独有
        "hf_upvotes": upvotes,
        "hf_source": source,
        "github_repo": github_repo,
        "github_stars": github_stars,
        "thumbnail": thumbnail,
        "ai_summary": ai_summary,
        "ai_keywords": ai_keywords,
        "hf_num_comments": num_comments,
    }


# ── 本地关键词打分 ───────────────────────────────────────────────────

def keyword_score(
    item: Dict[str, Any],
    keywords: List[str],
    *,
    upvote_weight: float = 0.5,
    star_weight: float = 0.3,
) -> float:
    """
    本地快速打分：关键词匹配 + HF upvotes + GitHub stars 加权。
    返回 0~100 分。

    - 关键词命中（title 权重 3x，summary 1x，ai_keywords 2x）→ 0~50 分
    - HF upvotes (log 缩放) → 0~30 分
    - GitHub stars (log 缩放) → 0~20 分
    """
    if not keywords:
        # 没有关键词则纯按社区热度
        return _community_score(item, upvote_weight=1.0, star_weight=0.5)

    title = (item.get("title") or "").lower()
    summary = (item.get("summary") or "").lower()
    ai_kw = " ".join(item.get("ai_keywords") or []).lower()
    ai_sum = (item.get("ai_summary") or "").lower()

    kw_score = 0.0
    max_per_kw = 50.0 / max(len(keywords), 1)

    for kw in keywords:
        kw_low = kw.lower().strip()
        if not kw_low:
            continue
        # 构建正则：支持连字符/空格变体
        pattern = re.escape(kw_low).replace(r"\ ", r"[\s\-]").replace(r"\-", r"[\s\-]")
        hit = 0.0
        if re.search(pattern, title):
            hit += 3.0
        if re.search(pattern, summary):
            hit += 1.0
        if re.search(pattern, ai_kw):
            hit += 2.0
        if re.search(pattern, ai_sum):
            hit += 1.0
        # 归一化单关键词得分
        kw_score += min(hit / 7.0 * max_per_kw, max_per_kw)

    community = _community_score(item, upvote_weight, star_weight)
    return min(kw_score + community, 100.0)


def _community_score(item: Dict[str, Any], upvote_weight: float, star_weight: float) -> float:
    """HF upvotes + GitHub stars 的社区热度分（0~50）"""
    import math
    upvotes = max(item.get("hf_upvotes") or 0, 0)
    stars = max(item.get("github_stars") or 0, 0)

    # log 缩放：upvotes 30 → ~10 分，100 → ~14，300 → ~17
    uv_score = math.log1p(upvotes) * 3.0  # log(1+x)*3
    st_score = math.log1p(stars) * 2.0

    uv_part = min(uv_score * upvote_weight, 30.0)
    st_part = min(st_score * star_weight, 20.0)
    return uv_part + st_part


def rank_and_filter(
    items: List[Dict[str, Any]],
    keywords: List[str],
    *,
    top_k: int = 30,
    upvote_weight: float = 0.5,
    star_weight: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    对候选论文进行本地关键词 + 社区热度打分，排序后返回 top_k。
    会把 local_score 注入每个 item。
    """
    for it in items:
        it["local_score"] = keyword_score(
            it, keywords,
            upvote_weight=upvote_weight,
            star_weight=star_weight,
        )

    items.sort(key=lambda x: x.get("local_score", 0), reverse=True)

    if top_k > 0:
        items = items[:top_k]

    if items:
        log_info(f"[HF] 本地打分完成，保留 top {len(items)} 篇")
        top3 = items[:3]
        for it in top3:
            log_debug(f"  [{it.get('local_score', 0):.1f}] {(it.get('title') or '')[:60]}")

    return items


# ── arXiv 元数据异步补全 ─────────────────────────────────────────────

ARXIV_API_URL = "https://export.arxiv.org/api/query"


def _fetch_arxiv_metadata(arxiv_id: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
    """
    通过 arXiv API 获取单篇论文的完整元数据。
    返回原始 XML 解析后的 item dict，或 None。
    """
    import feedparser
    from dateutil import parser as dtp
    from .extractors import extract_venue_info

    params = {
        "id_list": arxiv_id,
        "max_results": "1",
    }
    try:
        resp = requests.get(ARXIV_API_URL, params=params, timeout=timeout,
                            headers={"User-Agent": HF_UA})
        resp.raise_for_status()
    except Exception:
        return None

    feed = feedparser.parse(resp.text)
    if not feed.entries:
        return None

    e = feed.entries[0]
    authors = [a.get("name", "") for a in e.get("authors", [])] if "authors" in e else []

    # 机构信息：arXiv 有时在 author affiliations 里
    affiliations = []
    for a in e.get("authors", []):
        affs = a.get("arxiv_affiliations", [])
        if affs:
            affiliations.extend(affs)

    comments = getattr(e, "arxiv_comment", None) or ""
    journal_ref = getattr(e, "arxiv_journal_ref", None)
    primary_cat = getattr(getattr(e, "arxiv_primary_category", {}), "term", None) or None
    categories = [t.get("term") for t in e.get("tags", []) if t.get("term")]

    venue = extract_venue_info(f"{comments or ''} {journal_ref or ''}")

    published = e.get("published")
    updated = e.get("updated")
    published_iso = dtp.parse(published).isoformat() if published else None
    updated_iso = dtp.parse(updated).isoformat() if updated else None

    return {
        "authors": authors,
        "affiliations": affiliations,
        "primary_category": primary_cat,
        "categories": categories,
        "published": published_iso,
        "updated": updated_iso,
        "comments": comments,
        "journal_ref": journal_ref,
        "venue_inferred": venue,
    }


def augment_arxiv_metadata(
    items: List[Dict[str, Any]],
    *,
    max_workers: int = 8,
    timeout: int = 15,
    verbose: bool = False,
) -> None:
    """
    并发请求 arXiv API 补全元数据（作者、机构、分类、venue 等）。
    直接修改 items 列表中的字典。
    """
    if not items:
        return

    def _augment_one(item: Dict[str, Any]) -> Tuple[str, Optional[Dict]]:
        arxiv_id = item.get("arxiv_id") or ""
        if not arxiv_id:
            return (arxiv_id, None)
        # 限速：arXiv 建议间隔 3 秒，并发 8 个线程约需适度 sleep
        time.sleep(0.5)
        meta = _fetch_arxiv_metadata(arxiv_id, timeout=timeout)
        return (arxiv_id, meta)

    log_info(f"[arXiv] 开始补全 {len(items)} 篇论文的元数据...")
    success = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_augment_one, it): it for it in items}
        for fut in futures:
            item = futures[fut]
            try:
                arxiv_id, meta = fut.result(timeout=timeout + 10)
                if meta:
                    # 合并元数据，不覆盖已有非空字段
                    for key in ("authors", "primary_category", "categories",
                                "published", "updated", "comments",
                                "journal_ref", "venue_inferred"):
                        if meta.get(key) and not item.get(key):
                            item[key] = meta[key]
                    # affiliations 是新字段
                    if meta.get("affiliations"):
                        item["affiliations"] = meta["affiliations"]
                    success += 1
            except Exception as e:
                if verbose:
                    log_warn(f"[arXiv] 补全失败 {item.get('arxiv_id', '?')}: {e}")

    log_info(f"[arXiv] 元数据补全完成：{success}/{len(items)} 篇成功")


# ── 工具函数 ─────────────────────────────────────────────────────────

def _parse_iso(s: str) -> Optional[datetime]:
    """解析 ISO 时间字符串"""
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None
