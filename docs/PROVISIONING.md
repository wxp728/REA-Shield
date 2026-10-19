# 安装与按需获取（Provisioning）——最小部署 + 按需下载

> **原则（对所有语言一致）**：本技能**只交付自己的源码**（Python 引擎 + LLVM Pass 源码 +
> 集成脚本 + 文档）。**不打包、不预装、不代下载任何第三方工具或商用加固产品**；
> 第三方组件一律**记录获取源与用法**，由用户在自己选定的时机安装。
>
> **目标**：默认安装尽量小、尽量快；**不必然用到的组件先不下载**，等用户选定语言/模式/
> 可选功能后再按需获取。这也是 `SKILL.md` 分阶段工作流（P0 勘察 → P1 方案 → ……）里
> "依赖与环境安装清单"的落地依据。

## 0. 一句话回答「安装本技能会下载什么？」

| 你选的最小路径 | 会下载什么 | 体量量级 |
| :--- | :--- | :--- |
| **只读 / 只用 scan+plan**（T0） | 本仓库源码 + `jsonschema` + `PyYAML` | 数 MB |
| **要 protect C/C++**（再加 T1） | LLVM/clang 18 + cmake + binutils（系统包），并**本地编译**本仓库插件 | LLVM 包几百 MB 级 |
| **走容器**（不想在宿主装 LLVM） | 自建镜像时联网取 Debian 包（LLVM 18 等） | 镜像 1 GB 级 |
| **可选增强**（T3） | Ghidra + PyGhidra / `deap`(+numpy) / LLM 端点 | 按需，最重的一项 |
| **Java / Android 加固**（T4） | **不由本技能下载**：ProGuard / R8 / yGuard / DexGuard / DashO / Zelix / GraalVM / jadx … 自行获取 | — |

> 体量为量级参考、不承诺；以包管理器实际输出为准。**本技能仓库里没有第三方二进制、也没有第三方源码镜像。**

## 1. 分级（tier）与触发条件

| 分级 | 什么时候才需要 | 组成 | 随技能分发？ |
| :--- | :--- | :--- | :--- |
| **T0 核心（必装，最小）** | 始终 | Python ≥ 3.11；`jsonschema`、`PyYAML`；本仓库 `core/`、`schemas/`、`policies/` | 源码随包；依赖由 `pip` 装 |
| **T1 原生变换** | **选定模式 A/B 且要对原生代码施加变换**（protect/verify/attack_sim）时 | LLVM/clang 18（`clang`、`opt`、`llvm-config`）、cmake ≥ 3.16、binutils（`nm`/`objdump`/`strings`）、`file`；本地 `make build` 编译插件 | **否**（用户自备系统包；插件由本仓库源码编译） |
| **T2 语言与平台扩展** | 按**目标的语言 / 构建体系 / 宿主平台**选装 | rustc+cargo（Rust C/FFI 源）；node+npm（JS/TS **仅扫描**）；JDK/构建工具（Java/Android 勘察 —— 用你工程已有的）；容器运行时（宿主平台不匹配或不想装 LLVM 时） | **否**（用目标项目自己的工具链） |
| **T3 可选增强** | 只在用到该功能时 | Ghidra + PyGhidra（独立第三方交叉验证）；`deap`（`anti-rea evolve`，会连带 numpy）；LLM 出站端点（`attack_sim --allow-llm` 的红队会话） | **否**（用户自备；凭据/配额自管） |
| **T4 永不下发** | — | Java/Android 第三方加固工具与商用产品：ProGuard、R8、yGuard、Zelix KlassMaster、Allatori、DashO、DexGuard、GraalVM、jadx、CFR、Vineflower… | **否**（只记录获取源与用法，见 `docs/java-anti-rea.md`） |

**延迟策略**：默认只装 T0；T1/T2/T3 各自独立、可后装；T4 永不代取。
装与不装**互不阻塞**——缺 T1 时 `scan`/`plan` 照常可用（`doctor` 会明确告知"选到该功能时再装"）。

## 2. 最小部署集（skill-only deploy）

要**拷贝/分发**哪些文件才够用（容器镜像或其他方式同理）：

| 用途 | 需要的文件 | 说明 |
| :--- | :--- | :--- |
| **必带（T0）** | `SKILL.md`、`skill.json`、`core/`、`schemas/`、`policies/`、`requirements.txt`、`pyproject.toml` | 缺 `schemas/`/`policies/` 会报"找不到 schemas/policies"（见 FAQ） |
| **要 protect 时再加（T1）** | `engine/`（源码）、`Makefile`、`integrations/`（构建注入用） | 插件在本地编译；**不打包预编译 `.so`** |
| **按需再加（T2/T3）** | `requirements-optional.txt`（evolve）、`Dockerfile`（容器路径） | 用不到就不带 |
| **可以不下发（参考/开发用）** | `docs/design/`、`docs/release/`、`docs/analysis/`、`docs/requirements/`、`docs/STATUS.md`、`tests/`、`ci/`、`benchmarks/`、`pilots/`、`poc/` | 审计/复现/维护用；**不是运行时必需** |

