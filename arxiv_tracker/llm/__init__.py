# -*- coding: utf-8 -*-
"""
LLM 交互层：打分 / 摘要 / 翻译。
重新导出所有公开 API，保持外部 import 简洁。
"""
from .scoring import call_llm_score_papers, call_llm_filter_papers
from .summary import (
    call_llm_summary,
    call_llm_rich_summary,
    call_llm_two_stage,
    build_two_stage_summary,
    heuristic_paragraphs,
)
from .translate import call_llm_translate
from .api_client import chat_completions, json_loose

__all__ = [
    "call_llm_score_papers",
    "call_llm_filter_papers",
    "call_llm_summary",
    "call_llm_rich_summary",
    "call_llm_two_stage",
    "build_two_stage_summary",
    "heuristic_paragraphs",
    "call_llm_translate",
    "chat_completions",
    "json_loose",
]
