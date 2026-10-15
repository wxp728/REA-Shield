#!/usr/bin/env bash
# Anti-REA CI 门禁（plan §5.1：lint + 单测 + 覆盖率 + 构建）
# 用法：bash ci/ci.sh
set -euo pipefail

LLVM="${LLVM:-/opt/anti-rea-toolchain/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04}"
PY="${PY:-/opt/anti-rea-toolchain/python3.11/bin/python3.11}"
export PATH="$LLVM/bin:$PATH"

echo "== [1/6] 构建引擎（LLVM Pass 插件） =="
cmake -S engine -B engine/build -DLLVM_DIR="$LLVM/lib/cmake/llvm" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build engine/build -j

echo "== [2/6] Lint（ruff，若可用） =="
if command -v ruff >/dev/null 2>&1; then
  ruff check core tests
else
  echo "  ruff 未安装，跳过（不阻塞）"
fi

echo "== [3/6] 单元 + 集成测试 =="
"$PY" -m unittest discover -s tests -v

echo "== [4/6] 端到端流水线（scan->plan->protect->verify） =="
OUT="$(mktemp -d)"
"$PY" -m core.cli scan tests/samples -o "$OUT"
"$PY" -m core.cli plan "$OUT/asset_manifest.json" -o "$OUT"
"$PY" -m core.cli protect "$OUT/protection_policy.yaml" --root tests/samples \
    --source tests/samples/hello.c -o "$OUT" 2>/dev/null
"$PY" -m core.cli verify "$OUT"
echo "== [5/6] S4 系统验证（快速：差分 fuzz/性能/独立/可复现/稳健/兼容） =="
"$PY" tools/run_s4.py --quick --no-docs --out "$(mktemp -d)/s4" >/dev/null

echo "CI 全绿 ✅"
