# -*- coding: utf-8 -*-
"""
论文搜索与获取：arXiv API 查询、Feed 解析、链接补全、HTML 全文抓取。
"""
from .query import build_search_query
from .client import fetch_arxiv_feed
from .parser import parse_feed
from .scraper import augment_item_links
from .html_fetcher import fetch_paper_sections, get_rich_context
from .extractors import extract_venue_info, extract_urls

__all__ = [
    "build_search_query",
    "fetch_arxiv_feed",
    "parse_feed",
    "augment_item_links",
    "fetch_paper_sections",
    "get_rich_context",
    "extract_venue_info",
    "extract_urls",
]
