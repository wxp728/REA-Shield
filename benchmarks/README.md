# 攻击模拟基准题库（ground truth）

> **R3 已实现**：题库格式见 `schemas/benchmark.schema.json`（`docs/design/ddd/dd-07-evaluation.md §6`）；
> 现提供内置样例，用于攻击模拟判分（FR-E7）与回归检测（FR-E8）。

## 要求

- 许可证干净（CQ-01）、构建确定可复现（NFR-04）；
- 覆盖 C/C++/Rust，含 P0–P3 资产与已知漏洞；
- 每个目标函数标注：`symbol`（定位）、`name`（真名）、`category`（功能类别）、
  `secret`（关键秘密，可选）、`vuln`（漏洞标识，可选）。

## 现有题库

| 文件 | 对应样例 | 目标 |
| :--- | :--- | :--- |
| `bench-hello.yaml` | `tests/samples/hello.c` | `add` / `classify` / `secret_mix` |
| `bench-crypto-001.yaml` | `tests/samples/p0_secret.c` | `secret_schedule` / `secret_roundtrip`（P0） |
| `bench-crypto-module.yaml` |  `src/common/crypto_algorithm/` | SM4/SM3/DET-SM4 核心函数（crypto，实测用例） |

## 目录约定

```text
benchmarks/
├── <bench-id>.yaml          # 单文件题库（ground truth，见 benchmark.schema.json）
├── <bench-id>/              # 复杂题库（可选）：src/ + build.sh + ground_truth.yaml
└── README.md
```

用法：

```sh
python -m core.cli attack_sim <run_dir> --benchmark benchmarks/bench-crypto-001.yaml
python -m core.cli regress   <run_dir> --benchmark benchmarks/bench-crypto-001.yaml --db build/metrics.db
```
