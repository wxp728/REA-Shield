#!/usr/bin/env python3
"""正式发布打包（S6 / M8）。

产出到 `dist/`：
  - anti_rea-<ver>-py3-none-any.whl   Python wheel（次要件）
  - anti_rea-<ver>.tar.gz             Python sdist（若打包后端可用）
  - anti-rea-<ver>-bundle.tar.gz      全仓自包含包（主产物，离线可用）
  - MANIFEST.sha256                   所有产物的 SHA-256
  - SIGNING.md                        签名说明（密钥不入库，见 OI-05）

用法：
  python tools/release.py               # 构建全部产物到 dist/
  python tools/release.py --check       # 只做一致性/自检（CI 用，不构建）
  python tools/release.py --verify dist # 校验既有 dist/MANIFEST.sha256
  python tools/release.py --skill dist  # 只生成最小技能包（skill-only deploy）

设计：plan §8.2（M8 出口）。主产物为「全仓自包含包」，wheel 为次要件。
最小技能包用于「把技能装到别的项目」（按需获取，见 docs/PROVISIONING.md）。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

# 目录级排除（打包时）
_EXCLUDE_DIRS = {
    ".git", "engine/build", "build", "dist", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", ".eggs", ".tox", "node_modules",
    "tests/.tmp", ".venv", "venv", "pilots/crypto-lib/build",
    "anti_rea.egg-info", "anti-rea.egg-info",
}
_EXCLUDE_SUFFIX = (".pyc", ".pyo", ".so", ".o", ".a", ".dylib", ".dll", ".exe")
_EXCLUDE_SUFFIX_KEEP = ("anti_rea_passes.so",)  # 通常也不打包引擎产物（由用户构建）

# --------------------------------------------------------------------------
# 技能部署集（skill-only deploy，见 docs/PROVISIONING.md §2）
#
# 用途：把本技能装到**别的项目/环境**时，只带运行与接线需要的东西，
#      不带开发/审计/复现材料（tests/、ci/、benchmarks/、pilots/、poc/、
#      设计文档等）——降低部署代价，后续按需再取。
# --------------------------------------------------------------------------
SKILL_FILES = [
    "SKILL.md", "skill.json", "README.md", "README.zh-CN.md", "LICENSE",
    "requirements.txt", "requirements-optional.txt", "pyproject.toml",
    "Makefile", "Dockerfile",
]
SKILL_DIRS = ["core", "schemas", "policies", "integrations", "engine", "tools"]
SKILL_DOC_FILES = [
    "docs/INSTALL.md", "docs/FAQ.md", "docs/troubleshooting.md",
    "docs/build-injection.md", "docs/PROVISIONING.md", "docs/mcp-clients.md",
    "docs/java-anti-rea.md", "docs/java-anti-rea-options.yaml",
]
# 不进技能部署集（开发 / 审计 / 复现用；需要时再从仓库取）
SKILL_EXCLUDE = [
    "tests", "ci", "benchmarks", "pilots", "poc", "examples",
    "docs/design", "docs/release", "docs/analysis", "docs/requirements",
    "docs/STATUS.md", "AGENTS.md",
]


def skill_file_set() -> list[str]:
    """技能部署集的相对文件列表（纯函数，便于自检/测试）。"""
    files: list[str] = []

    def _add(rel: str) -> None:
        p = os.path.join(REPO, rel)
        if os.path.isfile(p):
            files.append(rel.replace("\\", "/"))

    for rel in SKILL_FILES + SKILL_DOC_FILES:
        _add(rel)
    for d in SKILL_DIRS:
        root = os.path.join(REPO, d)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = os.path.relpath(dirpath, REPO).replace("\\", "/")
            if rel_dir in _EXCLUDE_DIRS:
                dirnames[:] = []
                continue
            for fn in filenames:
                rel = ("%s/%s" % (rel_dir, fn)).replace("\\", "/")
                if rel in _EXCLUDE_DIRS or rel.startswith("dist/"):
                    continue
                if fn.endswith(_EXCLUDE_SUFFIX) and fn not in _EXCLUDE_SUFFIX_KEEP:
                    continue
                _add(rel)
    return sorted(set(files))


def skill_bundle(dist: str, ver: str) -> str:
    """最小技能包（skill-only deploy）——不含 tests/ci/poc/pilots/设计文档。"""
    out = os.path.join(dist, "anti-rea-skill-%s.tar.gz" % ver)
    if os.path.exists(out):
        os.remove(out)
    prefix = "anti-rea-skill-%s/" % ver
    files = skill_file_set()
    with tarfile.open(out, "w:gz") as tf:
        for rel in files:
            tf.add(os.path.join(REPO, rel), arcname=prefix + rel)
    listing = os.path.join(dist, "SKILL-FILES.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        fh.write("# 最小技能集文件清单（%d 个）\n" % len(files))
        fh.write("# 未包含（开发/审计/复现用，见 docs/PROVISIONING.md §2）：\n")
        for d in SKILL_EXCLUDE:
            fh.write("#   - %s\n" % d)
        fh.write("\n".join(files) + "\n")
    return out


def _version() -> str:
    from core import __version__
    return __version__


# --------------------------------------------------------------------------
# 一致性自检
# --------------------------------------------------------------------------

def _pyproject_version() -> str:
    try:
        import tomllib
    except ModuleNotFoundError:  # py<3.11 兜底
        return ""
    with open(os.path.join(REPO, "pyproject.toml"), "rb") as fh:
        return tomllib.load(fh).get("project", {}).get("version", "")


def check() -> list[str]:
    """返回问题列表（空 = 通过）。"""
    problems: list[str] = []
    ver = _version()
    if ver != _pyproject_version():
        problems.append("版本不一致：core.__version__=%s, pyproject=%s"
                        % (ver, _pyproject_version()))

    # 关键文件存在
    required = [
        "SKILL.md", "skill.json", "README.md", "README.zh-CN.md", "LICENSE",
        "requirements.txt", "requirements-optional.txt", "pyproject.toml",
        "Dockerfile",
        ".agents/skills/anti-rea/SKILL.md",
        "docs/INSTALL.md", "docs/mcp-clients.md", "docs/PROVISIONING.md",
        "docs/java-anti-rea.md", "docs/java-anti-rea-options.yaml",
        "engine/CMakeLists.txt", "core/common.py", "core/toolchain.py",
    ]
    for rel in required:
        if not os.path.exists(os.path.join(REPO, rel)):
            problems.append("缺少文件：%s" % rel)

    # skill.json 合法 + 版本一致
    try:
        with open(os.path.join(REPO, "skill.json"), encoding="utf-8") as fh:
            skill = json.load(fh)
        if skill.get("version") != ver:
            problems.append("skill.json 版本 %s != %s" % (skill.get("version"), ver))
        if not skill.get("tools"):
            problems.append("skill.json 未声明 tools")
    except Exception as exc:  # noqa: BLE001
        problems.append("skill.json 解析失败：%s" % exc)

    # 关键包可导入
    for mod in ("core", "core.cli", "core.toolchain", "core.verify",
                "core.mcp.server", "core.adaptive"):
        try:
            __import__(mod)
        except Exception as exc:  # noqa: BLE001
            problems.append("导入失败 %s: %s" % (mod, exc))

    # schemas / policies 存在
    for d in ("schemas", "policies"):
        p = os.path.join(REPO, d)
        if not os.path.isdir(p) or not os.listdir(p):
            problems.append("目录为空或缺失：%s/" % d)
    return problems


# --------------------------------------------------------------------------
# 打包
# --------------------------------------------------------------------------

def _git_clean() -> bool:
    git = shutil.which("git")
    if not git:
        return False
    r = subprocess.run([git, "status", "--porcelain"], cwd=REPO,
                       capture_output=True, text=True)
    return r.returncode == 0 and not r.stdout.strip()


def bundle_tarball(dist: str, ver: str) -> str:
    """全仓自包含 tarball（主产物）。

    工作区干净时用 `git archive HEAD`（只含已跟踪文件，等价发布状态）；
    有未提交改动时回退为遍历打包，确保当前状态可用。
    """
    out = os.path.join(dist, "anti-rea-%s-bundle.tar.gz" % ver)
    if os.path.exists(out):
        os.remove(out)
    prefix = "anti-rea-%s/" % ver

    git = shutil.which("git")
    if git and _git_clean():
        r = subprocess.run([git, "archive", "--format=tar.gz",
                            "--prefix=%s" % prefix, "-o", out, "HEAD"],
                           cwd=REPO, capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(out):
            return out
        # 回退到 tar（含未提交改动）
    with tarfile.open(out, "w:gz") as tf:
        for dirpath, dirnames, filenames in os.walk(REPO):
            rel_dir = os.path.relpath(dirpath, REPO)
            if rel_dir == ".":
                rel_dir = ""
            dirnames[:] = [d for d in dirnames
                           if os.path.join(rel_dir, d).replace("\\", "/")
                           not in _EXCLUDE_DIRS]
            for fn in filenames:
                rel = os.path.join(rel_dir, fn).replace("\\", "/")
                if rel in _EXCLUDE_DIRS:
                    continue
                if fn.endswith(_EXCLUDE_SUFFIX) and fn not in _EXCLUDE_SUFFIX_KEEP:
                    continue
                tf.add(os.path.join(dirpath, fn), arcname=prefix + rel)
    return out


def build_wheel(dist: str) -> list[str]:
    """构建 wheel（不允许构建隔离，避免联网拉构建依赖）。"""
    py = sys.executable
    if importlib.util.find_spec("wheel") is None:
        print("  [warn] 未安装 `wheel` 包，跳过 wheel 构建（主产物 bundle 不受影响）。\n"
              "         如需 wheel：pip install wheel && python tools/release.py",
              file=sys.stderr)
        return []
    cmd = [py, "-m", "pip", "wheel", ".", "--no-build-isolation",
           "--no-deps", "-w", dist]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        tail = "\n".join((r.stderr or r.stdout).strip().splitlines()[-5:])
        print("  [warn] wheel 构建失败（跳过）：\n%s" % tail, file=sys.stderr)
        return []
    return [os.path.join(dist, f) for f in os.listdir(dist) if f.endswith(".whl")]


def build_sdist(dist: str) -> list[str]:
    """尝试构建 sdist；后端不可用则跳过（主产物已自包含）。"""
    import contextlib
    import io
    before = set(os.listdir(dist))
    buf = io.StringIO()
    # 优先 python -m build --sdist --no-isolation
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            r = subprocess.run([sys.executable, "-m", "build", "--sdist",
                                "--no-isolation", "--outdir", dist],
                               cwd=REPO, capture_output=True, text=True)
        if r.returncode == 0:
            return [os.path.join(dist, f) for f in os.listdir(dist)
                    if f.endswith(".tar.gz") and f not in before and "bundle" not in f]
    except Exception:  # noqa: BLE001
        pass
    # 兜底：直接调 setuptools 后端
    try:
        from setuptools import build_meta  # noqa: F401
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            name = build_meta.build_sdist(dist)
        return [os.path.join(dist, name)]
    except Exception as exc:  # noqa: BLE001
        print("  [warn] sdist 构建跳过（后端不可用：%s）" % exc, file=sys.stderr)
        return []


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(dist: str, products: list[str]) -> str:
    lines = []
    for p in sorted(set(os.path.abspath(p) for p in products)):
        if os.path.exists(p):
            lines.append("%s  %s" % (_sha256(p), os.path.basename(p)))
    out = os.path.join(dist, "MANIFEST.sha256")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return out


def write_signing_doc(dist: str, ver: str) -> str:
    out = os.path.join(dist, "SIGNING.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(_SIGNING_TMPL.format(ver=ver))
    return out


_SIGNING_TMPL = """# 发布签名与校验（REA-Shield v{ver}）

