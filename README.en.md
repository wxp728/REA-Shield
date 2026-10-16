# Anti-REA Skill

> An **AI-agent-callable code-hardening skill**: apply multi-layer protection
> transforms to source code / binaries so that AI-driven reverse-engineering
> tools (REA-class) become **more expensive to run than they are worth**. The
> goal is not "unbreakable" — it is "not worth breaking".

🇨🇳 中文版见 [`README.md`](README.md) · 技能入口 [`SKILL.md`](SKILL.md)

## Start here (users & agents)

| I want to… | Read |
| :--- | :--- |
| Teach an agent to use this skill | **[`SKILL.md`](SKILL.md)** + [`skill.json`](skill.json) |
| Install / build / env vars / Docker | [`docs/INSTALL.md`](docs/INSTALL.md) |
| Wire the MCP server into my client | [`docs/mcp-clients.md`](docs/mcp-clients.md) |
| Run an end-to-end example | [`examples/quickstart/`](examples/quickstart/) |
| Troubleshoot | [`docs/FAQ.md`](docs/FAQ.md), [`docs/troubleshooting.md`](docs/troubleshooting.md) |

```bash
pip install -r requirements.txt   # jsonschema / PyYAML / deap
anti-rea doctor                   # environment self-check with fix guidance
make build                        # build the LLVM transform plugin
docker build -t anti-rea:1.0.0 .  # or: pinned image, no manual LLVM18 setup
```

## What it does

A toolchain (not just a prompt) that hardens **code you own** against automated
reverse engineering:

- **Engine** — LLVM pass plugin: control-flow flattening, MBA, opaque predicates,
  string encryption, code virtualization, function splitting/noise, debug-anchor
  removal, plus an in-process C++ SPI for external passes.
- **CLI** — `anti-rea doctor|scan|plan|protect|verify|report|attack_sim|regress|diff|evolve`.
- **MCP server** — `anti-rea-mcp`, stdio JSON-RPC, 7 tools, for agent integration.
- **Verification** — differential functional checks, performance budgets,
  independent cross-check (objdump / optional Ghidra), reproducibility, SBOM.

## Scope & limits (v1.0)

- **Only harden code you own.** Open-source components are skipped by default.
- LLVM-IR transforms cover **C/C++**; Rust (C/FFI sources only) and Python
  (C-extensions only) are supported via build integration. Pure Rust / Java /
  .NET / JS/TS get scanning only — no IR-level protection (ADR-006).
- Fully tested on **Linux x86_64** with **LLVM/clang 18**. Other platforms can
  run `scan`/`plan`; `protect` requires the built plugin (use Docker/WSL
  elsewhere).
- Threat model: **raise the cost**, not achieve impossibility.

## Project status

| Stage | Status |
| :--- | :--- |
| S0–S3 (requirements → R1/R2/R3 implementation) | ✅ done |
| S4 System integration & verification | ✅ done (fuzz 10⁵, perf, adversarial, reproducible, SBOM) |
| S5 Beta pilots | ✅ done (3 pilots, independent closed loop) |
| S6 Release v1.0 | ✅ done (tag `v1.0.0`) |

See [`docs/STATUS.md`](docs/STATUS.md) for the handoff/state of record.

## License

MIT (see [`LICENSE`](LICENSE)). Only apply to code you are authorized to modify.
