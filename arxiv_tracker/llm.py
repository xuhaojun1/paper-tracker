# -*- coding: utf-8 -*-
import os, json, re, requests
from typing import Dict, Any, List

# ========== 通用小工具 ==========

def _json_loose(s: str) -> Dict[str, Any]:
    """
    宽松 JSON 解析：尽力从文本中抽出首个 {...} 为 JSON。
    """
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return {}
    raw = m.group(0)
    try:
        return json.loads(raw)
    except Exception:
        # 去掉尾随逗号等常见小问题再试一次
        t = re.sub(r",\s*([}\]])", r"\1", raw)
        try:
            return json.loads(t)
        except Exception:
            return {}

def _loose_json_load(s: str) -> Dict[str, Any]:
    """兼容旧名，等价 _json_loose。"""
    return _json_loose(s)

def _normalize_chat_endpoint(base_url: str) -> str:
    """
    允许三种写法：
      1) https://api.xxx.com
      2) https://api.xxx.com/v1
      3) https://api.xxx.com/v1/chat/completions
    统一规范到完整终点：.../v1/chat/completions
    """
    if not base_url:
        raise ValueError("llm.base_url is empty")
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"

def _chat_completions_request(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 1024,
    timeout: int = 30,
) -> str:
    """
    统一的 OpenAI 兼容 Chat Completions 请求（requests 直连）。
    适配 DeepSeek / SiliconFlow / 其他 OAI 兼容服务。
    """
    url = _normalize_chat_endpoint(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    # 标准 OAI 兼容返回
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        # 兜底：部分实现把文本放在 text
        return data.get("choices", [{}])[0].get("text", "")

# ========== 双语“一段话总结” ==========

def call_llm_bilingual_summary(
    item: Dict[str, Any],
    *,
    base_url: str,
    model: str,
    api_key: str,
    system_prompt_zh: str = "",
    system_prompt_en: str = ""
) -> Dict[str, str]:
    """
    结构化双语论文摘要：返回 motivation / method / experiments / limitations，
    每个字段包含 _en 和 _zh 两个版本。
    —— 统一 OpenAI 兼容通道，无需区分供应商。
    """
    title   = item.get("title") or ""
    summary = item.get("summary") or ""
    comments= item.get("comments") or ""
    venue   = item.get("venue_inferred") or (item.get("journal_ref") or "")

    sys_prompt = (
        "You are a concise AI research analyst. "
        "Extract KEY UNIQUE information for each dimension — do NOT repeat or paraphrase the same point across dimensions. "
        "Each field: strictly 1-2 sentences, information-dense, no filler."
    )

    user_payload = {
        "title": title,
        "abstract": summary,
        "venue_or_comments": (venue or comments or "")
    }

    schema_desc = (
        '{\n'
        '  "motivation_en": "(1-2 sentences) What specific problem/gap? Do NOT repeat method details.",\n'
        '  "method_en": "(1-2 sentences) Core technique, architecture name, key novelty. No motivation/results.",\n'
        '  "experiments_en": "(1-2 sentences) Benchmarks, metrics, key numbers if available. No method recap.",\n'
        '  "limitations_en": "(1 sentence) Main limitation or open question.",\n'
        '  "motivation_zh": "(motivation_en 的简体中文翻译)",\n'
        '  "method_zh": "(method_en 的简体中文翻译)",\n'
        '  "experiments_zh": "(experiments_en 的简体中文翻译)",\n'
        '  "limitations_zh": "(limitations_en 的简体中文翻译)"\n'
        '}'
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content":
            "Analyze this paper. Rules:\n"
            "1. Write English analysis FIRST (4 fields), each 1-2 sentences MAX.\n"
            "2. Then translate each English field to Simplified Chinese (4 _zh fields).\n"
            "3. Each dimension must contain DIFFERENT information — zero overlap.\n"
            "4. No links, no bullet lists, no markdown. Plain sentences only.\n"
            f"Return STRICT JSON:\n{schema_desc}\n\n"
            f"DATA:\n{json.dumps(user_payload, ensure_ascii=False)}"
        }
    ]

    text = _chat_completions_request(
        base_url=base_url, api_key=api_key, model=model, messages=messages,
        temperature=0.2, max_tokens=800
    )
    data = _json_loose(text)
    fields = ["motivation_en", "motivation_zh", "method_en", "method_zh",
              "experiments_en", "experiments_zh", "limitations_en", "limitations_zh"]
    return {k: (data.get(k) or "").strip() for k in fields}

# ========== LLM 预筛选：基于标题+摘要片段批量打分 ==========

