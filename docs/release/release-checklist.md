# 发布清单（Release Checklist）与 Go/No-Go

> S5 出口「发布 checklist 完成」；S6（M8）据此执行发布。勾选项须有可复核证据。

## 1. 质量门（M6）

- [x] 全平台 CI 绿；单测通过率 100%（66 用例，`bash ci/ci.sh`）
- [x] 差分 fuzz 10⁵ 随机输入无行为差异（`docs/release/STR.md §2`）
- [x] 性能开销落在 NFR-01 预算内（`docs/release/performance-baseline.md`）
- [x] 对抗效果内置达标 + 独立工具交叉验证不矛盾（`docs/release/adversarial-report.md`）
- [x] 可复现性：同输入同种子产物逐位一致（`docs/release/STR.md §1`）
- [x] 稳健性：异常输入受控 / 超时受控 / 大工程可扩展（`docs/release/STR.md §1`）
- [x] 无未修复 P0/P1 缺陷（`docs/release/defects.md`）
- [x] 安全自检：SBOM 齐全、依赖许可证齐全（`docs/release/sbom.json`）
- [ ] **NFR-02 Token 消耗倍数 ≥ 100x**（需真实 LLM；CQ-05，S5→发布前补测）
- [ ] **外部第三方红队结论**（需独立 LLM/红队；S5→发布前补测）

## 2. 试点门（M7）

- [x] ≥ 2 个试点工程独立完成保护闭环（`docs/release/pilot-report.md`，3 个）
- [x] 各试点功能保持 + 对抗判定通过
- [x] 改进项清单已闭环（`docs/release/improvements.md`）
- [x] 合规审查通过（`docs/release/compliance-review.md`，CQ-04/05 观察项已记录）
- [x] 安装/升级指南可用（`docs/INSTALL.md`）

## 3. 发布准备（S6）

- [ ] 版本号冻结（`pyproject.toml` = 1.0.0）与 `CHANGELOG.md`
- [ ] 构件打包（sdist/wheel）+ 哈希清单
- [ ] 发布说明（`docs/release/RELEASE-1.0.0.md`）与快速开始 Demo（`examples/quickstart/`）
- [ ] 支持渠道（Issue 模板 / FAQ / 故障排查）
- [ ] 打 tag `v1.0.0` 并推送

## 4. Go/No-Go 判定

**Go（有条件）**：M6/M7 全部达成；两项「需真实 LLM」的门槛作为**已知条件项**随发布说明披露，
并在 S7（运维）持续补测。若发布方要求 NFR-02 量化门禁硬性达标，则**No-Go**，直至完成 LLM 会话计量。

> 判定人：发布经理 / 项目负责人。日期：______。
