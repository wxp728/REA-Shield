---
name: anti-rea
description: >-
  Harden code you own against reverse-engineering agents (REA). LLVM-based
  obfuscation toolchain with a CLI (anti-rea) and an MCP server (anti-rea-mcp):
  scan assets, plan a policy, protect, verify functional equivalence, simulate
  an attack. Use for C/C++ (also Rust C/FFI sources and Python C-extensions).
  Works in phases: survey -> proposal for user review -> user picks a mode
  (one-shot build / build-architecture transformation) -> verify. The skill
  provides information and methodology; it does not auto-modify the target
  project's build system.
license: MIT
version: 1.0.0
---

# REA-Shield

This is the skill manifest location. The **canonical, full instructions** live at
the repository root:

➡️ **[`SKILL.md`](../../../SKILL.md)**

Machine-readable manifest: **[`skill.json`](../../../skill.json)**

## TL;DR

```bash
pip install -r requirements.txt     # jsonschema, PyYAML, deap
anti-rea doctor                     # environment self-check (fast-fails w/ guidance)
make build                          # build the LLVM transform plugin
anti-rea scan  <your-project> -o out
anti-rea plan  out/asset_manifest.json -o out
anti-rea protect out/protection_policy.yaml --root <your-project> --source <your-project>/src/main.c -o out
anti-rea verify out && anti-rea attack_sim out --mode all
```

Or use the MCP server: `anti-rea-mcp` (stdio JSON-RPC, 7 tools — see
`docs/mcp-clients.md`).

For real-world artifacts (`.so` / large builds) use **mode B**: inject the
compiler wrapper into the project's own build via `anti-rea buildenv` +
`integrations/cc-wrapper/anti-rea-cc` (see root `SKILL.md` and
`docs/build-injection.md`). Before changing anything in the target project,
follow the phased workflow in the root `SKILL.md`: **P0 survey → P1 proposal
(user review) → P2 mode choice → P3 execute → P4 verify** — the skill provides
methodology, not automatic build-system rewrites.

Scope: only harden code you own. v1.0 fully tested on Linux x86_64 with
LLVM/clang 18. See `docs/INSTALL.md` for details, Docker, and environment
variables.
