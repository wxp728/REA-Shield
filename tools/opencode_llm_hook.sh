#!/usr/bin/env bash
# 把 REA-Shield 的 LLM 会话钩子指向本机 OpenCode（FR-E3 红队分析师）。
#
# 契约（见 core/evaluate/llm.py）：stdin 收提示词，stdout 回 JSON
#   {"output": "<模型文本>", "tokens_used": <int>}
#
# 用法：
#   export ANTI_REA_LLM_CMD="$PWD/tools/opencode_llm_hook.sh"
#   export ANTI_REA_LLM_MODEL="opencode/deepseek-v4.1-flash-free"   # 可选
#   anti-rea attack_sim <run>/ --allow-llm --benchmark benchmarks/xxx.yaml
#
# 说明：
# - `opencode run --format json` 输出 JSONL；本脚本按行取 type=="text" 的 part.text 拼接；
# - 该 JSONL **不含 token 计数**，故 tokens 按 (提示词+输出) 字符数 /4 估算，
#   仅用于同协议相对比较（token_ratio），不作为绝对计量。
set -euo pipefail

PY="${ANTI_REA_PYTHON:-python3}"

prompt="$(cat)"

model_args=()
if [ -n "${ANTI_REA_LLM_MODEL:-}" ]; then
  model_args=(--model "${ANTI_REA_LLM_MODEL}")
fi

raw="$(opencode run --standalone --auto --format json "${model_args[@]}" "$prompt" 2>/dev/null || true)"

output="$(printf '%s' "$raw" | "$PY" -c '
import json
import sys

buf = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        continue
    if ev.get("type") == "text":
        buf.append(ev.get("part", {}).get("text", ""))
sys.stdout.write("".join(buf))
')"

tokens=$(( ( ${#prompt} + ${#output} ) / 4 ))

"$PY" -c 'import json,sys; print(json.dumps({"output": sys.argv[1], "tokens_used": int(sys.argv[2])}))' \
  "$output" "$tokens"
