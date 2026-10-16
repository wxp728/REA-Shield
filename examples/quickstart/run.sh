#!/usr/bin/env bash
# Anti-REA 端到端快速上手（scan -> plan -> protect -> verify -> attack_sim -> report）
#
# 用法：
#   bash examples/quickstart/run.sh
#   PY=/opt/anti-rea-toolchain/python3.11/bin/python3.11 bash examples/quickstart/run.sh
#
# 前置：已 `pip install -r requirements.txt` 且已 `make build`（构建 LLVM 插件）。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${PY:-$(command -v python3.11 || command -v python3 || command -v python)}"
OUT="${OUT:-$HERE/out}"

cd "$REPO"

echo "== 0) 环境自检 =="
"$PY" -m core.cli doctor

rm -rf "$OUT" && mkdir -p "$OUT"

echo "== 1) scan：扫描工程，识别敏感资产 =="
"$PY" -m core.cli scan "$HERE" -o "$OUT"

echo "== 2) plan：生成加固策略（受性能预算约束） =="
"$PY" -m core.cli plan "$OUT/asset_manifest.json" -o "$OUT"

echo "== 3) protect：施加 LLVM 变换（需要已构建插件） =="
"$PY" -m core.cli protect "$OUT/protection_policy.yaml" \
    --root "$HERE" --source "$HERE/victim.c" -o "$OUT"

echo "== 4) verify：差分验证功能保持 =="
"$PY" -m core.cli verify "$OUT"

echo "== 5) attack_sim：攻击模拟评估（无 LLM 时退化为 static_only） =="
"$PY" -m core.cli attack_sim "$OUT" --mode all || true

echo "== 6) report：生成人读报告 =="
"$PY" -m core.cli report "$OUT"

echo
echo "完成 ✅  产物目录：$OUT"
echo "  - asset_manifest.json / protection_policy.yaml"
echo "  - artifacts/（baseline、protected、transform.log）"
echo "  - verification_report.json / eval_report.json / report.md"
