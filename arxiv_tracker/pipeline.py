# -*- coding: utf-8 -*-
"""
核心工作流管线：搜索 → 补链 → LLM 打分 → HTML 全文抓取 → LLM 摘要 → 翻译。
从 cli.py 拆分出来，便于测试和维护。
"""
import os
import json
import re
import pathlib
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Set, Tuple

from .search import build_search_query, fetch_arxiv_feed, parse_feed, get_rich_context
from .search.scraper import augment_item_links
from .llm import call_llm_translate, call_llm_score_papers, call_llm_rich_summary, build_two_stage_summary
from .utils.logging import log_info, log_warn, log_error, log_debug
from .utils.state import load_seen_ids, save_seen_ids


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def fetch_papers(
    cfg,
    raw_cfg: Dict[str, Any],
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    """
    阶段 1：arXiv API 搜索 + 分页 + 时间窗 + 去重。
    返回候选论文列表。
    """
    q = build_search_query(cfg.categories, cfg.keywords, cfg.exclude_keywords, cfg.logic)
    log_info(f"[Query] {q}")

    fresh_cfg = raw_cfg.get("freshness") or {}
    since_days = int(fresh_cfg.get("since_days", 0) or 0)
    unique_only = bool(fresh_cfg.get("unique_only", False))
    state_path = fresh_cfg.get("state_path", ".state/seen.json")
    fallback_when_empty = bool(fresh_cfg.get("fallback_when_empty", False))

    seen_ids = load_seen_ids(state_path) if unique_only and state_path else set()
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days) if since_days > 0 else None
    want_new = int(cfg.max_results or 200)

    page_size = min(200, max(25, want_new))
    max_pages = 20
    start = 0
    collected, reached_cutoff = [], False

    for _page in range(max_pages):
        xml = fetch_arxiv_feed(
            q, start=start, max_results=page_size,
            sort_by=cfg.sort_by, sort_order=cfg.sort_order
        )
        page_items = parse_feed(xml) or []
        if not page_items:
            break

        for it in page_items:
            t = _parse_dt(it.get("updated")) or _parse_dt(it.get("published"))
            if cutoff and t and t < cutoff:
                reached_cutoff = True
                break
            aid = it.get("id")
            if unique_only and aid and aid in seen_ids:
                continue
            collected.append(it)
            if len(collected) >= want_new:
                break

        if len(collected) >= want_new or reached_cutoff:
            break
        if len(page_items) < page_size:
            break
        start += page_size

    if not collected and fallback_when_empty:
        xml = fetch_arxiv_feed(
            q, start=0, max_results=want_new,
            sort_by=cfg.sort_by, sort_order=cfg.sort_order
        )
        collected = parse_feed(xml) or []

    if not collected:
        log_warn("[Info] No new items after pagination/freshness/dedup filter.")
    else:
        log_info(f"[Info] Fetched {len(collected)} new item(s) after pagination/dedup.")

    return collected


def augment_links(
    items: List[Dict[str, Any]],
    raw_cfg: Dict[str, Any],
    verbose: bool = False,
):
    """阶段 2：补全代码/项目链接（HTML 页 + PDF 兜底）"""
    scrape_cfg = raw_cfg.get("scrape") or {}
    scrape_html = bool(scrape_cfg.get("html", True))
    scrape_pdf_if_missing = bool(scrape_cfg.get("pdf_if_missing", True))
    scrape_pdf_always = bool(scrape_cfg.get("pdf_first_page", False))
    scrape_to = int(scrape_cfg.get("timeout", 10))

    if verbose:
        log_debug(f"[Scrape] html={scrape_html} pdf_if_missing={scrape_pdf_if_missing} "
                  f"pdf_first_page={scrape_pdf_always} timeout={scrape_to}")

    for it in items:
        try:
            added = augment_item_links(
                it,
                html=scrape_html,
                pdf_if_missing=scrape_pdf_if_missing,
                pdf_first_page=scrape_pdf_always,
                timeout=scrape_to,
            )
            if verbose and added > 0:
                log_debug(f"[Scrape] +{added} code link(s) for {(it.get('id') or '')[:32]}")
        except Exception as e:
            log_warn(f"[Scrape] 补链失败 {(it.get('id') or '')[:18]}...: {e}")


