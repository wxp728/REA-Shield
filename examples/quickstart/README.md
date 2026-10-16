# Quickstart：10 分钟跑通端到端闭环

这个示例演示 Anti-REA 的完整流程：**扫描敏感资产 → 生成策略 → 施加加固变换 →
验证功能保持 → 攻击模拟 → 出报告**。

`victim.c` 是一个「你自己的」小项目，含一个硬编码密钥和一个许可证校验函数，
用来展示扫描器如何把它们识别为 P0/P1 资产。

## 前置条件

- Linux x86_64，Python ≥ 3.11，LLVM/clang ≥ 18，CMake ≥ 3.16，binutils。
- 已完成：

```bash
cd /path/to/anti-rea
pip install -r requirements.txt
make build            # 构建 LLVM 变换插件（engine/build/anti_rea_passes.so）
make doctor           # 环境应全绿
```

> 不想手工装工具链？用容器：
> ```bash
> docker build -t anti-rea:1.0.0 .
> docker run --rm -v "$PWD:/work" anti-rea:1.0.0 \
>     scan /work/examples/quickstart -o /work/examples/quickstart/out
> ```

## 运行

```bash
bash examples/quickstart/run.sh
```

脚本会依次执行 `doctor → scan → plan → protect → verify → attack_sim → report`，
所有产物写入 `examples/quickstart/out/`。

## 产物说明

| 文件 | 内容 |
| :--- | :--- |
| `asset_manifest.json` | 扫描到的资产（路径、类型、敏感度 P0–P3、证据） |
| `protection_policy.yaml` | 每个资产采用的加固策略 |
| `artifacts/baseline` | 未加固的可执行文件（参照物） |
| `artifacts/protected` | 加固后的可执行文件 |
| `artifacts/transform.log` | 变换日志（seed、白名单、策略） |
| `verification_report.json` | 功能保持 + 性能开销验证 |
| `eval_report.json` | 攻击模拟评估（逆向成功率等） |
| `report.md` | 人读保护报告 |

## 观察要点

- `scan` 会把 `MASTER_KEY`（高熵字符串 + 关键字）判为 **P0 secret**，
  `verify_license` 判为许可证校验逻辑。
- `protect` 对 P0 默认启用**字符串加密**（锚点移除），对敏感逻辑启用
  **控制流平坦化 / MBA** 等；这些都是「抬高成本」而非「不可破解」。
- `verify` 用差分（baseline vs protected）确认功能一致；`attack_sim`
  在无 LLM 会话时退化为 `static_only`，仍给出可复现的指标。

自己动手核对（在 `out/` 下）：

```sh
# 符号级锚点移除：白名单函数被改名，符号消失
nm   artifacts/protected 2>/dev/null | grep -E 'verify_license|compute_checksum' || echo "(符号已移除)"
# 直接使用的字符串常量会被异或编码
strings artifacts/protected 2>/dev/null | grep -E 'S3cr3t|licensed' || echo "(直接量已编码)"
```

> **v0.1 已知限制**：经**全局指针变量**间接引用的字符串（如本例的
> `static const char *MASTER_KEY`）不会被 `string_encrypt` 编码——该 Pass 处理的是
> 指令中**直接**使用的字节串常量。故评估应综合 `nm`/`strings` 与独立核验，而非只看
> 单一信号（与 `docs/release/adversarial-report.md` 的口径一致）。这是能力增强项，
> 不阻塞使用。

## 下一步

- 换成你自己的项目：把 `--root` / `--source` 指向你的源码目录。
- 接进 Agent：见 [`../../docs/mcp-clients.md`](../../docs/mcp-clients.md)。
- 更多参数与限制：见 [`../../SKILL.md`](../../SKILL.md) 与
  [`../../docs/INSTALL.md`](../../docs/INSTALL.md)。
