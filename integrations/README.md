# integrations/：构建集成（CMake / Cargo / npm / Python / MCP Server）

设计见 `docs/design/ddd/dd-build-integration.md`；实现属 R2/R3（FR-D2…D6）。

统一原则（`dd-build-integration §4`）：**插件不内嵌引擎**，只调用集成驱动
`integrations/anti-rea`（或 `anti_rea.py`），走 `scan → plan → protect → verify`；
验证失败时按 `--abort-on-failure` 以非零退出中止构建（FR-D7）。

环境变量：`ANTI_REA_PYTHON`（解释器，缺省自动探测）、`ANTI_REA_DRIVER`（驱动路径覆盖）。

| 集成 | 文件 | 挂载点 | 样例 |
| :--- | :--- | :--- | :--- |
| CMake | `cmake/AntiRea.cmake` | `add_custom_target(POST_BUILD)` | `cmake/example/` |
| Cargo | `cargo/build.rs` | `build.rs` | `cargo/example/` |
| npm | `npm/anti-rea-protect.js` | `scripts.postbuild` | `npm/example/` |
| Python | `python/anti_rea_build_ext.py` | `build_ext` | `python/example/` |
| MCP Server | （R3，FR-D6） | stdio JSON-RPC | — |

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
