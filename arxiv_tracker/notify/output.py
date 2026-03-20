# -*- coding: utf-8 -*-
import os, json, datetime
from typing import List, Dict, Any, Optional

def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def save_json(items: List[Dict[str, Any]], out_dir: str) -> str:
    _ensure_dir(out_dir)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"arxiv_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return path

def _render_structured_analysis(summ: Optional[Dict[str, str]]) -> List[str]:
    """渲染结构化中文分析区块"""
    if not summ:
        return []
    dims = [
        ("研究动机", "motivation"),
        ("方法与架构", "method"),
        ("实验结果", "experiments"),
        ("局限性", "limitations"),
    ]
    has_any = any(summ.get(key) for _, key in dims)
    if not has_any:
        return []
    lines = ["", "**结构化分析**", ""]
    for label, key in dims:
        val = summ.get(key, "")
        if val:
            lines.append(f"**{label}**")
            lines.append(f"- {val}")
            lines.append("")
    return lines

def save_markdown(items: List[Dict[str, Any]], out_dir: str,
                  summaries_zh: Dict[str, Dict[str, str]] = None,
                  summaries_en: Dict[str, Dict[str, str]] = None,
                  lang: str = "both",
                  translations: Dict[str, Dict[str, str]] = None) -> str:
    _ensure_dir(out_dir)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"arxiv_{ts}.md")
    lines = ["# arXiv 检索结果 / Results", ""]
    for i, it in enumerate(items, 1):
        au = ", ".join(it.get("authors", []))
        title = it.get("title", "")
        venue = it.get("venue_inferred") or (it.get("journal_ref") or "")
        pub = it.get("published", "")
        upd = it.get("updated", "")
        score = it.get("importance_score")
        reason = it.get("importance_reason") or ""
        score_str = f" [★ {score}/10]" if score is not None else ""
        lines.append(f"## {i}.{score_str} {title}")
        if reason:
            lines.append(f"- **评分理由**：{reason}")
        lines.append(f"- Authors：{au}")
        if venue:
            lines.append(f"- Venue：{venue}")
        if it.get("comments"):
            lines.append(f"- Comments：{it['comments']}")
        lines.append(f"- First：{pub or '—'}；Latest：{upd or '—'}")
        if it.get("html_url"):
            lines.append(f"- Abs：{it['html_url']}")
        if it.get("pdf_url"):
            lines.append(f"- PDF：{it['pdf_url']}")
        if it.get("code_urls"):
            lines.append(f"- Code：{', '.join(it['code_urls'])}")
        if it.get("project_urls"):
            lines.append(f"- Project：{', '.join(it['project_urls'])}")

        sid = it.get("id") or ""
        # 中文翻译（标题/摘要）
        trans = translations.get(sid) if translations else None
        if trans:
            t_title = trans.get("title_zh")
            t_sum   = trans.get("summary_zh")
            if t_title or t_sum:
                lines.append("")
                lines.append("**中文翻译**")
                if t_title: lines.append(f"- 标题：{t_title}")
                if t_sum:   lines.append(f"- 摘要：{t_sum}")

        # 结构化分析（单个合并区块，不重复）
        summ = (summaries_zh or {}).get(sid) or (summaries_en or {}).get(sid)
        lines.extend(_render_structured_analysis(summ))
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
