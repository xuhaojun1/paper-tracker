# -*- coding: utf-8 -*-
"""
所有 LLM prompt 模板。纯字符串构造函数，无网络调用。
每个函数接收数据，返回 messages 列表（可直接传给 api_client.chat_completions）。
"""
import json
from typing import Dict, Any, List


# ========== 论文重要度打分 prompt ==========

def build_scoring_messages(
    papers_text: str,
    kw_text: str,
    batch_label: str,
    custom_prompt: str = "",
) -> List[Dict[str, str]]:
    """构造论文打分的 messages"""
    sys_prompt = (
        "You are a senior AI researcher screening papers for a weekly digest.\n"
        "The reader's core research directions are:\n"
        "  1) Video Generation & World Models — novel architectures, training paradigms, "
        "temporal consistency, physics-aware generation, interactive world simulation.\n"
        "  2) Vision-Language-Action (VLA) — models that jointly reason over vision, language, "
        "and robotic/embodied actions; multi-modal policy learning; sim-to-real.\n"
        "  3) 3D Reconstruction — neural 3D representations (NeRF, 3D Gaussian Splatting, VGGT), "
        "novel-view synthesis, large-scale scene reconstruction.\n\n"
        "Score each paper 1-10:\n"
        "- Relevance (40%): Does the paper's CORE contribution directly advance one of the 3 directions above? "
        "Merely mentioning a keyword in the abstract without substantial contribution to that direction → low relevance.\n"
        "- Novelty (30%): New architecture / framework / paradigm vs incremental or application-only work.\n"
        "- Impact (20%): Top-venue acceptance, broad applicability, strong quantitative gains.\n"
        "- Reproducibility (10%): Code released, clear setup.\n\n"
        "Scoring guide:\n"
        "  9-10: Directly advances a core direction with a major, novel contribution (e.g. new SOTA framework).\n"
        "  7-8: Solid contribution closely related to a core direction.\n"
        "  5-6: Tangentially related or moderate contribution.\n"
        "  1-4: Off-topic, purely application-level, or only superficially mentions keywords."
    )

    user_instruction = custom_prompt or (
        f"User keywords for reference: {kw_text}\n\n"
    )

    user_msg = (
        f"{user_instruction}"
        f"Papers ({batch_label}):\n{papers_text}\n\n"
        f"For each paper, output a JSON array of objects:\n"
        f'[{{"index": 0, "score": 8, "reason": "brief 1-sentence reason"}}, ...]\n'
        f"Return ONLY the JSON array, no other text."
    )

    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg},
    ]


# ========== 结构化中文摘要 prompt（纯 abstract 版）==========

_SUMMARY_SCHEMA = (
    '{\n'
    '  "motivation": "(1-2句) 这篇论文要解决什么具体问题/缺口？不要重复方法细节。",\n'
    '  "method": "(3-5句) 先讲数据流：输入是什么→经过哪些处理步骤→输出是什么；再讲关键组件：每个核心模块的名称和作用。不要笼统地说‘提出了一种新方法’，要写清楚具体做了什么。",\n'
    '  "experiments": "(1-2句) 基准测试、指标、关键数据（如有）。不要重复方法。",\n'
    '  "limitations": "(1句) 主要局限性或待解决的问题。"\n'
    '}'
)

def build_summary_messages(
    item: Dict[str, Any],
) -> List[Dict[str, str]]:
    """构造结构化中文摘要的 messages（基于 abstract）"""
    title = item.get("title") or ""
    summary = item.get("summary") or ""
    comments = item.get("comments") or ""
    venue = item.get("venue_inferred") or (item.get("journal_ref") or "")

    sys_prompt = (
        "你是一位精练的 AI 研究分析师。"
        "为每个维度提取关键独特信息——不同维度之间不要重复或复述相同内容。"
        "method 字段是最重要的，必须 3-5 句，先讲数据流（输入→处理步骤→输出），再讲关键组件的名称和作用。"
        "其他字段 1-2 句。信息密集，无废话。用简体中文输出。"
    )

    user_payload = {
        "title": title,
        "abstract": summary,
        "venue_or_comments": (venue or comments or "")
    }

    user_msg = (
        "分析这篇论文。规则：\n"
        "1. 用简体中文输出 4 个字段，每个 1-2 句。\n"
        "2. 每个维度必须包含不同信息——零重叠。\n"
        "3. 不要包含链接、列表、markdown。只用纯文本句子。\n"
        f"返回严格 JSON：\n{_SUMMARY_SCHEMA}\n\n"
        f"数据：\n{json.dumps(user_payload, ensure_ascii=False)}"
    )

    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg},
    ]