def score_and_filter(
    items: List[Dict[str, Any]],
    raw_cfg: Dict[str, Any],
    verbose: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    阶段 3：LLM 重要度打分 + 按分数排序 + 截取 top_k。
    返回: (排序后的 items 列表, {id: {"score": N, "reason": "..."}} 映射)
    """
    llm_cfg = raw_cfg.get("llm") or {}
    filter_cfg = raw_cfg.get("filter") or {}
    filter_enabled = bool(filter_cfg.get("enabled", False))

    if not filter_enabled or not items:
        return items, {}

    api_key = (llm_cfg.get("api_key")
               or os.getenv(llm_cfg.get("api_key_env") or "OPENAI_API_KEY", ""))
    if not api_key:
        log_warn("[Score] 跳过：未找到 LLM API Key")
        return items, {}

    top_k = int(filter_cfg.get("top_k", 50))
    custom_prompt = filter_cfg.get("prompt", "")
    kw_list = raw_cfg.get("keywords", [])

    try:
        scored = call_llm_score_papers(
            items=items, keywords=kw_list,
            base_url=llm_cfg.get("base_url", ""),
            model=llm_cfg.get("model", ""),
            api_key=api_key,
            top_k=top_k,
            custom_prompt=custom_prompt,
        )
        log_info(f"[Score] LLM 打分完成：{len(items)} 篇 → 保留 {len(scored)} 篇")

        # 构建 score 映射
        score_map = {s["id"]: {"score": s["score"], "reason": s["reason"]} for s in scored}

        # 按分数排序重建 items 列表
        id_to_item = {it.get("id"): it for it in items}
        sorted_items = []
        for s in scored:
            it = id_to_item.get(s["id"])
            if it:
                # 将 score 信息注入 item
                it["importance_score"] = s["score"]
                it["importance_reason"] = s["reason"]
                sorted_items.append(it)

        if verbose:
            for s in scored[:5]:
                log_debug(f"  [{s['score']:2d}] {id_to_item.get(s['id'], {}).get('title', '?')[:60]}")
                log_debug(f"       {s['reason']}")

        return sorted_items, score_map
    except Exception as e:
        log_warn(f"[Score] LLM 打分失败，跳过筛选：{e}")
        return items, {}


def fetch_html_content(
    items: List[Dict[str, Any]],
    raw_cfg: Dict[str, Any],
    verbose: bool = False,
) -> Dict[str, str]:
    """
    阶段 3.5：抓取 arxiv HTML 全文，提取关键章节。
    返回: {arxiv_id: rich_context_text}
    """
    scrape_cfg = raw_cfg.get("scrape") or {}
    html_fulltext = bool(scrape_cfg.get("html_fulltext", True))
    html_timeout = int(scrape_cfg.get("html_fulltext_timeout", 15))

    if not html_fulltext:
        return {}

    rich_contexts: Dict[str, str] = {}
    total = len(items)
    success = 0

    for i, it in enumerate(items):
        sid = it.get("id") or ""
        if verbose and i % 10 == 0:
            log_debug(f"[HTML] 抓取论文全文 {i+1}/{total}...")
        try:
            ctx = get_rich_context(it, timeout=html_timeout)
            if ctx and len(ctx) > 200:  # 有实质内容
                rich_contexts[sid] = ctx
                success += 1
        except Exception as e:
            if verbose:
                log_warn(f"[HTML] 抓取失败 {sid[:18]}...: {e}")

    log_info(f"[HTML] 全文抓取完成：{success}/{total} 篇成功")
    return rich_contexts


def generate_summaries(
    items: List[Dict[str, Any]],
    rich_contexts: Dict[str, str],
    raw_cfg: Dict[str, Any],
    mode: str = "llm",
    lang: str = "both",
    scope: str = "both",
    verbose: bool = False,
) -> Dict[str, Dict[str, str]]:
    """
    阶段 4：为选中的论文生成结构化摘要。
    优先使用 HTML 全文上下文；不可用时回退到纯 abstract。
    """
    llm_cfg = raw_cfg.get("llm") or {}
    summaries: Dict[str, Dict[str, str]] = {}

    api_key = (llm_cfg.get("api_key")
               or os.getenv(llm_cfg.get("api_key_env") or "OPENAI_API_KEY", ""))

    for i, it in enumerate(items):
        sid = it.get("id") or ""
        title_short = (it.get("title") or "")[:50]

        if mode == "llm" and api_key:
            rich_ctx = rich_contexts.get(sid, "")
            try:
                if rich_ctx and len(rich_ctx) > 300:
                    # 使用 HTML 全文版本
                    data = call_llm_rich_summary(
                        item=it, rich_context=rich_ctx,
                        base_url=llm_cfg.get("base_url", ""),
                        model=llm_cfg.get("model", ""),
                        api_key=api_key,
                    )
                    if verbose:
                        log_debug(f"[Summary] {i+1}/{len(items)} (rich) {title_short}...")
                else:
                    # 回退到纯 abstract 版本
                    data = build_two_stage_summary(
                        item=it, mode=mode, lang=lang, scope=scope, llm_cfg=llm_cfg
                    )
                    if verbose:
                        log_debug(f"[Summary] {i+1}/{len(items)} (abstract) {title_short}...")

                summaries[sid] = data
            except Exception as e:
                log_warn(f"[Summary] 失败 {sid[:18]}...: {e}")
                summaries[sid] = build_two_stage_summary(
                    item=it, mode="heuristic", lang=lang, scope=scope
                )
        else:
            summaries[sid] = build_two_stage_summary(
                item=it, mode=mode, lang=lang, scope=scope, llm_cfg=llm_cfg
            )

    return summaries


def translate_items(
    items: List[Dict[str, Any]],
    raw_cfg: Dict[str, Any],
    trans_cfg: Dict[str, Any],
    verbose: bool = False,
) -> Dict[str, Dict[str, str]]:
    """阶段 5：中文翻译"""
    llm_cfg = raw_cfg.get("llm") or {}
    translations: Dict[str, Dict[str, str]] = {}

    if not trans_cfg.get("enabled"):
        return translations
    if trans_cfg.get("lang", "zh") != "zh":
        return translations

    api_key = (llm_cfg.get("api_key")
               or os.getenv(llm_cfg.get("api_key_env") or "OPENAI_API_KEY", ""))
    if not api_key:
        log_warn("[Translate] 跳过：未找到 LLM API Key")
        return translations

    for it in items:
        sid = it.get("id") or ""
        try:
            translations[sid] = call_llm_translate(
                item=it, target_lang="zh",
                base_url=llm_cfg.get("base_url", ""),
                model=llm_cfg.get("model", ""),
                api_key=api_key,
                system_prompt=llm_cfg.get("system_prompt_translate_zh", "")
            )
        except Exception as e:
            log_error(f"[Translate] 失败 {sid[:18]}...: {e}")

    return translations
