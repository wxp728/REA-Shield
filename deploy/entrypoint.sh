#!/bin/sh
# Anti-REA 容器入口：支持 `mcp` 子命令切换到 MCP stdio 服务器，
# 其余参数交给 CLI（scan/plan/protect/verify/doctor/...）。
set -e
if [ "$1" = "mcp" ]; then
    shift
    exec python -m core.mcp "$@"
fi
exec python -m core.cli "$@"
