**English** | [简体中文](README.zh-CN.md)

# REA-Shield

> **Where there is a spear, there is a shield. REA is the spear; this skill is the shield.**
>
> Perhaps that day will come soon: AI will develop any software at extremely low cost, and both REA and this "shield" will lose their meaning. But until that day comes, we will always believe in and hold to one thing:
>
> **Cheating is wrong.**
>
> **Goal**: raise REA's cost above, or close to, the cost of forward development.
>
> **Currently**, this skill provides end-to-end protection **only on Linux x86_64**; its transformation engine is built on **LLVM IR** and can target ARM64 / Windows x64 / WASM, etc. (IR-level support; end-to-end verified only on Linux x86_64 so far); more platforms / OSes will be added in future releases.
>
> **Supported source languages**: the transform engine is an LLVM pass loaded via `clang -fpass-plugin`, so protection covers **C / C++** (first-class) plus the **C/FFI parts of Rust** and **Python C-extensions**. Pure **Rust / Java / .NET / JS-TS / Go** get **no IR-level protection** (ADR-006) — but for those languages the toolchain can still **scan** (inventory assets, detect language & build system) and **plan** (produce a protection policy); the protection stages — **protect / verify / attack_sim / report** — are unavailable, since they all build on a clang-compiled run.
>
> **Anti-reverse techniques**: control-flow flattening (CFF), non-linear MBA, opaque predicates, function-boundary perturbation, data-flow noise, identifier renaming, string encryption, code virtualization, white-box cryptography, adversarial inducement, MTD multi-variant; **costs**: runtime overhead (P2 ≤ 5% / P1 ≤ 15% / P0 ≤ 40%, configurable), increased binary size and build time, a heavy LLVM 18 toolchain dependency, and platforms / languages not yet covered end-to-end.
>
> Built with the assistance of Opencode + DeepSeek V4.1 Flash Free.

## Start here (users & agents)

> Want to **use** it rather than read all the development docs? Start here:

| I want to… | Read |
| :--- | :--- |
| Teach an agent to use this skill | **[`SKILL.md`](SKILL.md)** + [`skill.json`](skill.json) (machine-readable) |
| Install / build / environment variables / Docker | [`docs/INSTALL.md`](docs/INSTALL.md) |
| Wire the MCP server into my client | [`docs/mcp-clients.md`](docs/mcp-clients.md) |
| Run an end-to-end example | [`examples/quickstart/`](examples/quickstart/) |
| Troubleshoot | [`docs/FAQ.md`](docs/FAQ.md), [`docs/troubleshooting.md`](docs/troubleshooting.md) |

```bash
pip install -r requirements.txt   # jsonschema / PyYAML / deap
anti-rea doctor                   # environment self-check with fix guidance
make build                        # build the LLVM transform plugin
docker build -t anti-rea:1.0.0 .  # or: pinned image, no manual LLVM18 setup
```

## Repository Status

This repository is in the **coding phase** (S3 iterations R1/R2/R3 complete; M4/M5 approved).

| Phase | Status |
| :--- | :--- |
| S0 Scoping & Requirements | ✅ Done (M0 requirements baseline approved, tag `m0-baseline`) |
| S1 High-Level Design | ✅ Done (design deliverables + **all 4 PoCs passed**, tag `m1-architecture`) |
| S2 Detailed Design | ✅ Done (DD-01…DD-10 + build integration, tag `m2-design`) |
| S3 Coding · R1 | ✅ Done (scaffolding + CFF/MBA/predicates + Scanner/Strategy + end-to-end pipeline, tag `m3-r1`) |
| S3 Coding · R2 | ✅ Done (virtualization / white-box crypto / adversarial inducement / function perturbation / noise / SPI / build integration, tag `m4-r2`) |
| S3 Coding · R3 | ✅ Done (evaluation & verification / adaptive evolution / MCP Server / reporting, tag `m5-frozen`) |
| S4 System Integration & Verification | ✅ Done (differential fuzz 10⁵ / performance / adversarial (built-in + independent) / reproducibility / robustness / compatibility / SBOM; reports in `docs/release/`) |
| S5 Beta Pilot | ✅ Done (3 pilots — C / C++ / Python-ext — closed the protection loop independently; improvements / compliance / release checklist / install guide) |
| S6 Official Release v1.0 | ✅ Done (v1.0.0: skill entry / self-check / container / MCP config / example / release packaging; tag `v1.0.0`) |

