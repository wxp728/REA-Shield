# 试点工程 1：crypto-lib（C / CMake / P0）

一个含**许可校验**与**密钥调度**的 C 库（受保护资产 P0）。用于 S5 Beta 试点的
「按文档独立完成保护闭环」验证。

## 构建

```sh
cmake -S pilots/crypto-lib -B build/pilot1 && cmake --build build/pilot1
build/pilot1/crypto_lib
```

## 保护闭环（按 `docs/INSTALL.md`）

```sh
python -m core.cli scan pilots/crypto-lib -o build/pilot1/anti-rea
python -m core.cli plan  build/pilot1/anti-rea/asset_manifest.json -o build/pilot1/anti-rea
python -m core.cli protect build/pilot1/anti-rea/protection_policy.yaml \
    --root pilots/crypto-lib --source pilots/crypto-lib/src/license.c \
    -o build/pilot1/anti-rea
python -m core.cli verify build/pilot1/anti-rea
python -m core.cli attack_sim build/pilot1/anti-rea \
    --benchmark benchmarks/bench-crypto-001.yaml
python -m core.cli report build/pilot1/anti-rea --format all
```
