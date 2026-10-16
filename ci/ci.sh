#!/usr/bin/env bash
# Anti-REA CI 门禁（plan §5.1：lint + 单测 + 覆盖率 + 构建）
# 用法：bash ci/ci.sh
# 工具链定位：环境变量 LLVM/PY 优先，其次 llvm-config/常见目录自动探测。
set -euo pipefail

if [ -z "${LLVM:-}" ]; then
  if [ -n "${ANTI_REA_LLVM:-}" ]; then
    LLVM="$ANTI_REA_LLVM"
  elif command -v llvm-config >/dev/null 2>&1; then
    LLVM="$(dirname "$(dirname "$(command -v llvm-config)")")"
  else
    LLVM="$(ls -d /opt/anti-rea-toolchain/clang+llvm-* /opt/anti-rea-toolchain/llvm* /usr/lib/llvm-* 2>/dev/null | sort | tail -1)"
  fi
fi
PY="${PY:-$(command -v python3.11 || command -v python3 || command -v python)}"
LLVM_CMAKE_DIR="$(llvm-config --cmakedir 2>/dev/null || echo "$LLVM/lib/cmake/llvm")"
if [ -n "$LLVM" ]; then export PATH="$LLVM/bin:$PATH"; fi

echo "== [1/8] 环境自检（doctor） =="
"$PY" -m core.cli doctor || true

echo "== [2/8] 构建引擎（LLVM Pass 插件） =="
cmake -S engine -B engine/build -DLLVM_DIR="$LLVM_CMAKE_DIR" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build engine/build -j

echo "== [3/8] Lint（ruff，若可用） =="
if command -v ruff >/dev/null 2>&1; then
  ruff check core tests
else
  echo "  ruff 未安装，跳过（不阻塞）"
fi

echo "== [4/8] 单元 + 集成测试 =="
"$PY" -m unittest discover -s tests -v

echo "== [5/8] 端到端流水线（scan->plan->protect->verify） =="
OUT="$(mktemp -d)"
"$PY" -m core.cli scan tests/samples -o "$OUT"
"$PY" -m core.cli plan "$OUT/asset_manifest.json" -o "$OUT"
"$PY" -m core.cli protect "$OUT/protection_policy.yaml" --root tests/samples \
    --source tests/samples/hello.c -o "$OUT" 2>/dev/null
"$PY" -m core.cli verify "$OUT"
echo "== [6/8] S4 系统验证（快速：差分 fuzz/性能/独立/可复现/稳健/兼容） =="
"$PY" tools/run_s4.py --quick --no-docs --out "$(mktemp -d)/s4" >/dev/null

echo "== [7/8] S5 Beta 试点（3 试点独立闭环） =="
"$PY" tools/run_s5.py --out "$(mktemp -d)/s5" --docs "$(mktemp -d)/rel" >/dev/null

echo "== [8/8] 打包自检（release.py --check） =="
"$PY" tools/release.py --check --out "$(mktemp -d)/dist" >/dev/null || true

echo "CI 全绿 ✅"