> **New to the project? Read [`docs/STATUS.md`](docs/STATUS.md) first** (project status & handoff), then continue from the "next step" listed there.
> **Users: start with [`SKILL.md`](SKILL.md)** (skill entry) and [`docs/INSTALL.md`](docs/INSTALL.md).
>
> **Note**: the detailed design / requirements docs are currently written in Chinese.

## Repository Layout

```text
REA-Shield/
├── SKILL.md                  # ★ Skill entry (start here as a user / agent)
├── skill.json                # ★ Machine-readable skill manifest (tools/env/platform)
├── README.md / README.zh-CN.md  # Overview (EN / 中文)
├── LICENSE                   # MIT
├── CHANGELOG.md              # Version history
├── Dockerfile                # Pinned image (LLVM18 + Python3.11 + engine plugin)
├── .agents/skills/anti-rea/  # Skill manifest location (points to root SKILL.md)
├── examples/quickstart/      # Runnable end-to-end example
├── plan/                     # Plan & project plan
│   ├── anti-rea-plan.md              # Original technical plan (capability-module oriented)
│   └── anti-rea-project-plan.md      # Full-lifecycle project plan (phases/milestones/exit criteria)
├── docs/
│   ├── STATUS.md             # ★ Project status & handoff (new-session entry point)
│   ├── INSTALL.md            # Install / build / env vars / Docker
│   ├── mcp-clients.md        # MCP client config (paste-ready)
│   ├── FAQ.md、troubleshooting.md    # FAQ & troubleshooting
│   ├── requirements/         # S0 deliverables
│   │   ├── SRS.md                    # Software Requirements Spec (47 FR + 11 NFR + 5 CQ)
│   │   ├── use-cases.md              # Use cases
│   │   ├── rtm.md                    # Requirements Traceability Matrix
│   │   └── compliance.md             # Compliance & boundary requirements
│   └── design/               # S1/S2 deliverables
│       ├── HLD.md                    # High-Level Design (S1)
│       ├── interfaces.md             # Interface contracts (module/MCP/CLI/SPI/error codes)
│       ├── ADR.md                    # Architecture Decision Records (ADR-001…007)
│       ├── poc-plan.md              # Technology PoC plan (PoC-1…4)
│       └── ddd/                      # S2 Detailed Design
│           ├── README.md                    # Index / task tracking / M2 exit mapping
│           ├── e2e-scenario.md              # End-to-end Agent invocation scenario (main line)
│           ├── dd-01-scanner.md … dd-08-adaptive.md  # Module detailed designs
│           ├── dd-09-test-plan.md           # Test plan (covers all requirements)
│           ├── dd-build-integration.md      # Build integration & artifact management
│           ├── dd-10-review.md              # Detailed-design review (M2 gate)
│           └── decisions/                   # OI-05 / OI-07 decision records
├── schemas/                  # Data contracts (JSON Schema, Draft 2020-12)
│   ├── asset_manifest.schema.json
│   ├── protection_policy.schema.json
│   ├── verification_report.schema.json
│   ├── eval_report.schema.json
│   └── benchmark.schema.json
├── engine/                   # S3 transformation engine (LLVM Pass plugin)
│   ├── CMakeLists.txt
│   ├── README.md
│   └── passes/anti_rea_passes.cpp    # CFF / MBA / opaque predicates / whitelist / virtualization / anchor removal
├── core/                     # S3 orchestration core (Python)
│   ├── scanner/              #   Input analysis layer (Scanner v0.1)
│   ├── strategy/             #   Strategy decision layer (Strategy Engine v0.1)
│   ├── evaluate/             #   Evaluation layer (differential verify + attack sim + metrics / timeseries / regression)
│   ├── adaptive/             #   Adaptive strategy engine (DEAP evolution + weakness tuning + knowledge base)
│   ├── mcp/                  #   MCP Server (stdio JSON-RPC 2.0, 7 tools)
│   ├── verify/               #   S4 system verification (differential fuzz / perf / independent cross-check / reproducibility / robustness / compatibility)
│   ├── transform.py          #   Transform execution (drives the engine plugin)
│   ├── toolchain.py          #   Toolchain discovery + doctor self-check (no hardcoded paths)
│   ├── platform_info.py      #   Platform / target-environment detection
│   ├── report.py             #   Reporting & artifact management (unified dir / metadata / diff)
│   ├── common.py             #   Schema validation / run_id / IO
│   └── cli.py                #   CLI entry (doctor/scan/plan/protect/verify/report/attack_sim/regress/diff/evolve)
├── tools/                    # S4/S5/S6 tools (run_s4.py / run_s5.py / sbom.py / release.py / ghidra_functions.py)
├── pilots/                   # S5 Beta pilots (crypto-lib / protocol-svc / python-ext)
├── docs/release/             # S4/S5 verification & release artifacts (STR/perf/adversarial/compatibility/SBOM/pilot/release checklist)
├── docs/INSTALL.md           # Install & upgrade guide
├── policies/                 # Strategy template library + matching rules
├── integrations/             # Build integration (CMake/Cargo/npm/Python/MCP, R2+)
├── plugins/                  # Transformation plugin SPI (R2+)
├── benchmarks/               # Attack-simulation benchmark suite (R3)
├── tests/                    # Unit / integration tests + samples
├── ci/ci.sh                  # CI gate
├── Makefile                  # build / test / e2e / ci
└── poc/                      # S1 technology PoCs (executable code & evidence)
    ├── poc1-llvm-pass/       #   LLVM Pass: control-flow flattening (CFF)
    ├── poc2-ghidra-headless/ #   Ghidra Headless (PyGhidra) batch decompilation
    ├── poc3-deap/            #   DEAP strategy-evolution prototype
    ├── poc4-wbc/             #   White-box lookup-table encoding (AES)
    └── setup_env.sh          #   Environment setup script
```

