# integrations/：构建集成（CMake / Cargo / npm / Python / MCP Server）

设计见 `docs/design/ddd/dd-build-integration.md`；实现属 R2/R3（FR-D2…D6）。

统一原则（`dd-build-integration §4`）：**插件不内嵌引擎**，只调用集成驱动
`integrations/anti-rea`（或 `anti_rea.py`），走 `scan → plan → protect → verify`；
验证失败时按 `--abort-on-failure` 以非零退出中止构建（FR-D7）。

环境变量：`ANTI_REA_PYTHON`（解释器，缺省自动探测）、`ANTI_REA_DRIVER`（驱动路径覆盖）。

| 集成 | 文件 | 挂载点 | 样例 |
| :--- | :--- | :--- | :--- |
| **编译器包装器** | `cc-wrapper/anti-rea-cc` | `CC=<wrapper>`（注入真实构建，产出 `.so`/可执行） | 见 `docs/build-injection.md` |
| CMake | `cmake/AntiRea.cmake` | `add_custom_target(POST_BUILD)` | `cmake/example/` |
| Cargo | `cargo/example/build.rs` | `build.rs` | `cargo/example/` |
| npm | `npm/anti-rea-protect.js` | `scripts.postbuild` | `npm/example/` |
| Python | `python/anti_rea_build_ext.py` | `build_ext` | `python/example/` |
| MCP Server | `core/mcp/server.py` | stdio JSON-RPC（7 工具） | `anti-rea-mcp` / `python -m core.mcp` |

## 已知限制

- **Rust IR 级保护**：变换引擎基于 LLVM Pass + clang 流水线；Cargo 集成 v1.0 保护 crate 内的
  **C/FFI 源**（`--source csrc/secret.c`）。对纯 Rust 源做 IR 级保护需 `rustc --emit=llvm-ir`
  适配（ADR-006 适配层），列为后续增强。

## 快速验证

```sh
# CMake
cmake -S integrations/cmake/example -B /tmp/ar-cmake && cmake --build /tmp/ar-cmake

# npm
( cd integrations/npm/example && npm run build )

# Python
( cd integrations/python/example && $ANTI_REA_PYTHON setup.py build_ext --inplace )

# Cargo（需 rustc/cargo）
( cd integrations/cargo/example && cargo build )
```

自动化用例见 `tests/test_integrations.py`（缺相应工具链时跳过）。
