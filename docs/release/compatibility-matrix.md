# 兼容性矩阵（Compatibility Matrix）

> 由 `tools/run_s4.py` 生成（NFR-05 / NFR-10）。

工具链：`{"system": "Linux", "machine": "x86_64", "clang": "clang version 18.1.8"}`

| 平台 | 语言 | 构建系统 | 状态 |
| :--- | :--- | :--- | :--- |
| linux-x86_64 | c | direct | tested |
| linux-x86_64 | c | cmake | tested |
| linux-x86_64 | c | npm | tested |
| linux-x86_64 | c | python-build_ext | tested |
| linux-x86_64 | rust(c/ffi) | cargo | tested |
| aarch64-linux-gnu | c | ir-only | tested |
| riscv64-linux-gnu | c | ir-only | tested |
| wasm32-unknown-unknown | c | ir-only | tested |
| x86_64-pc-windows-gnu | c | ir-only | tested |
| windows-x64 | - | - | unverified |
| macos-arm64 | - | - | unverified |
| android | - | - | unverified |
| wasm | - | - | unverified |

> `tested`=本机实测通过；`ir-only`=编译到该目标三元组的汇编探针；`unverified`=未实测（不含糊声称支持，待 S5/后续平台）。
