# 决策记录：OI-05 MTD 变体数量上限与制品签名 / 分发方式

## 文档信息

- **版本**：v1.0
- **日期**：2026-10-15
- **阶段**：S2 详细设计（原定处置阶段：S2）
- **状态**：**已落定**（S2）
- **上游**：`SRS.md` v1.2 §8.3 OI-05、FR-B4（MTD）、FR-G1/G2（产物）、CQ-01/CQ-04、NFR-04/09/10
- **说明**：本决策细化 FR-B4 的 `variant_count` 边界与制品签名/分发方式，**不改变任何已基线需求条目**。

---

## 1. 问题陈述（OI-05）

> MTD 变体数量上限与制品签名 / 分发方式。——影响需求：FR-B4。

## 2. 决策摘要

| 编号 | 决策 |
| :--- | :--- |
| **D1** | `variant_count`：**Schema 上限 64**（不变）；**缺省 8**；**建议 ≤16**；实际值由 DD-02 预算优化裁剪 |
| **D2** | 每个变体携带哈希清单；一次构建的变体集打包为 **signed release bundle**（`release.json` + 分离签名 + SBOM） |
| **D3** | 签名用**项目/发布方密钥**（缺省 minisign/GPG，可配），私钥不入库（NFR-09） |
| **D4** | 随产物分发 **CycloneDX SBOM** 与 **EDR 白名单/签名指引**（CQ-01/CQ-04） |

## 3. D1：变体数量上限

| 项 | 值 | 依据 |
| :--- | :--- | :--- |
| Schema 硬上限 | 64 | `protection_policy.schema.json` `variant_count ∈ [1,64]` |
| 缺省 | 8 | `plan §3.2` 示例 |
| 建议上限 | 16 | 构建时间/存储随变体数线性增长 |
| 生效值 | ≤ 上限 | 由 DD-02 在 `max_overhead` 与构建预算下裁剪（FR-B3） |

- 差异率要求：n 个变体两两差异率 ≥ 预设阈值（FR-B4），由 DD-01/DD-03 的 seed 派生保证（不同 seed → 不同状态置换/编码表）。

## 4. D2/D3：制品签名与分发

```text
变体集/
├── variant_0/{artifacts, transform.log, hashes.json}
├── ...
├── variant_n-1/...
├── release.json          # 变体清单 + 每个变体的哈希 + 元数据(FR-G2)
├── release.json.sig      # 分离签名（minisign/GPG）
└── sbom.cdx.json         # CycloneDX SBOM (CQ-01)
```

- **哈希清单**：每个变体产物 sha256（可复现校验，FR-G2）；
- **签名**：`release.json` 分离签名；验证流程文档化；私钥由发布方保管（CI secret），**不入库**（NFR-09）；
- **分发**：以「签名的 release bundle」为单位分发；每个 bundle 关联 `run_id`。

## 5. D4：EDR 兼容与合规

- 附带 **SBOM**（CycloneDX）与**许可证清单**（CQ-01）；
- 提供 **EDR 白名单 / 签名指引**文档（CQ-04）：签名者信息、哈希清单、误报申诉流程；
- 保护产物**不引入**已知恶意特征（NFR-10），与 CQ-03 的拒绝执行互补。

## 6. 影响与后续

- **FR-B4**：实现须遵守 D1 边界；DD-02 §9 的 MTD 配置据此收敛；
- **FR-G1/G2**：产物目录新增 `release.json`/`*.sig`/`sbom.cdx.json`（`dd-build-integration.md §7`）；
- **CQ-04 / NFR-10**：签名与白名单指引纳入 S5 试点交付；
- **未引入**：v1.0 不做代码签名证书采购（成本），缺省用开源签名工具，企业场景可替换。