def call_llm_filter_papers(
    items: List[Dict[str, Any]],
    keywords: List[str],
    *,
    base_url: str,
    model: str,
    api_key: str,
    top_k: int = 20,
    custom_prompt: str = "",
) -> List[str]:
    """
    批量发送论文标题+摘要片段给 LLM，返回最相关的论文 ID 列表。
    参数:
        items: arXiv 条目列表
        keywords: 用户关注的关键词列表
        top_k: 最多保留几篇
        custom_prompt: 用户自定义筛选 prompt（可选）
    返回:
        选中的 arXiv ID 列表
    """
    if not items:
        return []

    # 构造简短的论文列表（标题 + 摘要前 150 字）
    paper_list = []
    for i, it in enumerate(items):
        title = (it.get("title") or "").strip()
        abstract_short = (it.get("summary") or "")[:150].strip()
        sid = it.get("id") or f"unknown_{i}"
        paper_list.append(f"[{i}] id={sid}\n    title: {title}\n    abstract: {abstract_short}...")

    papers_text = "\n".join(paper_list)
    kw_text = ", ".join(keywords) if keywords else "general AI research"

    sys_prompt = (
        "You are a research paper relevance judge. "
        "Given a list of paper titles and abstract snippets, select the ones most relevant to the user's research interests. "
        "Be selective — only keep papers that are clearly relevant."
    )

    user_instruction = custom_prompt or (
        f"My research interests: {kw_text}\n\n"
        "Select the papers that are MOST relevant to my interests. "
        "A paper is relevant if its core contribution directly addresses one of my interest topics. "
        "Papers that only tangentially mention a keyword but focus on something else should be excluded.\n\n"
    )

    user_msg = (
        f"{user_instruction}"
        f"Papers ({len(items)} total):\n{papers_text}\n\n"
        f"Return ONLY a JSON array of the selected paper indices (0-based integers), e.g. [0, 2, 5].\n"
        f"Select at most {top_k} papers. If fewer are relevant, return fewer."
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg}
    ]

    text = _chat_completions_request(
        base_url=base_url, api_key=api_key, model=model, messages=messages,
        temperature=0.0, max_tokens=200
    )

    # 解析返回的 JSON 数组
    m = re.search(r"\[[\s\S]*?\]", text)
    if not m:
        # 解析失败则返回所有论文（不过滤）
        return [it.get("id", "") for it in items]
    try:
        indices = json.loads(m.group(0))
        selected_ids = []
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(items):
                sid = items[idx].get("id", "")
                if sid:
                    selected_ids.append(sid)
        return selected_ids if selected_ids else [it.get("id", "") for it in items]
    except Exception:
        return [it.get("id", "") for it in items]

# ========== 两阶段摘要（保留你原有接口与行为） ==========

def build_llm_prompt(item: Dict[str, Any], lang: str = "zh", scope: str = "both"):
    title   = item.get("title") or ""
    authors = ", ".join(item.get("authors") or [])
    venue   = item.get("venue_inferred") or (item.get("journal_ref") or "")
    comments = item.get("comments") or ""
    summary  = item.get("summary") or ""
    links = {
        "html": item.get("html_url"),
        "pdf": item.get("pdf_url"),
        "code": item.get("code_urls") or [],
        "project": item.get("project_urls") or [],
        "other": item.get("other_urls") or [],
    }
    meta = {
        "title": title, "authors": authors, "venue": venue,
        "comments": comments, "summary": summary, "links": links
    }
    ask_lang = "中文" if lang == "zh" else "English"
    user_prompt = f"""
请阅读以下论文元信息(JSON)，用{ask_lang}输出“两阶段摘要”：
1) TL;DR（1~2 句，先总后分，避免口号）
2) **Method Card**：任务/动机、核心方法、关键设计、数据与指标、主要结果与结论、局限与未来工作、保留链接（PDF/代码/项目页）
3) **Discussion Questions**：3~5 个高质量问题（可用于组会讨论）
请保留所有给定链接，不要臆造。scope="{scope}" 表示输出范围（tldr/full/both）。

JSON:
{json.dumps(meta, ensure_ascii=False, indent=2)}
""".strip()
    return user_prompt

def call_llm_two_stage(item: Dict[str, Any], lang: str, scope: str,
                       base_url: str, model: str, api_key: str,
                       system_prompt: str = "") -> Dict[str, str]:
    """
    兼容你原先的“两阶段摘要”接口，内部改为统一 OpenAI 兼容通道。
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": build_llm_prompt(item, lang=lang, scope=scope)})

    text = _chat_completions_request(
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
                t = ln.replace("TL;DR","").replace("TLDR","").replace("Tl;dr","")
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

# ========== 标题/摘要中文翻译 ==========

def call_llm_translate(item: Dict[str, Any], target_lang: str,
                       base_url: str, model: str, api_key: str,
                       system_prompt: str = "") -> Dict[str, str]:
    """
    返回：{ title_zh?, summary_zh?, comments_zh? }
    —— 同一 OpenAI 兼容通道，按任意 base_url + api_key 工作。
    """
    title   = item.get("title") or ""
    summary = item.get("summary") or ""
    comments= item.get("comments") or ""
    want_comments = bool(comments.strip())
    schema_keys = ["title_zh", "summary_zh"] + (["comments_zh"] if want_comments else [])

    sys_prompt = system_prompt or (
        "You are a precise academic translator. Translate to Simplified Chinese concisely and faithfully; keep technical terms."
    )
    inst = f"""
Translate the following fields into Simplified Chinese.
Return ONLY compact JSON with keys {schema_keys} (omit keys you can't translate).
Do not add commentary.

DATA:
{json.dumps({"title": title, "summary": summary, "comments": comments}, ensure_ascii=False, indent=2)}
""".strip()

    messages = [{"role":"system","content":sys_prompt},
                {"role":"user","content":inst}]
    text = _chat_completions_request(
        base_url=base_url, api_key=api_key, model=model, messages=messages,
        temperature=0.0, max_tokens=600
    ).strip()

    data = _loose_json_load(text)
    out: Dict[str, str] = {}
    if isinstance(data, dict):
        if "title_zh" in data and isinstance(data["title_zh"], str):
            out["title_zh"] = data["title_zh"].strip()
        if "summary_zh" in data and isinstance(data["summary_zh"], str):
            out["summary_zh"] = data["summary_zh"].strip()
        if "comments_zh" in data and isinstance(data["comments_zh"], str):
            out["comments_zh"] = data["comments_zh"].strip()
    return out
