# FAQ（常见问题）

## 这个项目到底是什么？是"skill"吗？

是。Anti-REA 是一套 **AI Agent 可调用的代码加固工具链**：
- 技能入口：[`../SKILL.md`](../SKILL.md)、机器可读清单 [`../skill.json`](../skill.json)；
- 命令行：`anti-rea`（scan/plan/protect/verify/report/attack_sim/…）；
- MCP Server：`anti-rea-mcp`（stdio JSON-RPC，7 个工具），供上层 Agent 调用。

它不是一个「贴进 prompt 就能用」的纯提示词包，而是**要安装、构建、接线**的软件——
但已经把「上手成本」压到：`pip install -r requirements.txt` → `anti-rea doctor`
→ `make build`（或用 Docker 一步到位）。

## 会不会去攻击/破解别人的软件？

不会。本工具链只对你**拥有或有权修改**的代码施加**加固**（间接反制），
不包含任何针对 REA 工具的破坏能力。扫描器默认跳过开放源码组件，
所有权不明时拒绝执行（`E_REFUSED`）。

## 支持哪些语言？

- **可施加 IR 层变换**：C、C++；Rust 仅 C/FFI 源（经 Cargo 集成）；
  Python 仅 C 扩展（经 setup.py 集成）。
- **仅可扫描（无 IR 防护）**：纯 Rust、Java、.NET/C#、JS/TS、纯 Python。

原因见 `docs/design/ADR.md` 的 ADR-006。SRS 中的语言清单是「扫描/识别范围」，
不等于「变换范围」。

## 支持哪些平台？

v1.0 **完整实测**：Linux x86_64。`scan`/`plan` 在任何能跑 Python 的平台都可用；
`protect`/`verify` 需要已构建的 LLVM 插件，其他平台（含 Windows）请用
Docker 或 WSL。见 `docs/release/compatibility-matrix.md`。

## 为什么 `protect` 说找不到 clang？

因为 `protect` 需要 LLVM/clang。先跑 `anti-rea doctor` 看缺什么。修复方式：

```sh
export ANTI_REA_LLVM=/usr/lib/llvm-18     # 指向你的 LLVM 前缀
# 或把 LLVM 的 bin 加进 PATH
```

工具链路径**已不再写死**，按「环境变量 > PATH > 常见目录」自动探测。

## 需要联网/LLM 吗？

核心闭环**不需要**。`attack_sim` 在没有真实 LLM 会话时自动降级为
`static_only`（静态代理指标）。接入真实 LLM 会话是可选能力，通过
`ANTI_REA_LLM_CMD`（外部命令）或 `ANTI_REA_LLM_ENDPOINT` 等环境变量配置，
且必须显式 `--allow-llm` 才出站。

## 加固后是不是就"不可逆向"了？

不是，也不追求这个。威胁模型是「把逆向成本抬高到高于收益」。任何加固都可被
有决心、有资源的分析者攻克。请把它当作**提高门槛**的手段，而非绝对保护。

## 会拖慢程序吗？

会，但受**性能预算**约束（NFR-01）：P0 增量开销 ≤ 0.40、P1 ≤ 0.15、
P2/P3 ≤ 0.05（相对基线）。`verify` 会实测并判定是否超预算。

## 产物在哪 / 怎么判断"加固成功"？

`protect` 产出到 `-o` 指定目录：`artifacts/baseline`（未加固）、
`artifacts/protected`（加固后）、`artifacts/transform.log`、`protection_policy.yaml`。
`verify` 判断功能是否保持 + 开销是否达标；`attack_sim` 给出逆向成功率等评估。

## Wheel 安装后报找不到 schemas/policies？

wheel 是次要件。数据契约与策略模板随仓库分发，wheel 安装后请设置
`ANTI_REA_ROOT` 指向含 `schemas/`、`policies/` 的目录，或直接用**全仓自包含包**
`anti-rea-<ver>-bundle.tar.gz`（主产物）。

## 还有问题？

见 [`troubleshooting.md`](troubleshooting.md)（按错误码/现象排障），
或在仓库提 Issue（`.github/ISSUE_TEMPLATE/`）。
