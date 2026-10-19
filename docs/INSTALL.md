# 安装与升级指南（Install & Upgrade）

> 面向 **Linux x86_64**（v1.0 已实测平台）。其他平台见
> `docs/release/compatibility-matrix.md`。

## 0. 安装策略：最小安装 + 按需获取

> **本技能只交付自己的源码**（Python 引擎 + LLVM Pass 源码 + 集成脚本 + 文档），
> **不打包、不预装、不代下载任何第三方工具**；第三方组件一律只记录**获取源与用法**。
> 完整策略、体量量级、最小部署集与卸载见 [`PROVISIONING.md`](PROVISIONING.md)。

| 分级 | 什么时候才需要 | 组成 | 装法 |
| :--- | :--- | :--- | :--- |
| **T0 核心（必装）** | 始终（`scan`/`plan`/`doctor`/`report`） | Python ≥ 3.11、`jsonschema`、`PyYAML` | `pip install -r requirements.txt` |
| **T1 原生变换** | 选定模式 A/B 且要 `protect`/`verify`/`attack_sim` | LLVM/clang 18、CMake ≥ 3.16、binutils、`file` | 系统包 + `make build` |
| **T2 语言与平台** | 按目标语言 / 构建体系 / 宿主平台 | rustc+cargo、node+npm（仅扫描）、JDK（用工程自带）、容器运行时 | 各自按需 |
| **T3 可选增强** | 只在用到该功能时 | Ghidra+PyGhidra、`deap`（`evolve`）、LLM 端点（红队） | `pip install -r requirements-optional.txt` 等 |
| **T4 永不下发** | — | Java/Android 第三方加固工具/产品 | 自行获取（见 [`java-anti-rea.md`](java-anti-rea.md)） |

**默认只装 T0**；缺 T1/T2/T3 不阻塞 `scan`/`plan`——`anti-rea doctor` 会按分级分组，
标出每项的「何时需要 / 怎么装」。

### 0.1 最小安装（推荐起步，T0）

```sh
git clone https://gitee.com/wxp728/REA-Shield.git   # 或 GitHub 镜像：https://github.com/wxp728/REA-Shield
cd REA-Shield
pip install -r requirements.txt     # 仅 jsonschema + PyYAML
anti-rea doctor --tier T0           # 只看最小集
anti-rea scan <你的工程> -o out      # scan/plan 无需编译器
```

### 0.2 只把技能装到别的项目（不带开发材料）

```sh
python tools/release.py --skill dist   # → dist/anti-rea-skill-<version>.tar.gz + SKILL-FILES.txt
```

技能包只含运行与接线所需文件；`tests/`、`ci/`、`poc/`、`pilots/`、`benchmarks/`、
设计文档等**不下发**（需要时再从仓库取）。

### 0.3 容器路径（较重，可选；开箱即用）

不想手工拼装 LLVM18 + 插件？用仓库根目录的钉死镜像。**注意这是较重的一条路径**
（镜像内带整套 LLVM）；只想跑 `scan`/`plan` 的话用 §0.1 最小安装即可：

```sh
git clone https://gitee.com/wxp728/REA-Shield.git   # 或 GitHub 镜像：https://github.com/wxp728/REA-Shield
cd anti-rea
docker build -t anti-rea:1.0.0 .    # 镜像构建期联网获取 Debian 包（LLVM 18 等）
# 需要 evolve 时再加：--build-arg WITH_EXTRAS=1（会带 deap/numpy）

# 直接跑 CLI（宿主目录挂进 /work）
docker run --rm -v "$PWD:/work" anti-rea:1.0.0 doctor
docker run --rm -v "$PWD:/work" anti-rea:1.0.0 scan /work/tests/samples -o /work/out

# 以 MCP stdio 服务器方式运行（供上层 Agent 调用）
docker run --rm -i anti-rea:1.0.0 mcp
```

镜像内固定 Python 3.11 + LLVM/clang 18 + 已构建的变换插件，`doctor` 在构建期
即自检通过。**Windows 用户建议用 Docker 或 WSL**（变换引擎是 Linux 共享库插件）。

