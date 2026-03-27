# -*- coding: utf-8 -*-
"""
论文搜索与获取：HuggingFace 社区热门 + arXiv API 元数据补全、链接补全、HTML 全文抓取。
"""
from .query import build_search_query
from .client import fetch_arxiv_feed
from .parser import parse_feed
from .scraper import augment_item_links
from .html_fetcher import fetch_paper_sections, get_rich_context
from .extractors import extract_venue_info, extract_urls
from .hf_client import (
    fetch_hf_papers,
    rank_and_filter,
    keyword_score,
    augment_arxiv_metadata,
)

__all__ = [
    "build_search_query",
    "fetch_arxiv_feed",
    "parse_feed",
    "augment_item_links",
    "fetch_paper_sections",
    "get_rich_context",
    "extract_venue_info",
    "extract_urls",
    # HuggingFace 源
    "fetch_hf_papers",
    "rank_and_filter",
    "keyword_score",
    "augment_arxiv_metadata",
]
