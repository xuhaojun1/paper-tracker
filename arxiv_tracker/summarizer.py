# -*- coding: utf-8 -*-
import os, re
from typing import Dict, Any, Optional
from .llm import call_llm_two_stage
from .llm import call_llm_bilingual_summary

KNOWN_DATASETS = [
    "COCO","LVIS","ADE20K","Cityscapes","ScanNet","ImageNet","OpenImages",
    "Pascal VOC","NYUv2","KITTI","GQA","VQAv2","RefCOCO","RefCOCO+","RefCOCOg",
    "Flickr30k","SA-1B","LAION","Objects365","Waymo","nuScenes","COCO-Stuff"
]
TASK_HINTS = [
    ("open-vocabulary","Open-Vocabulary"),("open vocabulary","Open-Vocabulary"),
    ("segmentation","Segmentation"),("detection","Detection"),
    ("referring","Referring / Grounding"),("grounding","Grounding"),
    ("3d","3D Vision"),("multimodal","Vision-Language"),("vision-language","Vision-Language")
]

def _first_sentence(text: str, max_chars=1024):
    """取第一句，尽量不截断；超过 max_chars 时裁剪但不加 '…'。"""
    if not text: return ""
    t = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?。！？])\s+", t)
    pick = parts[0] if parts else t
    return pick[:max_chars]


_STRUCTURED_FIELDS = ["motivation_en", "motivation_zh", "method_en", "method_zh",
                      "experiments_en", "experiments_zh", "limitations_en", "limitations_zh"]

def heuristic_paragraphs(item: Dict[str, Any]) -> Dict[str, str]:
    # 无 LLM 时的兜底：英文取摘要首句填入 motivation_en，其余留空
    absu = item.get("summary") or ""
    en = _first_sentence(absu) or (item.get("title") or "")
    out = {k: "" for k in _STRUCTURED_FIELDS}
    out["motivation_en"] = en
    return out
    
def _detect(items, text):
    T = (text or "").lower()
    out = []
    for n in items:
        if n.lower() in T and n not in out:
            out.append(n)
    return out[:8]

def _detect_tasks(text, title="", comments=""):
    src = " ".join([title or "", text or "", comments or ""]).lower()
    out = []
    for k, lab in TASK_HINTS:
        if k in src and lab not in out:
            out.append(lab)
    return out[:6]

def heuristic_two_stage(item: Dict[str, Any], lang: str, scope: str) -> Dict[str, str]:
    title   = item.get("title") or ""
    summ    = item.get("summary") or ""
    comm    = item.get("comments") or ""
    venue   = item.get("venue_inferred") or (item.get("journal_ref") or "")
    pdf     = item.get("pdf_url") or ""
    absu    = item.get("html_url") or ""
    codes   = item.get("code_urls") or []
    projs   = item.get("project_urls") or []

    tasks = _detect_tasks(summ, title, comm)
    datasets = _detect(KNOWN_DATASETS, summ + " " + comm)

    tldr = _first_sentence(summ) or title

    # —— 只保留关键信息；不再输出 Links（网页和邮件已有独立的链接区）——
    lines = []
    if tasks:    lines.append("- **Task / Problem**: " + ", ".join(tasks))
    lines.append("- **Core Idea**: " + (_first_sentence(summ, 360) or title))
    if datasets: lines.append("- **Data / Benchmarks**: " + ", ".join(datasets))
    if venue:    lines.append("- **Venue**: " + venue)

    card = "\n".join(lines)
    disc = "\n".join([
        "1. 相比强基线，优势是否稳定显著？",
        "2. 代价/延迟与内存开销如何，复现细节是否充分？",
        "3. 失败模式与局限？可能改进方向？",
        "4. 数据与指标是否充分支撑结论，是否存在偏置/重叠？",
        "5. 是否可迁移到真实应用或边缘设备？"
    ])
    full_md = "**Method Card (方法卡)**\n" + card + "\n\n**Discussion (讨论问题)**\n" + disc

    if scope == "tldr": full_md = ""
    if scope == "full": tldr = ""
    return {"tldr": tldr, "full_md": full_md}

def llm_two_stage(item: Dict[str, Any], lang: str, scope: str, cfg: Dict[str, Any]) -> Dict[str, str]:
    api_key = (cfg.get("api_key") or
               os.getenv(cfg.get("api_key_env") or "OPENAI_API_KEY", ""))
    if not api_key:
        raise RuntimeError("未找到 LLM API Key，请设置环境变量：{}，或在 config.yaml 的 llm.api_key 填入（仅本机测试用）"
                           .format(cfg.get("api_key_env") or "OPENAI_API_KEY"))
    return call_llm_two_stage(
        item=item, lang=lang, scope=scope,
        base_url=cfg.get("base_url", ""),
        model=cfg.get("model", ""),
        api_key=api_key,
        system_prompt=cfg.get("system_prompt_zh" if lang == "zh" else "system_prompt_en", "")
    )

def build_two_stage_summary(item: Dict[str, Any], mode: str, lang: str, scope: str, llm_cfg: Optional[Dict[str, Any]] = None):
    """
    结构化双语摘要，输出 8 个字段：
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
                data = call_llm_bilingual_summary(
                    item=item,
                    base_url=cfg.get("base_url", ""),
                    model=cfg.get("model", ""),
                    api_key=api_key,
                    system_prompt_zh=cfg.get("system_prompt_zh", ""),
                    system_prompt_en=cfg.get("system_prompt_en", "")
                )
                return _wrap(data)
            except Exception:
                pass
        return _wrap(heuristic_paragraphs(item))

    return _wrap(heuristic_paragraphs(item))
