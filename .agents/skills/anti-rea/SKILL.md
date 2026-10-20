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
  project's build system. For Java / Android (no LLVM IR transforms) it provides
  a selectable anti-REA option menu (server-side logic, bytecode obfuscation,
  packing, bytecode virtualization, native offload via JNI/JNA/FFM, GraalVM
  native-image, runtime hardening, key management) with principles, trade-offs,
  impacts and tool sources; the user chooses the combination. For .NET / Unity
  (no IL transforms) it provides a D0-D8 menu including NativeAOT and IL2CPP.
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
pip install -r requirements.txt     # minimal (T0): jsonschema + PyYAML
anti-rea doctor                     # environment self-check, grouped by tier
anti-rea doctor --tier T0           # core only; T1/T2/T3 are fetched on demand
make build                          # build the LLVM transform plugin (T1; protect only)
anti-rea scan  <your-project> -o out
anti-rea plan  out/asset_manifest.json -o out
anti-rea protect out/protection_policy.yaml --root <your-project> --source <your-project>/src/main.c -o out
anti-rea verify out && anti-rea attack_sim out --mode all
```

Install minimally and fetch optional, language/platform-specific components only
when the chosen mode needs them — third-party tools are never bundled, only their
sources are recorded. See `docs/PROVISIONING.md`; to hand just the skill to
another project: `python tools/release.py --skill dist`.

Or use the MCP server: `anti-rea-mcp` (stdio JSON-RPC, 7 tools — see
`docs/mcp-clients.md`).

For real-world artifacts (`.so` / large builds) use **mode B**: inject the
compiler wrapper into the project's own build via `anti-rea buildenv` +
`integrations/cc-wrapper/anti-rea-cc` (see root `SKILL.md` and
`docs/build-injection.md`). Before changing anything in the target project,
follow the phased workflow in the root `SKILL.md`: **P0 survey → P1 proposal
(user review) → P2 mode choice → P3 execute → P4 verify** — the skill provides
methodology, not automatic build-system rewrites.

**Java / Android** (no LLVM IR transforms): the skill provides a selectable
anti-REA **option menu** (J0–J8) — see `docs/java-anti-rea.md` (machine-readable
`docs/java-anti-rea-options.yaml`). Present the candidate combinations with
principles / trade-offs / impacts to the user and let them choose; third-party
tools are not bundled, only their sources and usage are recorded.

**.NET / Unity** (no IL transforms): same approach with the **D0–D8** menu —
see `docs/dotnet-anti-rea.md` (machine-readable
`docs/dotnet-anti-rea-options.yaml`). NativeAOT / IL2CPP / native-offload
outputs can be hardened with the regular native pipeline. Note that
ReadyToRun is NOT protection, and public deobfuscators (e.g. de4dot) can undo
some commercial obfuscation — combine layers.

Scope: only harden code you own. v1.0 fully tested on Linux x86_64 with
LLVM/clang 18. See `docs/INSTALL.md` for details, Docker, and environment
variables.
