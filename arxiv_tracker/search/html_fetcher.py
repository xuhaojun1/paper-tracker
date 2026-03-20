# -*- coding: utf-8 -*-
"""
抓取 arXiv 论文的 HTML 全文页面，提取 Abstract / Method / Experiment 等关键章节内容。
用于给 LLM 提供比纯摘要更丰富的上下文，提升打分和总结质量。
"""
import re
import requests
from typing import Dict, Optional

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

# arXiv HTML 页面的 URL 格式：https://arxiv.org/html/2401.12345v1
_ABS_TO_HTML_RE = re.compile(r"https?://arxiv\.org/abs/(\d+\.\d+)(v\d+)?")

# 需要提取的章节关键词（按优先级）
_SECTION_KEYWORDS = {
    "abstract": [r"abstract"],
    "introduction": [r"introduction"],
    "method": [
        r"method(?:s|ology)?",
        r"approach",
        r"framework",
        r"model(?:\s+architecture)?",
        r"proposed\s+(?:method|approach|framework)",
        r"technical\s+approach",
        r"our\s+(?:method|approach)",
    ],
    "experiment": [
        r"experiment(?:s|al)?(?:\s+result(?:s)?)?",
        r"evaluation",
        r"result(?:s)?(?:\s+and\s+(?:discussion|analysis))?",
        r"empirical\s+(?:study|evaluation|result)",
        r"quantitative\s+(?:result|evaluation)",
        r"comparison",
    ],
    "conclusion": [r"conclusion(?:s)?(?:\s+and\s+future\s+work)?", r"summary"],
}

# HTML 标签清理正则
_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"\s+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def _clean_html(html_text: str) -> str:
    """去除 HTML 标签，保留纯文本"""
    text = _TAG_RE.sub(" ", html_text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def _abs_url_to_html_url(abs_url: str) -> Optional[str]:
    """将 arXiv abs URL 转换为 HTML 全文 URL"""
    if not abs_url:
        return None
    m = _ABS_TO_HTML_RE.search(abs_url)
    if m:
        arxiv_id = m.group(1)
        version = m.group(2) or ""
        return f"https://arxiv.org/html/{arxiv_id}{version}"
    # 兜底：直接替换 /abs/ -> /html/
    if "/abs/" in abs_url:
        return abs_url.replace("/abs/", "/html/", 1)
    return None


def _fetch_html_page(url: str, timeout: int = 15) -> Optional[str]:
    """获取 HTML 页面内容"""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": UA, "Accept": "text/html,*/*"},
            timeout=timeout,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception:
        return None


def _extract_sections(html_content: str) -> Dict[str, str]:
    """
    从 arXiv HTML 页面中提取各个章节。
    arXiv HTML 页面使用 <section> 标签或 <h2>/<h3> 来分隔章节。
    """
    sections: Dict[str, str] = {}

    # 策略 1：按 <section> 标签分割（arXiv HTML5 格式）
    section_blocks = re.findall(
        r"<section[^>]*>([\s\S]*?)</section>", html_content, re.IGNORECASE
    )

    # 策略 2：按 <h2> 标签分割（如果 section 标签不够）
    if len(section_blocks) < 3:
        section_blocks = re.split(r"<h[23][^>]*>", html_content)

    for block in section_blocks:
        # 从块的开头提取标题
        heading_match = re.search(
            r"<(?:h[1-6]|span|div)[^>]*class=[\"'][^\"']*(?:title|heading|ltx_title)[^\"']*[\"'][^>]*>([\s\S]*?)</(?:h[1-6]|span|div)>",
            block[:500],
            re.IGNORECASE,
        )
        if not heading_match:
            heading_match = re.search(r"^([\s\S]{0,200}?)(?:<p|<div)", block, re.IGNORECASE)

        if not heading_match:
            continue

        heading_text = _clean_html(heading_match.group(1)).strip().lower()

        # 匹配章节类型
        for section_type, patterns in _SECTION_KEYWORDS.items():
            for pat in patterns:
                if re.search(pat, heading_text, re.IGNORECASE):
                    # 提取正文内容
                    body_text = _clean_html(block)
                    # 限制每个章节最大字符数，避免过长
                    max_chars = 3000 if section_type == "method" else 2000
                    if len(body_text) > max_chars:
                        body_text = body_text[:max_chars] + "..."
                    if section_type not in sections or len(body_text) > len(sections[section_type]):
                        sections[section_type] = body_text
                    break

    return sections


def fetch_paper_sections(
    item: dict, timeout: int = 15
) -> Dict[str, str]:
    """
    抓取论文的 HTML 全文并提取关键章节。

    参数:
        item: arXiv 条目字典（需要 html_url 或 id 字段）
        timeout: HTTP 请求超时（秒）

    返回:
        {
            "abstract": "...",
            "introduction": "...",
            "method": "...",
            "experiment": "...",
            "conclusion": "...",
            "full_text_available": True/False
        }
    """
    result = {"full_text_available": False}

    # 确定 HTML URL
    abs_url = item.get("html_url") or item.get("id") or ""
    html_url = _abs_url_to_html_url(abs_url)
    if not html_url:
        return result

    # 抓取 HTML
    html_content = _fetch_html_page(html_url, timeout=timeout)
    if not html_content:
        return result

    # 提取各章节
    sections = _extract_sections(html_content)
    if sections:
        result["full_text_available"] = True
        result.update(sections)

    return result


def get_rich_context(item: dict, timeout: int = 15) -> str:
    """
    获取论文的富文本上下文，用于 LLM 打分和总结。
    优先使用 HTML 全文章节；不可用时回退到 abstract。

    返回格式化的文本字符串，可直接嵌入 LLM prompt。
    """
    sections = fetch_paper_sections(item, timeout=timeout)

    parts = []
    title = (item.get("title") or "").strip()
    if title:
        parts.append(f"Title: {title}")

    comments = (item.get("comments") or "").strip()
    if comments:
        parts.append(f"Comments: {comments}")

    venue = item.get("venue_inferred") or (item.get("journal_ref") or "")
    if venue:
        parts.append(f"Venue: {venue}")

    if sections.get("full_text_available"):
        # 使用 HTML 全文章节
        if sections.get("abstract"):
            parts.append(f"\n[Abstract]\n{sections['abstract']}")
        if sections.get("introduction"):
            parts.append(f"\n[Introduction]\n{sections['introduction']}")
        if sections.get("method"):
            parts.append(f"\n[Method]\n{sections['method']}")
        if sections.get("experiment"):
            parts.append(f"\n[Experiments]\n{sections['experiment']}")
        if sections.get("conclusion"):
            parts.append(f"\n[Conclusion]\n{sections['conclusion']}")
    else:
        # 回退到 abstract
        abstract = (item.get("summary") or "").strip()
        if abstract:
            parts.append(f"\n[Abstract]\n{abstract}")

    return "\n".join(parts)
