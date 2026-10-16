# MCP 客户端配置（Anti-REA Server）

Anti-REA 通过 **MCP（Model Context Protocol）** 暴露 7 个工具（`scan` / `plan` /
`protect` / `verify` / `attack_sim` / `report` / `evolve`），让上层 Agent 以工具调用
而非手工拼命令的方式完成加固。

传输：**stdio JSON-RPC**（`initialize` / `tools/list` / `tools/call`），
协议版本 `2024-11-05`。

启动命令二选一（任选其一即可）：

| 方式 | 命令 | 适用 |
|------|------|------|
| 已 `pip install`（有 console script） | `anti-rea-mcp` | 最简 |
| 直接跑仓库（无需安装） | `python -m core.mcp`（`cwd` 设为仓库根） | 开发/免安装 |

> **务必让 MCP 进程能找到 clang/opt 与已构建的引擎插件。**
> 最简单的方式是在配置里注入环境变量 `ANTI_REA_LLVM` 与 `PATH`；
> 启动前先在目标环境跑一次 `anti-rea doctor` 确认全绿。

---

## 1. Claude Desktop

配置文件：
- macOS：`~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows：`%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "anti-rea": {
      "command": "python3",
      "args": ["-m", "core.mcp"],
      "cwd": "/home/YOU/anti-rea",
      "env": {
        "ANTI_REA_LLVM": "/path/to/llvm-18",
        "PATH": "/path/to/llvm-18/bin:/usr/bin:/bin"
      }
    }
  }
}
```

## 2. Cursor

项目级 `.cursor/mcp.json`（或全局 `~/.cursor/mcp.json`）：

```json
{
  "mcpServers": {
    "anti-rea": {
      "command": "anti-rea-mcp",
      "env": {
        "ANTI_REA_LLVM": "/path/to/llvm-18"
      }
    }
  }
}
```

## 3. 通用 stdio 客户端（VS Code / Continue / 自研 Agent）

任何支持 MCP stdio 的客户端，本质都是「启动一个子进程 + 读写 JSON-RPC」，
因此等价配置：

```json
{
  "name": "anti-rea",
  "transport": { "type": "stdio" },
  "command": "anti-rea-mcp",
  "environment": {
    "ANTI_REA_LLVM": "/path/to/llvm-18"
  }
}
```

最小手测（不依赖任何客户端）：

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | anti-rea-mcp
```

## 4. MCP Inspector（调试）

```bash
npx @modelcontextprotocol/inspector anti-rea-mcp
```

---

## 工具调用示例

`tools/call` 的 `params` 形如 `{"name": "...", "arguments": {...}}`。

```jsonc
// 1) 扫描
{"name": "anti_rea.scan", "arguments": {"path": "/path/to/project"}}

// 2) 生成策略（budget 可选）
{"name": "anti_rea.plan", "arguments": {"manifest": { /* 上一步结果 */ }, "seed": 0}}

// 3) 施加加固
{"name": "anti_rea.protect", "arguments": {
  "policy": { /* plan 结果 */ },
  "root": "/path/to/project",
  "sources": ["/path/to/project/src/main.c"],
  "out": "/tmp/anti-rea-out",
  "seed": 0
}}

// 4) 功能验证 / 攻击模拟
{"name": "anti_rea.verify", "arguments": {"artifacts": "/tmp/anti-rea-out"}}
{"name": "anti_rea.attack_sim", "arguments": {"artifacts": "/tmp/anti-rea-out", "mode": "all"}}
```

完整工具参数见 [`skill.json`](../skill.json) 的 `tools` 字段，或对服务器发送
`tools/list`。

## 常见问题

- **`tools/call` 报找不到 clang / 插件**：MCP 子进程环境通常很干净。请像上面
  那样显式注入 `ANTI_REA_LLVM` 和 `PATH`，并确认已 `make build`。
- **Windows 上 protect 失败**：v1.0 的变换引擎为 Linux 共享库插件；Windows 上
  请用 Docker/WSL（见 `docs/INSTALL.md`）。
- **只想让 Agent「看一眼」不加固**：先用 `scan` / `plan`（只读），确认无误再
  `protect`。
