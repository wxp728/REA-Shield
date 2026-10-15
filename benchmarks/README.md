# 攻击模拟基准题库（ground truth）

> R1 占位。题库建设为 S3 行动项（见 `docs/design/ddd/dd-10-review.md §7` DD-A1）。
> 格式设计见 `docs/design/ddd/dd-07-evaluation.md §6`（拟新增 `schemas/benchmark.schema.json`）。

## 要求

- 许可证干净（CQ-01）、构建确定可复现（NFR-04）；
- 覆盖 C/C++/Rust，含 P0–P3 资产与已知漏洞；
- 每个目标函数标注：`name`（真名）、`category`（功能类别）、`secrets`（关键秘密）、`vulns`（漏洞及位置）。

## 目录（规划）

```text
benchmarks/
├── <bench-id>/
│   ├── src/                 # 源码（自研或许可证干净的开源子集）
│   ├── build.sh             # 确定性构建
│   └── ground_truth.yaml    # 见 dd-07 §6
└── README.md
```