# ========== 基于 HTML 全文的高质量中文摘要 prompt ==========

_RICH_SCHEMA = (
    '{\n'
    '  "motivation": "(2-3句) 这篇论文要解决什么具体问题？现有方法为什么失败？",\n'
    '  "method": "(10句，这是最重要的字段) 分两步写：① 数据流——输入是什么，经过哪些处理步骤（按顺序），输出是什么；② 关键组件——列出每个核心模块的名称和它具体做了什么。禁止笼统描述，必须写出具体技术细节。",\n'
    '  "experiments": "(2-3句) 基准测试名称、对比基线、关键指标和数值。",\n'
    '  "limitations": "(1-2句) 主要局限性或待解决的问题。"\n'
    '}'
)

def build_rich_summary_messages(
    rich_context: str,
) -> List[Dict[str, str]]:
    """构造基于 HTML 全文的高质量中文摘要 messages"""
    sys_prompt = (
        "你是一位精练的 AI 研究分析师，可以读取论文全文（摘要、方法、实验等章节）。"
        "为每个维度提取关键独特信息——不同维度之间不要重复或复述相同内容。\n"
        "method 是最重要的字段，必须 10 句，分两步写：\n"
        "  第一步“数据流”：输入→各处理阶段（按顺序）→输出；\n"
        "  第二步“关键组件”：每个核心模块的名称和它具体做了什么。\n"
        "禁止笼统性描述如‘提出了一种新框架’‘该方法通过…’，必须写清楚具体技术细节。\n"
        "其他字段 2-3 句。信息密集，无废话。"
        "实验部分：包含具体基准测试名称、基线方法、关键量化结果。"
        "用简体中文输出。"
    )

    user_msg = (
        "使用提供的论文章节分析这篇论文。规则：\n"
        "1. 用简体中文输出 4 个字段。\n"
        "2. method 字段最重要，必须 10 句，分两步：先“数据流”（输入→处理步骤→输出），再“关键组件”（各模块名称+作用）。\n"
        "3. 每个维度必须包含不同信息——零重叠。\n"
        "4. 要具体：包含方法名、数据、基准测试名称。\n"
        "5. 不要包含链接、列表、markdown。只用纯文本句子。\n"
        f"返回严格 JSON：\n{_RICH_SCHEMA}\n\n"
        f"论文内容：\n{rich_context[:6000]}"
    )

    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg},
    ]


# ========== 翻译 prompt ==========

def build_translate_messages(
    item: Dict[str, Any],
    system_prompt: str = "",
) -> List[Dict[str, str]]:
    """构造翻译的 messages"""
    title = item.get("title") or ""
    summary = item.get("summary") or ""
    comments = item.get("comments") or ""
    want_comments = bool(comments.strip())
    schema_keys = ["title_zh", "summary_zh"] + (["comments_zh"] if want_comments else [])

    sys_prompt = system_prompt or (
        "You are a precise academic translator. Translate to Simplified Chinese concisely and faithfully; keep technical terms."
    )
    inst = (
        f"Translate the following fields into Simplified Chinese.\n"
        f"Return ONLY compact JSON with keys {schema_keys} (omit keys you can't translate).\n"
        f"Do not add commentary.\n\n"
        f"DATA:\n{json.dumps({'title': title, 'summary': summary, 'comments': comments}, ensure_ascii=False, indent=2)}"
    )

    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": inst},
    ]