一键生成最小技能包（不含 tests/poc/pilots/设计文档等）：

```bash
python tools/release.py --skill dist     # → dist/anti-rea-skill-<version>.tar.gz
```

## 3. Agent 侧纪律（省 token 也是省部署代价）

1. **先最小、后按需**：P0 只做 `doctor`（T0）+ `scan`；**在用户选定模式之前**不要装 LLVM、
   不要拉镜像、不要下载 Ghidra。
2. **只读需要的那份文档**：`SKILL.md` + 与当前语言/模式相关的**一篇**（`docs/build-injection.md`
   或 `docs/java-anti-rea.md`）；不要把 `docs/` 全量读进上下文。
3. **把"要装什么"写进 P1 方案**：按 §1 列出「现在就装 / 选定模式后再装 / 可选功能再装」三档，
   附触发条件与用户是否同意；未选到的组件标"延后安装"。
4. **安装动作先经用户确认**：装系统包、拉镜像、下载第三方工具前说明体量与影响；
   工具许可与凭据由用户自管（本技能不代管 token）。
5. **装不上如实回报**，不要悄悄换用其他组件或假装成功。

## 4. 与分阶段工作流（`SKILL.md`）的接线

| 阶段 | 该做什么 |
| :--- | :--- |
| **P0 勘察** | 跑 `doctor`（默认全部，按 tier 分组显示）；只读源码与配置，**不安装任何东西** |
| **P1 方案** | "依赖与环境安装清单"按 tier 分列：T0 立即、T1 视模式、T2/T3 视语言与可选功能；T4 只给获取源 |
| **P2 决策** | 用户选 A/B/C → 决定 T1 是否必需；用户选语言 → 决定 T2；是否要独立验证/红队 → 决定 T3 |
| **P3 执行** | 只装本阶段真正需要的组件；每项安装前后可核对 `doctor --tier <T>` |
| **P4 验证** | 不需要的组件保持未装状态（更小的环境 = 更小的攻击面与更好的可复现性） |

## 5. 命令速查

```bash
anti-rea doctor                 # 全部检查（按 tier 分组：标出"何时需要 / 怎么装"）
anti-rea doctor --tier T0       # 只看最小集（必装）
anti-rea doctor --tier T1       # 只看原生变换所需（protect/verify）
anti-rea doctor --json          # 机器可读（每项含 tier / when / required / hint）
pip install -r requirements.txt             # T0：最小
pip install -r requirements-optional.txt    # T3：按需（evolve）
python tools/release.py --skill dist        # 生成最小技能包
```

## 6. 卸载与回退

- **按需即插即拔**：`pip uninstall deap`、删掉容器镜像、删掉 Ghidra 目录、`unset
  ANTI_REA_LLM_ENDPOINT` / `ANTI_REA_GHIDRA` 即可回到最小状态。
- 本技能自身除了可选的 `pip install -e .`（提供 `anti-rea` / `anti-rea-mcp` 入口）外，
  **不做系统级安装**；`engine/build/` 是本地构建产物，可直接删除（需要时再 `make build`）。

## 7. C/C++（原生）侧审查结论

问题："原生侧的反逆向工具是**一起下载/打包**的，还是也符合'只记录来源'的原则？"

**结论：符合——原生侧从来没有打包第三方工具。** 具体地：

- 原生侧需要的一切都是**外部依赖**：LLVM/clang 18、cmake、binutils（T1）；Ghidra/PyGhidra（T3）——
  由用户自行安装，本技能只在 `doctor` 里检测并给出安装指引。
- 仓库内**没有**第三方二进制，也没有第三方源码镜像；`engine/build/anti_rea_passes.so`、
  `vm_interp.bc` 都是**由本仓库自己的源码编译**出来的，且**不随包分发**（打包排除 + `.gitignore`）。
- 唯一在"安装期"联网获取第三方的是 **`Dockerfile` 构建镜像**（Debian 包：LLVM 18 等）——
  这是**可选的容器路径**，属于"按需获取"的一种形态，已在 Dockerfile 注释与本文说明。
- 与 Java 侧完全一致：`docs/java-anti-rea.md` 的 T4 工具同样只记录**获取源与用法**。

> 本轮同时修正了一处与"不提交本地环境信息"原则不一致的旧代码：工具链兜底搜索路径从
> 写死的本机目录改为通用通配（`/opt/*/clang+llvm-*` 等），行为不变、换机更稳。
