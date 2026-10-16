# 发布上传清单（maintainer 执行）

> 需要**凭据**的步骤由维护者在可联网环境执行；本仓库与自动化流程中**不包含**
> 任何 token / 密钥。

## 0. 前置

```bash
cd /path/to/anti-rea
make doctor                 # 环境全绿
bash ci/ci.sh               # 门禁全绿
python tools/release.py     # 产出 dist/（含 MANIFEST.sha256、SIGNING.md）
python tools/release.py --verify dist
```

## 1. 打标签

```bash
git tag -a v1.0.0 -m "Anti-REA Skill v1.0.0"
git push origin v1.0.0
```

## 2. Gitee Release（主站）

1. 打开 `https://gitee.com/wxp728/REA-Shield/releases/new`。
2. 标题：`Anti-REA Skill v1.0.0`；标签选 `v1.0.0`。
3. 正文：粘贴 `docs/release/RELEASE-1.0.0.md`。
4. 附件上传 `dist/` 下的产物：
   - `anti-rea-1.0.0-bundle.tar.gz`（**主产物**）
   - `anti_rea-1.0.0-py3-none-any.whl`
   - `anti_rea-1.0.0.tar.gz`（如生成）
   - `MANIFEST.sha256`
   - `*.asc`（维护者离线签名，见 `dist/SIGNING.md`）

## 3. GitHub 镜像 / Release（可选）

```bash
git remote add github git@github.com:wxp728/REA-Shield.git   # 若尚未配置
git push github v1.0.0
# 用 gh CLI 创建 Release 并上传附件：
gh release create v1.0.0 dist/*.tar.gz dist/*.whl dist/MANIFEST.sha256 \
    --title "Anti-REA Skill v1.0.0" \
    --notes-file docs/release/RELEASE-1.0.0.md
```

> 两个远端可分别用不同的 SSH 私钥（在 `~/.ssh/config` 中按 Host 指定）；


## 4. PyPI（可选，需 token）

wheel/sdist 为次要件；安装后 `schemas/`、`policies/` 需 `ANTI_REA_ROOT` 指向它们。

```bash
python -m pip install --upgrade twine
twine check dist/*.whl dist/*.tar.gz
twine upload dist/anti_rea-1.0.0*        # 需 TWINE_USERNAME/__token__
```

## 5. npm（可选）

构建集成包含 npm 插件示例；若要发布对应 npm 包（如
`@anti-rea/protect`）：

```bash
npm login
cd integrations/npm && npm publish --access public
```

## 6. 发布后验证（从"外人"视角）

```bash
# 干净目录，模拟外部用户
d=$(mktemp -d) && cd "$d"
tar xzf /path/to/anti-rea-1.0.0-bundle.tar.gz && cd anti-rea-1.0.0
pip install -r requirements.txt
python -m core.cli doctor
make build && bash examples/quickstart/run.sh
```

## 7. 归档与公告

- [ ] 更新 `docs/STATUS.md` 的里程碑为已发布。
- [ ] 在 `CHANGELOG.md` 顶部确认 `[1.0.0]` 条目。
- [ ] 发布公告（可选）：说明用途、范围、限制与入口 `SKILL.md`。

## 未决 / 顺延

- NFR-02（Token 倍数 ≥ 100×）与外部第三方红队验收：需真实 LLM，**S7 执行**。
- 私有凭据（PyPI token、npm token、GPG 私钥）**一律不入库**。
