# -*- coding: utf-8 -*-
"""
去重状态管理：load / save seen IDs。
从 pipeline.py 提取为独立模块。
"""
import os
import json
import pathlib
from typing import Set


def load_seen_ids(state_path: str) -> Set[str]:
    """读取已见 ID 集合（兼容 list / {"ids":[...]} / {id: timestamp} 三种格式）"""
    try:
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                j = json.load(f) or {}
                if isinstance(j, dict) and "ids" in j:
                    return set(j.get("ids") or [])
                elif isinstance(j, dict):
                    return set(j.keys())
                elif isinstance(j, list):
                    return set(j)
    except Exception:
        pass
    return set()


def save_seen_ids(state_path: str, seen_ids: Set[str]):
    """持久化去重状态"""
    p = pathlib.Path(state_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"ids": sorted(seen_ids)}, f, ensure_ascii=False, indent=2)
