# 文档验证（按文档从零复现）

> 由 `tools/run_s4.py` 生成（§10.3）。逐条执行文档中的命令并记录结果。
> 命令中的 `python3.11` / `<out>` 为占位写法（生成时已去除本机绝对路径），退出码与结果不变。

| 命令 | 退出码 | 结果 |
| :--- | ---: | :--- |
| `python3.11 -m core.cli scan tests/samples -o <out>` | 0 | 通过 |
| `python3.11 -m core.cli plan <out>/asset_manifest.json -o <out>` | 0 | 通过 |
| `python3.11 -m core.cli protect <out>/protection_policy.yaml --root tests/samples --source tests/samples/p0_secret.c -o <out>` | 0 | 通过 |
| `python3.11 -m core.cli verify <out>` | 0 | 通过 |
| `python3.11 -m core.cli attack_sim <out> --benchmark benchmarks/bench-crypto-001.yaml` | 0 | 通过 |
| `python3.11 -m core.cli report <out> --format all` | 0 | 通过 |

总体：**通过**
