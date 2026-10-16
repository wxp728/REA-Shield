"""独立会话攻击编排（FR-E3；判定口径见 `docs/design/ddd/decisions/OI-07-rea-success-criteria.md`）。

对同一素材（受保护产物 / baseline）各开一个**独立 LLM 会话**：喂入固定中性提示 + 二进制证据
（可见符号 + 字符串 + 反汇编节选），要求模型以固定 JSON 结构回填函数名、功能类别与关键秘密，
据此计算 S1/S2/S4 信号与 token/time 倍数（FR-E6）。

设计约束（OI-07）：
- **判分器固定**：提示模板与判分逻辑固定，与调用方 Agent 无关、可复现（§3）；
- **独立会话**：无历史、无跨样本迁移；每次针对单个产物（§5）；
- 出站经 `core.evaluate.llm`（`ANTI_REA_LLM_CMD` 或 OpenAI 兼容 `ANTI_REA_LLM_ENDPOINT`）；
  未配置时由调用方降级 `static_only`（§D5）。

判分粒度说明（v0.2 局限）：受保护产物里函数可能已改名，模型给出的「描述符 → 目标」映射不再
可逆，故 S1/S2 采用**集合级**代理——「ground truth 名称/类别是否出现在模型的输出集合中」。
这比逐函数映射宽松，但对「防护是否让分析者拿不到正确名称/类别」仍具判别力；逐函数判分待
基准题库携带「保护后定位」信息后启用。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time

from . import static_features
from .metrics import TH

# 证据上限（字符）：工具返回的反编译文本计入会话消耗（OI-07 §5），故给出可调上限。
MAX_EVIDENCE_CHARS = int(os.environ.get("ANTI_REA_LLM_EVIDENCE_CHARS", "24000"))
MAX_SYMBOLS = 300
MAX_STRINGS = 300

_CATEGORIES = ("crypto", "license", "protocol", "business_logic", "algorithm", "other")

PROMPT_TEMPLATE = """你是一名独立逆向分析员，正在一个全新会话中分析一段二进制产物。

请**只依据**下面给出的证据，对其中与目标资产相关的函数给出你的判断：
1. 该函数的**原始名称**（尽量贴近其真实命名，拿不准也要给出最可能的猜测）；
2. 它的**功能类别**，只能取以下之一：{cats}；
3. 你在证据中能提取到的任何**关键秘密**（硬编码密钥、算法关键参数、受保护常量等）。

严格要求：只输出一个 JSON 对象，不要解释、不要 Markdown 代码块围栏。格式：
{{"functions": [{{"descriptor": "<证据中该函数的定位信息>", "name": "<你判断的原始函数名>", "category": "<类别>"}}],
 "secrets": ["<提取到的关键秘密，如无则空数组>"],
 "notes": "<一句话说明>"}}

二进制证据：
{evidence}
"""

_NORM_RE = re.compile(r"[^a-z0-9]+")


def _norm(s: str) -> str:
    return _NORM_RE.sub("_", (s or "").lower()).strip("_")


def _disasm(exe: str, limit: int) -> str:
    objdump = shutil.which("objdump")
    if not objdump:
        return ""
    try:
        p = subprocess.run([objdump, "-d", "--no-show-raw-insn", exe],
                           capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (p.stdout or "")[:limit]


def build_evidence(exe: str, limit: int = MAX_EVIDENCE_CHARS) -> str:
    """构造喂给独立会话的二进制证据文本（符号 + 字符串 + 反汇编节选）。"""
    chunks: list[str] = []
    try:
        syms = sorted(static_features.user_symbols(exe))[:MAX_SYMBOLS]
    except Exception:  # noqa: BLE001 - 证据构造失败不应中断会话编排
        syms = []
    if syms:
        chunks.append("### 可见符号\n" + "\n".join(syms))
    try:
        strs = sorted(s for s in static_features.string_literals(exe) if len(s) >= 4)
    except Exception:  # noqa: BLE001
        strs = []
    if strs:
        chunks.append("### 字符串\n" + "\n".join(strs[:MAX_STRINGS]))
    dis = _disasm(exe, limit)
    if dis:
        chunks.append("### 反汇编（节选）\n" + dis)
    return "\n\n".join(chunks)[:limit]


def _parse_json(text: str) -> dict:
    """从模型输出里稳妥地取出第一个 JSON 对象（容忍围栏/前后杂讯）。"""
    if not text:
        return {}
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start < 0:
        return {}
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def score(output: str, targets: list[dict]) -> dict:
    """固定判分器：由模型输出与 ground truth 计算 S1/S2/S4（集合级代理，见模块 docstring）。"""
    parsed = _parse_json(output)
    fns = [f for f in parsed.get("functions", []) if isinstance(f, dict)]
    seen_names = {_norm(f.get("name", "")) for f in fns}
    seen_cats = {_norm(f.get("category", "")) for f in fns}

    gt_names = {_norm(t.get("name", "")) for t in targets if t.get("name")}
    gt_cats = {_norm(t.get("category", "")) for t in targets if t.get("category")}
    name_hit = seen_names & gt_names
    cat_hit = seen_cats & gt_cats
    name_acc = len(name_hit) / len(gt_names) if gt_names else 0.0
    cat_acc = len(cat_hit) / len(gt_cats) if gt_cats else 0.0

    gt_secrets = [t["secret"] for t in targets if t.get("secret")]
    haystack = output + " " + " ".join(str(s) for s in parsed.get("secrets", []))
    secret_hits = [s for s in gt_secrets if s and s in haystack]

    signals = {
        # S1 功能类别：准确率 > 0.30（OI-07 §3）
        "S1_function_judgement": cat_acc > TH["function_judgement_max"],
        # S2 函数名恢复：准确率 > 0.20（OI-07 §3）
        "S2_name_recovery": name_acc > TH["name_recovery_max"],
        # S4 关键秘密提取：命中任一 P0 秘密（OI-07 §3）
        "S4_secret_extraction": len(secret_hits) >= 1,
    }
    return {
        "name_recovery_accuracy": round(name_acc, 4),
        "function_judgement_accuracy": round(cat_acc, 4),
        "recovered_names": sorted(seen_names),
        "recovered_categories": sorted(seen_cats),
        "secret_hits": secret_hits,
        "signals": signals,
        "rea_success": any(signals.values()),
    }


def run_session(exe: str, targets: list[dict], *, evidence: str | None = None) -> dict:
    """对单个产物开一次独立会话并判分。返回 token/time/信号等（dict）。

    调用方需先经 `llm.available()` 确认可出站；本函数直接调用 `llm.session()`。
    """
    from . import llm

    ev = build_evidence(exe) if evidence is None else evidence
    prompt = PROMPT_TEMPLATE.format(cats="/".join(_CATEGORIES), evidence=ev)
    t0 = time.perf_counter()
    res = llm.session(prompt)
    secs = time.perf_counter() - t0
    out = res.get("output", "")
    scored = score(out, targets)
    scored.update({
        "exe": os.path.abspath(exe),
        "tokens": int(res.get("tokens_used", 0)),
        "seconds": round(secs, 4),
        "context_window": int(res.get("context_window", 0)),
        "context_used_ratio": float(res.get("context_used_ratio", 0.0)),
        "provider": res.get("provider", "env"),
        "model": res.get("model", "default"),
        "evidence_chars": len(ev),
    })
    return scored