## 1. 依赖

| 组件 | 版本 | 用途 | 是否必需 | 分级 |
| :--- | :--- | :--- | :--- | :--- |
| Python | ≥ 3.11 | 编排核心 / 评估 | 必需 | T0 |
| Python 包 | `jsonschema`、`PyYAML` | Schema 校验 / 配置 | 必需 | T0 |
| Python 包 | `deap`（连带 numpy） | 遗传进化 `evolve` | 可选① | T3 |
| LLVM/clang | 18.x | 变换引擎宿主 + 编译 | 必需③ | T1 |
| CMake | ≥ 3.16 | 构建引擎 | 必需③ | T1 |
| binutils | `nm`/`objdump`/`strings` | 静态特征 / 独立验证 | 必需③ | T1 |
| Node.js / npm | ≥ 18 | npm 集成（仅扫描/识别） | 可选 | T2 |
| rustc / cargo | ≥ 1.75 | Cargo 集成（C/FFI 源） | 可选 | T2 |
| JDK + Ghidra | 21 + 12.x | 可选独立验证（PyGhidra） | 可选 | T2/T3 |

① `deap` **默认不装**（它是本技能唯一"偏重"的 Python 依赖，会连带 numpy）：
只在要用 `anti-rea evolve` 时 `pip install -r requirements-optional.txt`。

③ `scan`/`plan` 只需要 Python + Python 包；LLVM/CMake/binutils 是
`protect`/`verify` 的依赖。缺什么、怎么修，`anti-rea doctor` 会直接告诉你。

## 2. 安装（源码）

```sh
git clone https://gitee.com/wxp728/REA-Shield.git   # 或 git@gitee.com:wxp728/REA-Shield.git
# GitHub 镜像：git clone git@github.com:wxp728/REA-Shield.git
cd REA-Shield

# 依赖（T0 最小）
pip install -r requirements.txt      # 仅 jsonschema + PyYAML
# 可选（T3）：pip install -r requirements-optional.txt   # deap（evolve 用）

# 环境自检（按分级分组：缺什么、何时需要、怎么修）
anti-rea doctor                      # 或：python -m core.cli doctor
anti-rea doctor --tier T0            # 只看最小集

# 构建变换引擎（LLVM Pass 插件）——**仅 protect/verify 需要（T1）**，路径自动探测
make build                           # 等价于 cmake -S engine -B engine/build \
                                     #          -DLLVM_DIR=$(llvm-config --cmakedir) && cmake --build engine/build -j
```

> **T1 组件（LLVM/clang 18、CMake、binutils）由你自行安装**（系统包管理器 / 官方
> 发布页），本技能不分发它们。等 P2 选定模式 A/B、确实要 `protect` 时再装即可。

### LLVM 定位（不再写死路径）

工具链定位优先级：**环境变量 > PATH > 常见安装目录**。若 clang 不在 PATH：

```sh
export ANTI_REA_LLVM=/usr/lib/llvm-18          # LLVM 安装前缀（其下有 bin/）
# 或 make/ci 时：make build LLVM=/usr/lib/llvm-18
# 或单独指定可执行文件：
export ANTI_REA_CLANG=/usr/lib/llvm-18/bin/clang
```

`anti-rea doctor --llvm /usr/lib/llvm-18` 可临时指定前缀做自检。

### 常用环境变量

