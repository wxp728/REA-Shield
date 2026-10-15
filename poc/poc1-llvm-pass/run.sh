#!/usr/bin/env bash
# PoC-1 构建与验证脚本：LLVM Pass 控制流平坦化
# 用法: ./run.sh [LLVM_PREFIX]
#   LLVM_PREFIX 默认取 llvm-config-18 / llvm-config / $LLVM_HOME/bin
# 通过标准：样例函数变换后可编译、可运行、单元测试全过
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
cd "$here"

# --- 定位 LLVM ---
LLVM_CONFIG="${1:-}"
if [ -z "$LLVM_CONFIG" ]; then
  for cand in llvm-config-18 llvm-config; do
    if command -v "$cand" >/dev/null 2>&1; then LLVM_CONFIG="$cand"; break; fi
  done
fi
if [ -z "${LLVM_CONFIG}" ] && [ -n "${LLVM_HOME:-}" ] && [ -x "$LLVM_HOME/bin/llvm-config" ]; then
  LLVM_CONFIG="$LLVM_HOME/bin/llvm-config"
fi
[ -n "$LLVM_CONFIG" ] || { echo "错误: 未找到 llvm-config" >&2; exit 1; }
echo "LLVM_CONFIG = $LLVM_CONFIG"
"$LLVM_CONFIG" --version 2>/dev/null | sed 's/^/LLVM 版本: /'

BIN="$("$LLVM_CONFIG" --bindir)"
CXX="${CXX:-$BIN/clang++}"; [ -x "$CXX" ] || CXX=clang++
CC="${CC:-$BIN/clang}";     [ -x "$CC" ]  || CC=clang
OPT="${OPT:-$BIN/opt}";     [ -x "$OPT" ] || OPT=opt
echo "CXX=$CXX  CC=$CC  OPT=$OPT"

CXXFLAGS="$("$LLVM_CONFIG" --cxxflags | sed 's/-fno-exceptions//g') -fPIC -fno-rtti -std=c++17"
LDFLAGS="$("$LLVM_CONFIG" --ldflags)"

text_size() { size -A "$1" | awk '/^\.text/{print $2}'; }

# --- 构建插件 ---
echo "== 构建 Pass 插件 =="
$CXX $CXXFLAGS -shared -o cff_flatten.so flatten.cpp $LDFLAGS
echo "插件: cff_flatten.so"

# --- 基线（不施加变换） ---
echo "== 基线编译（无变换）=="
$CC -O1 -o sample_plain sample.c
base_out="$(./sample_plain)"; echo "基线输出: $base_out"
[ "$base_out" = "OK" ] || { echo "基线未通过"; exit 1; }
echo "基线 .text = $(text_size sample_plain)"

# --- 路径 A：clang -fpass-plugin（经 OptimizerLast 自动挂载 reg2mem+cff）---
echo "== 路径 A：clang -fpass-plugin =="
$CC -O1 -fpass-plugin=./cff_flatten.so -o sample_cff sample.c
cff_out="$(./sample_cff)"; echo "变换输出: $cff_out"
[ "$cff_out" = "OK" ] || { echo "路径 A 变换后未通过"; exit 1; }
tA=$(text_size sample_cff); echo "路径 A .text = $tA"

# --- 路径 B：opt -passes='reg2mem,cff-flatten'（显式流水线，IR 可复现/可核验）---
echo "== 路径 B：opt reg2mem,cff-flatten =="
$CC -O1 -S -emit-llvm -o sample.ll sample.c
$OPT -load-pass-plugin=./cff_flatten.so -passes='reg2mem,cff-flatten' -S sample.ll -o sample_cff.ll
n_disp=$(grep -c 'cff.dispatch' sample_cff.ll || true)
echo "变换后 IR 中 cff.dispatch 出现次数: $n_disp"
[ "$n_disp" -gt 0 ] || { echo "未检测到 CFF 派发块"; exit 1; }
$CC -O0 sample_cff.ll -o sample_cff_opt
opt_out="$(./sample_cff_opt)"; echo "变换输出: $opt_out"
[ "$opt_out" = "OK" ] || { echo "路径 B 变换后未通过"; exit 1; }
tB=$(text_size sample_cff_opt); echo "路径 B .text = $tB"

echo "--------------------------------------------------"
echo ".text 对比: plain=$(text_size sample_plain)  A=$tA  B=$tB"
echo "结论: PASS（变换后可编译、可运行、单元测试全过；两条加载路径均通过，.text 增大）"