## Quick Navigation

| I want to… | Look here |
| :--- | :--- |
| **Hand the skill to an agent / person new to the project** | **[`SKILL.md`](SKILL.md)** + [`docs/INSTALL.md`](docs/INSTALL.md) + [`docs/mcp-clients.md`](docs/mcp-clients.md) |
| Understand what this project does | `plan/anti-rea-plan.md` |
| Understand the development process & milestones | `plan/anti-rea-project-plan.md` |
| Know the current progress / how to take over | `docs/STATUS.md` |
| Check requirements & acceptance criteria | `docs/requirements/SRS.md` |
| Check architecture & interfaces | `docs/design/HLD.md`, `docs/design/interfaces.md` |
| Check the rationale behind technical choices | `docs/design/ADR.md` |
| See the PoC plan & conclusions | `docs/design/poc-plan.md`, `poc/` |
| See detailed design / the end-to-end scenario | `docs/design/ddd/README.md`, `docs/design/ddd/e2e-scenario.md` |
| Build & run (R1) | `engine/README.md`, `Makefile` (`make build/test/e2e/ci`) |
| Continue de-risking verification | `docs/design/poc-plan.md` |

## Conventions

- Requirement IDs: `FR-<layer><number>` / `NFR-<number>` / `CQ-<number>`; priority via MoSCoW.
- All cross-module data must pass validation against `schemas/` (fail-fast).
- Line endings are LF (see `.gitattributes`).
- Document changes must record a version bump and change history.
