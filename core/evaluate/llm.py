"""LLM 会话适配（不绑定供应商；OI-07 §5、CQ-05 出站控制）。

优先级：
1. `ANTI_REA_LLM_CMD`：本地命令钩子（stdin 收提示词，stdout 返回 JSON `{"output":..,"tokens_used":..}`）；
2. `ANTI_REA_LLM_ENDPOINT`（OpenAI 兼容 `/chat/completions`）+ `ANTI_REA_LLM_MODEL` + `ANTI_REA_LLM_KEY`。

无上述配置或未授权出站（`allow_llm=False`）时 `available()` 为 False，评估降级 `static_only`
（OI-07 §D5）。
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request

DEFAULT_WINDOW = 128000


def available(allow_llm: bool = True) -> bool:
    if not allow_llm:
        return False
    return bool(os.environ.get("ANTI_REA_LLM_CMD")
                or os.environ.get("ANTI_REA_LLM_ENDPOINT"))


def context_window() -> int:
    try:
        return int(os.environ.get("ANTI_REA_LLM_WINDOW", DEFAULT_WINDOW))
    except ValueError:
        return DEFAULT_WINDOW


def _via_cmd(prompt: str) -> dict:
    cmd = os.environ["ANTI_REA_LLM_CMD"]
    p = subprocess.run(cmd, shell=True, input=prompt, capture_output=True,
                       text=True, timeout=600)
    if p.returncode != 0:
        raise RuntimeError("E_LLM_UNAVAILABLE: cmd 退出码 %d" % p.returncode)
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("E_LLM_UNAVAILABLE: 非法 JSON 输出") from exc
    return {"output": data.get("output", ""),
            "tokens_used": int(data.get("tokens_used", 0))}


def _via_http(prompt: str) -> dict:
    ep = os.environ["ANTI_REA_LLM_ENDPOINT"].rstrip("/")
    model = os.environ.get("ANTI_REA_LLM_MODEL", "default")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(ep + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    key = os.environ.get("ANTI_REA_LLM_KEY")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310
        data = json.loads(resp.read().decode())
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = data.get("usage", {})
    used = int(usage.get("total_tokens", 0))
    return {"output": text, "tokens_used": used}


def session(prompt: str) -> dict:
    """在独立会话中执行一次请求，返回 `{output, tokens_used, context_window}`。"""
    if os.environ.get("ANTI_REA_LLM_CMD"):
        out = _via_cmd(prompt)
    elif os.environ.get("ANTI_REA_LLM_ENDPOINT"):
        out = _via_http(prompt)
    else:
        raise RuntimeError("E_LLM_UNAVAILABLE: 未配置 LLM 出站")
    out["context_window"] = context_window()
    out["context_used_ratio"] = min(
        1.0, out["tokens_used"] / out["context_window"]
        if out["context_window"] else 1.0)
    out["provider"] = os.environ.get("ANTI_REA_LLM_PROVIDER", "env")
    out["model"] = os.environ.get("ANTI_REA_LLM_MODEL", "default")
    return out
