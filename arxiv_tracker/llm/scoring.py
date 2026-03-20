# -*- coding: utf-8 -*-
"""
论文重要度打分：基于标题+摘要批量评分（1-10），按分数排序返回。
"""
import json
import re
from typing import Dict, Any, List

from .api_client import chat_completions
from .prompts import build_scoring_messages


def call_llm_score_papers(
    items: List[Dict[str, Any]],
    keywords: List[str],
    *,
    base_url: str,
    model: str,
    api_key: str,
    top_k: int = 50,
    custom_prompt: str = "",
    batch_size: int = 25,
) -> List[Dict[str, Any]]:
    """
    批量发送论文标题+摘要给 LLM，为每篇论文打重要度分数(1-10)。
    评分维度：
      - 方法创新性（method novelty）
      - 领域相关性（relevance to user interests）
      - 影响力指标（是否被顶会接收、适用范围）
    参数:
        items: arXiv 条目列表
        keywords: 用户关注的关键词列表
        top_k: 最多保留几篇
        custom_prompt: 用户自定义筛选 prompt（可选）
        batch_size: 每批处理的论文数（控制 token 长度）
    返回:
        排好序的结果列表 [{"id": ..., "score": 1-10, "reason": "..."}]
    """
    if not items:
        return []

    all_scores: List[Dict[str, Any]] = []
    kw_text = ", ".join(keywords) if keywords else "general AI research"

    # 分批处理，避免单次请求 token 过长
    for batch_start in range(0, len(items), batch_size):
        batch = items[batch_start:batch_start + batch_size]
        paper_list = []
        for i, it in enumerate(batch):
            idx = batch_start + i
            title = (it.get("title") or "").strip()
            abstract = (it.get("summary") or "")[:300].strip()
            comments = (it.get("comments") or "").strip()
            venue = it.get("venue_inferred") or (it.get("journal_ref") or "")
            meta_parts = [f"[{idx}] title: {title}"]
            if venue:
                meta_parts.append(f"    venue: {venue}")
            if comments:
                meta_parts.append(f"    comments: {comments}")
            meta_parts.append(f"    abstract: {abstract}")
            paper_list.append("\n".join(meta_parts))

        papers_text = "\n\n".join(paper_list)
        batch_label = f"batch {batch_start // batch_size + 1}"

        messages = build_scoring_messages(
            papers_text=papers_text,
            kw_text=kw_text,
            batch_label=batch_label,
            custom_prompt=custom_prompt,
        )

        try:
            text = chat_completions(
                base_url=base_url, api_key=api_key, model=model, messages=messages,
                temperature=0.0, max_tokens=2000, timeout=60
            )

            # 解析返回的 JSON 数组
            m = re.search(r"\[\s*\{[\s\S]*\}\s*\]", text)
            if m:
                scored = json.loads(m.group(0))
                for entry in scored:
                    idx = entry.get("index")
                    if isinstance(idx, int) and 0 <= idx < len(items):
                        all_scores.append({
                            "id": items[idx].get("id", ""),
                            "score": min(10, max(1, int(entry.get("score", 5)))),
                            "reason": (entry.get("reason") or "").strip(),
                        })
        except Exception:
            # 此批次失败，给默认分 5
            for it in batch:
                all_scores.append({
                    "id": it.get("id", ""),
                    "score": 5,
                    "reason": "(scoring failed for this batch)",
                })

    # 补全未打分的论文（给默认分 5）
    scored_ids = {s["id"] for s in all_scores}
    for it in items:
        sid = it.get("id", "")
        if sid and sid not in scored_ids:
            all_scores.append({"id": sid, "score": 5, "reason": "(not scored)"})

    # 按分数降序排列
    all_scores.sort(key=lambda x: x["score"], reverse=True)

    # 截取 top_k
    return all_scores[:top_k]


# 向后兼容旧接口（返回 ID 列表）
def call_llm_filter_papers(
    items: List[Dict[str, Any]],
    keywords: List[str],
    *,
    base_url: str,
    model: str,
    api_key: str,
    top_k: int = 50,
    custom_prompt: str = "",
) -> List[str]:
    """向后兼容：返回选中的 arXiv ID 列表"""
    scored = call_llm_score_papers(
        items=items, keywords=keywords,
        base_url=base_url, model=model, api_key=api_key,
        top_k=top_k, custom_prompt=custom_prompt,
    )
    return [s["id"] for s in scored]