## 校验完整性

```bash
cd dist
sha256sum -c MANIFEST.sha256
```

## 签名（维护者操作，密钥**不入库**，见 OI-05）

发布产物应使用维护者私钥离线签名，公钥随发行页公布：

```bash
# 生成密钥（仅首次，密钥保存在仓库之外）
gpg --full-generate-key

# 对每个产物生成分离签名
for f in anti-rea-{ver}-bundle.tar.gz anti_rea-{ver}-py3-none-any.whl; do
  gpg --armor --detach-sign "$f"
done

# 校验
gpg --verify anti-rea-{ver}-bundle.tar.gz.asc anti-rea-{ver}-bundle.tar.gz
```

## 说明

- 本仓库**不包含**任何签名私钥；`dist/SIGNING.md` 仅描述流程。
- 主产物为 `anti-rea-{ver}-bundle.tar.gz`（全仓自包含，离线可构建）；
  wheel 为次要件（schemas/policies 依 REPO_ROOT 解析，可能需要 `ANTI_REA_ROOT`）。
- 校验哈希以 `MANIFEST.sha256` 为准。
"""


def verify(dist: str) -> int:
    manifest = os.path.join(dist, "MANIFEST.sha256")
    if not os.path.exists(manifest):
        print("E_VERIFY: 未找到 %s" % manifest, file=sys.stderr)
        return 1
    bad = 0
    with open(manifest, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            digest, name = re.split(r"\s+", line, 1)
            p = os.path.join(dist, name.strip())
            if not os.path.exists(p):
                print("MISSING %s" % name)
                bad += 1
            elif _sha256(p) != digest:
                print("MISMATCH %s" % name)
                bad += 1
            else:
                print("OK      %s" % name)
    if bad:
        print("校验失败：%d 项不一致" % bad, file=sys.stderr)
        return 1
    print("校验通过 ✅")
    return 0


def build(dist: str) -> int:
    ver = _version()
    os.makedirs(dist, exist_ok=True)
    print("REA-Shield 发布打包 v%s -> %s" % (ver, dist))
    products: list[str] = []
    products += build_wheel(dist)
    products += build_sdist(dist)
    products.append(bundle_tarball(dist, ver))
    products = [p for p in products if p and os.path.exists(p) and not p.endswith("MANIFEST.sha256")]
    write_manifest(dist, products)
    write_signing_doc(dist, ver)
    print("产物：")
    for p in sorted(products):
        print("  %-48s %8d B" % (os.path.basename(p), os.path.getsize(p)))
    print("  MANIFEST.sha256")
    print("  SIGNING.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="release.py", description="REA-Shield 发布打包")
    ap.add_argument("--out", default=os.path.join(REPO, "dist"), help="输出目录")
    ap.add_argument("--check", action="store_true", help="只做一致性自检")
    ap.add_argument("--verify", metavar="DIST", default=None, help="校验既有 dist/MANIFEST.sha256")
    ap.add_argument("--skill", metavar="DIST", default=None,
                    help="生成最小技能包（skill-only deploy，见 docs/PROVISIONING.md）")
    args = ap.parse_args(argv)

    if args.verify:
        return verify(args.verify)
    if args.check:
        problems = check()
        if problems:
            print("发布自检失败：", file=sys.stderr)
            for p in problems:
                print("  - %s" % p, file=sys.stderr)
            return 1
        print("发布自检通过（版本 %s，关键文件/包/skill.json 均 OK）" % _version())
        return 0
    if args.skill:
        os.makedirs(args.skill, exist_ok=True)
        out = skill_bundle(args.skill, _version())
        print("最小技能包：%s (%d B, %d 个文件)"
              % (out, os.path.getsize(out), len(skill_file_set())))
        print("文件清单：%s" % os.path.join(args.skill, "SKILL-FILES.txt"))
        return 0
    problems = check()
    if problems:
        print("发布前自检有问题：", file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        return 1
    return build(args.out)


if __name__ == "__main__":
    raise SystemExit(main())
