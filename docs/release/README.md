# docs/release/：S4 验证与发布产物

> 由 S4（M6）生成，S5（试点）/S6（发布）继续更新。

| 文件 | 内容 | 生成方式 |
| :--- | :--- | :--- |
| `STR.md` | 系统测试报告（M6 出口核对） | `python tools/run_s4.py` |
| `performance-baseline.md` | 性能基线数据（NFR-01） | 同上 |
| `adversarial-report.md` | 对抗评估报告（NFR-02） | 同上 |
| `compatibility-matrix.md` | 兼容性矩阵（NFR-05/10） | 同上 |
| `doc-verification.md` | 文档验证 | 同上 |
| `security-selfcheck.md` | 安全自检说明（NFR-09） | `python tools/sbom.py` |
| `sbom.json` | 软件物料清单 | `python tools/sbom.py` |
| `defects.md` | 缺陷清单 | 人工维护 |

## 关于 M6「外部独立验证」

`plan §6.3` 要求「至少 1 家外部独立验证结果与内置结论不矛盾」。本次以
**独立工具交叉验证**（`objdump`；开启 `ANTI_REA_GHIDRA=1` 时含 **Ghidra/PyGhidra**）
近似该要求：它是与内置 `nm`/`strings` 路径**实现独立**的第二方复核，但**不等同于
第三方红队/独立 LLM 评估**——后者需真实 LLM 出站（CQ-05），列为 S5 行动项。

## 关于 Token 消耗倍数 ≥ 100x

该指标需真实 LLM 独立会话（FR-E3/OI-07）。无 LLM 时评估降级 `static_only`，
以可复现的静态代理指标作为替代门禁；Token 倍数留待 S5 配置 LLM 后计量。
