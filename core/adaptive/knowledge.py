"""策略知识库与迁移推荐（FR-F4；DD-08 §6/§7）。

以 JSON 存档有效策略，签名为项目特征（语言 + 资产类型分布）的哈希；
相似项目可获得迁移推荐。
"""
from __future__ import annotations

import hashlib
import json
import os


def signature(language: str, assets: list[dict]) -> str:
    types = sorted(a.get("type", "?") for a in assets)
    raw = "%s|%s" % (language, ",".join(types))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("entries", [])


def save(path: str, entry: dict) -> None:
    """入库一条策略（含签名、得分、策略与指标）。"""
    entries = _load(path)
    entries = [e for e in entries if e.get("signature") != entry.get("signature")
               or e.get("seed") != entry.get("seed")]
    entries.append(entry)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"entries": entries}, fh, ensure_ascii=False, indent=2)


def recommend(path: str, sig: str) -> dict | None:
    """返回同签名中得分最高的一条（迁移推荐）。"""
    entries = [e for e in _load(path) if e.get("signature") == sig]
    if not entries:
        return None
    return max(entries, key=lambda e: e.get("fitness", 0.0))
