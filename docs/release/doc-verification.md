# 文档验证（按文档从零复现）

> 由 `tools/run_s4.py` 生成（§10.3）。逐条执行文档中的命令并记录结果。

| 命令 | 退出码 | 结果 |
| :--- | ---: | :--- |
| `/opt/anti-rea-toolchain/python3.11/bin/python3.11 -m core.cli scan tests/samples -o /home/user/anti-rea/build/s4/docrun` | 0 | 通过 |
| `/opt/anti-rea-toolchain/python3.11/bin/python3.11 -m core.cli plan /home/user/anti-rea/build/s4/docrun/asset_manifest.json -o /home/user/anti-rea/build/s4/docrun` | 0 | 通过 |
| `/opt/anti-rea-toolchain/python3.11/bin/python3.11 -m core.cli protect /home/user/anti-rea/build/s4/docrun/protection_policy.yaml --root tests/samples --source tests/samples/p0_secret.c -o /home/user/anti-rea/build/s4/docrun` | 0 | 通过 |
| `/opt/anti-rea-toolchain/python3.11/bin/python3.11 -m core.cli verify /home/user/anti-rea/build/s4/docrun` | 0 | 通过 |
| `/opt/anti-rea-toolchain/python3.11/bin/python3.11 -m core.cli attack_sim /home/user/anti-rea/build/s4/docrun --benchmark benchmarks/bench-crypto-001.yaml` | 0 | 通过 |
| `/opt/anti-rea-toolchain/python3.11/bin/python3.11 -m core.cli report /home/user/anti-rea/build/s4/docrun --format all` | 0 | 通过 |

总体：**通过**
