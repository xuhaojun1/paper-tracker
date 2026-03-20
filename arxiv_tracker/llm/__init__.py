# -*- coding: utf-8 -*-
"""
LLM 交互层：打分 / 摘要 / 翻译。
"""
from .scoring import call_llm_score_papers
from .summary import call_llm_rich_summary, build_summary, heuristic_paragraphs
from .translate import call_llm_translate
from .api_client import chat_completions, json_loose

__all__ = [
    "call_llm_score_papers",
    "call_llm_rich_summary",
    "build_summary",
    "heuristic_paragraphs",
    "call_llm_translate",
    "chat_completions",
    "json_loose",
]