| 变量 | 作用 |
| :--- | :--- |
| `ANTI_REA_LLVM` / `ANTI_REA_LLVM_BIN` | LLVM 前缀 / bin 目录 |
| `ANTI_REA_CLANG` / `ANTI_REA_OPT` | 显式指定可执行文件 |
| `ANTI_REA_PLUGIN` / `ANTI_REA_VM_BC` | 插件 / VM 解释器路径 |
| `ANTI_REA_WHITELIST` / `ANTI_REA_STRATEGIES` / `ANTI_REA_SEED` | 变换白名单 / 策略 / 随机种子 |
| `ANTI_REA_RENAME_EXTERNAL` | 是否重命名**外部链接**函数（默认 `1`）。多编译单元工程改名会断链，`protect` 多源时自动置 `0`；单文件/整程序可保持 `1`。 |
| `ANTI_REA_CONST_ENCODE` | `string_encryption` 下是否启用**常数编码**（默认 `1`）：把可疑整型立即数（SM4 FK / SM3 IV 等）收进本函数常量池、用运行期解码取值。设 `0` 关闭。 |
| `ANTI_REA_STRIP` | 链接后是否 `strip --strip-unneeded`（默认 `0`）。由 `buildenv --strip` 置 `1`；隐藏产物的本地符号名。 |
| `ANTI_REA_VERSION_SCRIPT` | 链接期 `-Wl,--version-script` 的版本脚本路径（导出收敛）。由 `buildenv --exports` 写入 `scope.env`。 |
| `ANTI_REA_GHIDRA=1` + `GHIDRA_INSTALL_DIR` | 启用 Ghidra 独立验证 |
| `ANTI_REA_LLM_CMD` / `ANTI_REA_LLM_ENDPOINT` 等 | 接入真实 LLM 会话（攻击模拟） |
| `ANTI_REA_ROOT` | wheel 安装场景下指向含 `schemas/`、`policies/` 的目录 |

### LLM 会话判定（FR-E3，可选）

`attack_sim --allow-llm` 会经 `core.evaluate.llm` 开**独立会话**，对 baseline / protected 各做一次
同协议逆向，产出 `token_ratio` / `time_ratio` / `name_recovery_accuracy` / `function_judgement_accuracy`
等（判定口径见 `docs/design/ddd/decisions/OI-07-rea-success-criteria.md`）。两种出站方式二选一：

- **本地命令钩子** `ANTI_REA_LLM_CMD`：stdin 收提示词、stdout 回 `{"output":...,"tokens_used":...}`。
  本机 OpenCode 可直接用：`export ANTI_REA_LLM_CMD="$PWD/tools/opencode_llm_hook.sh"`。
- **OpenAI 兼容 HTTP**：`ANTI_REA_LLM_ENDPOINT`（`/chat/completions`）+ `ANTI_REA_LLM_MODEL`
  （+ 可选 `ANTI_REA_LLM_KEY`）。

未配置时自动降级 `static_only`（OI-07 §D5）。会话窗口经 `ANTI_REA_LLM_WINDOW` 指定（默认 128000）。

## 3. 快速上手（保护闭环）

```sh
anti-rea scan       <你的工程> -o build/run
anti-rea plan       build/run/asset_manifest.json -o build/run
anti-rea protect    build/run/protection_policy.yaml \
                    --root <你的工程> --source <敏感源文件> -o build/run
anti-rea verify     build/run
anti-rea attack_sim build/run --mode all
anti-rea report     build/run --format all
```

端到端可运行示例见 [`../examples/quickstart/`](../examples/quickstart/)：

```sh
bash examples/quickstart/run.sh
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
面向常见客户端的**可直接粘贴配置**见 [`mcp-clients.md`](mcp-clients.md)。

## 6. 升级

```sh
git fetch --tags && git checkout v1.0.0
make build                             # 引擎需随版本重建
anti-rea --version                     # 确认版本
```

> 数据契约（`schemas/`）向后兼容；跨大版本升级请阅读 [`CHANGELOG.md`](../CHANGELOG.md)
> 的「破坏性变更」小节。

## 7. 卸载

源码安装：删除目录即可（Python 包为可编辑/就地使用，不污染环境）。
容器安装：`docker rmi anti-rea:1.0.0`。

按需组件可**即插即拔**、互不影响：`pip uninstall deap`、删掉镜像、删掉 Ghidra 目录、
`unset ANTI_REA_LLM_ENDPOINT` / `ANTI_REA_GHIDRA`；`engine/build/` 是本地构建产物，
可随时删除（需要时再 `make build`）。回到最小（T0）状态不会影响 `scan`/`plan`。
