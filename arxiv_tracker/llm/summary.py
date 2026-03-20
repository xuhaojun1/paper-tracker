# -*- coding: utf-8 -*-
"""
摘要生成：结构化中文摘要（abstract 版 + HTML 全文版）+ 启发式兖底。
"""
import os
import re
from typing import Dict, Any, Optional

from .api_client import chat_completions, json_loose
from .prompts import build_summary_messages, build_rich_summary_messages


# ========== 结构化字段 ==========

_STRUCTURED_FIELDS = [
    "motivation", "method", "experiments", "limitations",
]


# ========== 启发式兜底（无 LLM 时）==========

def _first_sentence(text: str, max_chars=1024):
    """取第一句，尽量不截断；超过 max_chars 时裁剪"""
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?。！？])\s+", t)
    pick = parts[0] if parts else t
    return pick[:max_chars]


def heuristic_paragraphs(item: Dict[str, Any]) -> Dict[str, str]:
    """无 LLM 时的兜底：取摘要首句填入 motivation，其余留空"""
    absu = item.get("summary") or ""
    text = _first_sentence(absu) or (item.get("title") or "")
    out = {k: "" for k in _STRUCTURED_FIELDS}
    out["motivation"] = text
    return out


# ========== LLM 结构化摘要（基于 abstract）==========

def call_llm_summary(
    item: Dict[str, Any],
    *,
    base_url: str,
    model: str,
    api_key: str,
) -> Dict[str, str]:
    """
    结构化中文论文摘要：返回 motivation / method / experiments / limitations，
    统一中文输出。
    """
    messages = build_summary_messages(item)

    text = chat_completions(
        base_url=base_url, api_key=api_key, model=model, messages=messages,
        temperature=0.2, max_tokens=600
    )
    data = json_loose(text)
    return {k: (data.get(k) or "").strip() for k in _STRUCTURED_FIELDS}


# ========== LLM 高质量摘要（基于 HTML 全文）==========

def call_llm_rich_summary(
    item: Dict[str, Any],
    rich_context: str,
    *,
    base_url: str,
    model: str,
    api_key: str,
) -> Dict[str, str]:
    """
    基于 HTML 全文提取的富文本上下文，生成更高质量的结构化双语摘要。
    """
    messages = build_rich_summary_messages(rich_context)

    text = chat_completions(
        base_url=base_url, api_key=api_key, model=model, messages=messages,
        temperature=0.2, max_tokens=800, timeout=60
    )
    data = json_loose(text)
    return {k: (data.get(k) or "").strip() for k in _STRUCTURED_FIELDS}


# ========== 统一入口：基于 abstract 的摘要（LLM / 启发式兖底）==========

def build_summary(
    item: Dict[str, Any],
    mode: str = "llm",
    llm_cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    结构化中文摘要统一入口。
    mode="llm" 时调用 LLM，失败回退启发式兖底；其他 mode 直接用启发式。
    输出：{motivation, method, experiments, limitations}
    """
    if mode == "llm":
        cfg = llm_cfg or {}
        api_key = (cfg.get("api_key") or os.getenv(cfg.get("api_key_env") or "OPENAI_API_KEY", ""))
        if api_key:
            try:
                return call_llm_summary(
                    item=item,
                    base_url=cfg.get("base_url", ""),
                    model=cfg.get("model", ""),
                    api_key=api_key,
                )
            except Exception:
                pass
    return heuristic_paragraphs(item)
