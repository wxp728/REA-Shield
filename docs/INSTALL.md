# 安装与升级指南（Install & Upgrade）

> 面向 **Linux x86_64**（已实测平台）。其他平台见 `docs/release/compatibility-matrix.md`。

## 1. 依赖

| 组件 | 版本 | 用途 | 是否必需 |
| :--- | :--- | :--- | :--- |
| Python | 3.11 | 编排核心 / 评估 | 必需 |
| LLVM/clang | 18.x | 变换引擎宿主 + 编译 | 必需 |
| CMake | ≥ 3.10 | 构建引擎、CMake 集成 | 必需 |
| Python 包 | `jsonschema`、`PyYAML`、`deap` | Schema 校验 / 配置 / 遗传进化 | 必需 |
| binutils | `nm`/`objdump`/`strings` | 静态特征 / 独立验证 | 必需 |
| Node.js / npm | ≥ 18 | npm 集成 | 可选 |
| rustc / cargo | ≥ 1.75 | Cargo 集成（C/FFI 源） | 可选 |
| JDK + Ghidra | 21 + 12.x | 可选独立验证（PyGhidra） | 可选 |

## 2. 安装

```sh
git clone git@gitee.com:wxp728/REA-Shield.git
# GitHub 镜像：git clone git@github.com:wxp728/REA-Shield.git
cd REA-Shield

# （推荐）安装到虚拟环境或直接使用系统 Python
pip install jsonschema PyYAML deap

# 构建变换引擎（LLVM Pass 插件）
export PATH=/opt/anti-rea-toolchain/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04/bin:$PATH
cmake -S engine -B engine/build -DLLVM_DIR=$LLVM_DIR/lib/cmake/llvm -DCMAKE_BUILD_TYPE=Release
cmake --build engine/build -j

# 自检
python -m core.cli scan tests/samples -o /tmp/ar && echo OK
```

## 3. 快速上手（保护闭环）

```sh
python -m core.cli scan      <你的工程> -o build/run
python -m core.cli plan      build/run/asset_manifest.json -o build/run
python -m core.cli protect   build/run/protection_policy.yaml \
                             --root <你的工程> --source <敏感源文件> -o build/run
python -m core.cli verify    build/run
python -m core.cli attack_sim build/run --benchmark benchmarks/bench-crypto-001.yaml
python -m core.cli report    build/run --format all
```

- `attack_sim` 无 LLM 时自动降级 `static_only`（以静态代理指标判定）。
- `report` 产出 `report.json/md/html`；`diff` 对比两次运行（FR-G3）。

## 4. 构建系统集成

```sh
# CMake：在 CMakeLists 内 include 并挂 POST_BUILD
include(integrations/cmake/AntiRea.cmake)

# npm：scripts.postbuild 调 integrations/npm/anti-rea-protect.js
# Python：setup.py 用 integrations/python/anti_rea_build_ext.py 作为 build_ext
# Cargo：build.rs 调 integrations/cargo
```

统一原则：**集成不内嵌引擎**，均调用驱动 `integrations/anti-rea`（`scan→plan→protect→verify`）；
验证失败时 `--abort-on-failure` 以非零退出中止构建（FR-D7）。

## 5. MCP Server（供 AI Agent 调用）

```sh
anti-rea-mcp            # 或 python -m core.mcp
```

stdio JSON-RPC 2.0，暴露 7 个工具：`anti_rea.scan/plan/protect/verify/attack_sim/report/evolve`。

## 6. 升级

```sh
git fetch --tags && git checkout v1.0.0
cmake --build engine/build -j          # 引擎需随版本重建
python -m core.cli --version           # 确认版本
```

> 数据契约（`schemas/`）向后兼容；跨大版本升级请阅读对应 `CHANGELOG.md` 的「破坏性变更」小节。
