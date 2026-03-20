# -*- coding: utf-8 -*-
"""
摘要生成：结构化双语摘要（abstract 版 + HTML 全文版）+ 两阶段摘要 + 启发式兜底。
合并了原 summarizer.py 的逻辑。
"""
import os
import re
from typing import Dict, Any, Optional

from .api_client import chat_completions, json_loose
from .prompts import (
    build_summary_messages,
    build_rich_summary_messages,
    build_two_stage_prompt,
)


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


# ========== LLM 结构化双语摘要（基于 abstract）==========

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


# ========== 两阶段摘要（旧接口兼容）==========

def call_llm_two_stage(
    item: Dict[str, Any], lang: str, scope: str,
    base_url: str, model: str, api_key: str,
    system_prompt: str = "",
) -> Dict[str, str]:
    """兼容原先的"两阶段摘要"接口"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": build_two_stage_prompt(item, lang=lang, scope=scope)})

    text = chat_completions(
        base_url=base_url, api_key=api_key, model=model, messages=messages,
        temperature=0.2, max_tokens=900
    ).strip()

    tldr, full_md = "", ""
    if "TL;DR" in text or "TLDR" in text or "Tl;dr" in text:
        parts = text.splitlines()
        tldr_lines, rest_lines, in_tldr = [], [], False
        for ln in parts:
            if "TL;DR" in ln or "TLDR" in ln or "Tl;dr" in ln:
                in_tldr = True
                t = ln.replace("TL;DR", "").replace("TLDR", "").replace("Tl;dr", "")
                tldr_lines.append(t.strip(" :："))
            elif in_tldr and (ln.strip().startswith("**Method") or ln.strip().lower().startswith("**discussion")):
                in_tldr = False
                rest_lines.append(ln)
            elif in_tldr:
                tldr_lines.append(ln)
            else:
                rest_lines.append(ln)
        tldr = " ".join([s.strip() for s in tldr_lines if s.strip()])
        full_md = "\n".join(rest_lines).strip()
    else:
        full_md = text
    return {"tldr": tldr, "full_md": full_md}


# ========== 统一入口：build_two_stage_summary ==========

def build_two_stage_summary(
    item: Dict[str, Any],
    mode: str,
    lang: str,
    scope: str,
    llm_cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    结构化双语摘要统一入口，输出 8 个字段：
      motivation_en/zh, method_en/zh, experiments_en/zh, limitations_en/zh
    兼容旧字段 tldr/full_md（留空）。
    """
    def _wrap(data: Dict[str, str]) -> Dict[str, str]:
        out = {k: data.get(k, "") for k in _STRUCTURED_FIELDS}
        out["tldr"] = ""
        out["full_md"] = ""
        return out

    if mode == "llm":
        cfg = llm_cfg or {}
        api_key = (cfg.get("api_key") or os.getenv(cfg.get("api_key_env") or "OPENAI_API_KEY", ""))
        if api_key:
            try:
                data = call_llm_summary(
                    item=item,
                    base_url=cfg.get("base_url", ""),
                    model=cfg.get("model", ""),
                    api_key=api_key,
                )
                return _wrap(data)
            except Exception:
                pass
        return _wrap(heuristic_paragraphs(item))

    return _wrap(heuristic_paragraphs(item))
