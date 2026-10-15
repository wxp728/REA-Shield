#!/usr/bin/env bash
# PoC-2 构建与验证脚本：Ghidra Headless（PyGhidra）批量反编译
# 用法: ./run.sh [GHIDRA_HOME]
#   通过标准：批量反编译成功率 >= 95%
set -uo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
cd "$here"

# --- 定位 Ghidra 与 JDK ---
GHIDRA_HOME="${1:-${GHIDRA_HOME:-}}"
if [ -z "$GHIDRA_HOME" ]; then
  for d in /opt/anti-rea-toolchain/ghidra_* /opt/ghidra_*; do
    [ -d "$d" ] && GHIDRA_HOME="$d" && break
  done
fi
[ -n "$GHIDRA_HOME" ] || { echo "错误: 未找到 Ghidra（设 GHIDRA_HOME 或传入路径）" >&2; exit 1; }
export GHIDRA_HOME GHIDRA_INSTALL_DIR="$GHIDRA_HOME"
echo "GHIDRA_INSTALL_DIR = $GHIDRA_HOME"

if [ -z "${JAVA_HOME:-}" ]; then
  for d in /opt/anti-rea-toolchain/jdk-21* /opt/anti-rea-toolchain/jdk-17*; do
    [ -d "$d" ] && export JAVA_HOME="$d" && break
  done
fi
[ -n "${JAVA_HOME:-}" ] && echo "JAVA_HOME = $JAVA_HOME"
export PATH="$JAVA_HOME/bin:$PATH"

# --- 定位 Python（需已安装 pyghidra） ---
PY="${POC_PYTHON:-/opt/anti-rea-toolchain/python3.11/bin/python3.11}"
command -v "$PY" >/dev/null 2>&1 || PY=python3
"$PY" -c "import pyghidra" 2>/dev/null || {
  echo "错误: $PY 未安装 pyghidra。见 poc-plan §7 或 Ghidra/Features/PyGhidra/pypkg/dist" >&2; exit 1; }
echo "PYTHON = $PY"

# --- 构建样例二进制 ---
mkdir -p samples out
echo "== 构建样例二进制 =="
gcc -O0 -o samples/sample_O0 samples/sample.c
gcc -O2 -o samples/sample_O2 samples/sample.c
cp samples/sample_O2 samples/sample_stripped && strip samples/sample_stripped
ls -la samples/ | grep -E 'sample_'

OVERALL_OK=0; OVERALL_TOTAL=0
for bin in sample_O0 sample_O2 sample_stripped; do
  echo "== 反编译 $bin =="
  odir="out/$bin"; mkdir -p "$odir"
  "$PY" decompile_batch.py "samples/$bin" "$odir" "$odir/summary.json" > "out/$bin.log" 2>&1
  line=$(grep -h 'DECOMP_RESULT' "out/$bin.log" | tail -1)
  echo "  ${line:-（无结果，见 out/$bin.log）}"
  ok=$(echo "$line" | sed -n 's/.*ok=\([0-9]*\).*/\1/p'); ok=${ok:-0}
  total=$(echo "$line" | sed -n 's/.*total=\([0-9]*\).*/\1/p'); total=${total:-0}
  OVERALL_OK=$((OVERALL_OK + ok)); OVERALL_TOTAL=$((OVERALL_TOTAL + total))
done

if [ "$OVERALL_TOTAL" -eq 0 ]; then echo "错误: 未采集到函数统计"; exit 1; fi
rate=$(awk "BEGIN{printf \"%.4f\", $OVERALL_OK/$OVERALL_TOTAL}")
echo "--------------------------------------------------"
echo "合计: ok=$OVERALL_OK total=$OVERALL_TOTAL 成功率=$rate"
pass=$(awk "BEGIN{print ($rate>=0.95)?1:0}")
if [ "$pass" -eq 1 ]; then
  echo "结论: PASS（成功率 >= 95%）"; exit 0
else
  echo "结论: FAIL（成功率 < 95%）"; exit 1
fi
