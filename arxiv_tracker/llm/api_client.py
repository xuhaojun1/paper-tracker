# -*- coding: utf-8 -*-
"""
OpenAI 兼容 Chat Completions HTTP 客户端 + JSON 工具函数。
纯基础设施层，零业务逻辑。
"""
import json
import re
import requests
from typing import Dict, Any, List


def json_loose(s: str) -> Dict[str, Any]:
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


def normalize_chat_endpoint(base_url: str) -> str:
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


def chat_completions(
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
    返回 assistant 回复的纯文本。
    """
    url = normalize_chat_endpoint(base_url)
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
