# -*- coding: utf-8 -*-
"""
标题/摘要中文翻译。
"""
from typing import Dict, Any

from .api_client import chat_completions, json_loose
from .prompts import build_translate_messages


def call_llm_translate(
    item: Dict[str, Any],
    target_lang: str,
    base_url: str,
    model: str,
    api_key: str,
    system_prompt: str = "",
) -> Dict[str, str]:
    """
    返回：{ title_zh?, summary_zh?, comments_zh? }
    """
    messages = build_translate_messages(item, system_prompt=system_prompt)

    text = chat_completions(
        base_url=base_url, api_key=api_key, model=model, messages=messages,
        temperature=0.0, max_tokens=600
    ).strip()

    data = json_loose(text)
    out: Dict[str, str] = {}
    if isinstance(data, dict):
        if "title_zh" in data and isinstance(data["title_zh"], str):
            out["title_zh"] = data["title_zh"].strip()
        if "summary_zh" in data and isinstance(data["summary_zh"], str):
            out["summary_zh"] = data["summary_zh"].strip()
        if "comments_zh" in data and isinstance(data["comments_zh"], str):
            out["comments_zh"] = data["comments_zh"].strip()
    return out
