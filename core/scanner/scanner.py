"""REA-Shield 输入分析层（Scanner v0.1，R1 MVP）。

设计：docs/design/ddd/dd-01-scanner.md
覆盖：FR-A1（工程类型）、FR-A2（敏感资产三类）、FR-A3（分级）、
      FR-A5（Schema 校验）、FR-A6（拒绝执行）；FR-A4/A7 留待后续迭代。
"""
from __future__ import annotations

import math
import os
import re
import hashlib
from typing import Any

from .. import common
from .. import platform_info

# 语言/构建/平台识别信号
_EXT_LANG = {
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hh": "cpp", ".rs": "rust", ".py": "python",
    ".js": "javascript", ".ts": "typescript", ".java": "java", ".cs": "dotnet",
    ".fs": "dotnet", ".vb": "dotnet",
}
_BUILD_MARKERS = [
    ("CMakeLists.txt", "cmake"), ("Cargo.toml", "cargo"),
    ("build.gradle", "gradle"), ("pom.xml", "maven"),
    ("package.json", "npm"), ("pyproject.toml", "pip"), ("setup.py", "pip"),
    ("Makefile", "make"),
]
_DEFAULT_EXCLUDE = {"test", "tests", "examples", "vendor", "node_modules",
                    "build", ".git", "dist", "target"}

# 敏感资产识别规则（类型 -> 名称正则）
_NAME_RULES = [
    ("license_check", re.compile(r"(license|licence|activate|activation|verify_signature|check_license)", re.I)),
    ("crypto", re.compile(r"(aes|des|rsa|sha\d*|md5|hmac|encrypt|decrypt|cipher|sbox|keystream)", re.I)),
    ("secret", re.compile(r"(secret|passwd|password|credential|api_?key|token|master_?key)", re.I)),
    ("algorithm", re.compile(r"(algorithm|hash|digest|checksum|derive)", re.I)),
]
_SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
# 简易 C/C++ 函数定义：返回类型 [可换行] 函数名(参数) {；容许 extern "C" 前缀（C++ 导出）。
# 同时兼容两种主流书写风格（类型段用 \s 从而可跨越换行）：
#   1) 同行风格：   int foo(int a) { ... }
#   2) Allman/PG：  int\n foo(int a)\n { ... }  （返回类型、函数名、花括号各占一行，
#                   PostgreSQL 内核等大型 C 工程的默认风格）
_FUNC_RE = re.compile(
    r"^(?:extern\s*\"C\"\s*)?[A-Za-z_][\w\s\*]*?\b([A-Za-z_]\w*)\s*\([^;{]*\)\s*\{", re.M)

_TYPE_WEIGHT = {
    "secret": 1.00, "crypto": 0.95, "license_check": 0.90, "algorithm": 0.80,
    "business_logic": 0.50, "protocol": 0.60, "ui": 0.20, "util": 0.15,
    "open_source": 0.00, "unknown": 0.10,
}
_STRATEGY_BY_TYPE = {
    "secret": ["string_encryption", "white_box_crypto"],
    "crypto": ["white_box_crypto", "control_flow_flattening"],
    "license_check": ["control_flow_flattening", "mixed_boolean_arithmetic"],
    "algorithm": ["mixed_boolean_arithmetic", "opaque_predicates"],
}


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _detect_project(root: str, options: dict | None = None) -> dict:
    options = options or {}
    lang_votes: dict[str, float] = {}
    build = "unknown"
    total_ext = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _DEFAULT_EXCLUDE]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in _EXT_LANG:
                total_ext += 1
                lang_votes[_EXT_LANG[ext]] = lang_votes.get(_EXT_LANG[ext], 0.0) + 1.0
        for marker, bs in _BUILD_MARKERS:
            if marker in filenames and build == "unknown":
                build = bs
        if build == "unknown" and any(
                fn.endswith((".csproj", ".sln", ".fsproj", ".vbproj"))
                for fn in filenames):
            build = "msbuild"
    if total_ext == 0:
        language = "unknown"
    else:
        ranked = sorted(lang_votes.items(), key=lambda kv: kv[1], reverse=True)
        top = ranked[0]
        if len(ranked) > 1 and (top[1] - ranked[1][1]) / total_ext < 0.15:
            language = "mixed"
        else:
            language = top[0]
    # 目标平台：显式指定 > 主机探测（dd-01 §目标平台 优先级的前两项）
    target = platform_info.normalize(options.get("target_platform")) \
        or platform_info.host_platform()
    return {"root": root, "language": language, "build_system": build,
            "target_platform": target}


def _function_body(text: str, brace_pos: int) -> str:
    """从 '{' 位置起做朴素花括号匹配，返回函数体文本（含花括号）。"""
    if brace_pos < 0 or brace_pos >= len(text) or text[brace_pos] != "{":
        return ""
    depth = 0
    for i in range(brace_pos, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[brace_pos:i + 1]
    return text[brace_pos:]


_HEX_BYTES_RE = re.compile(r"(?:0x[0-9A-Fa-f]{2}\s*,?\s*){4,}")


def _looks_like_key_material(body: str) -> bool:
    """轻量数据流信号（FR-A4 部分）：函数体内含硬编码密钥字节数组或高熵密钥串。"""
    if _HEX_BYTES_RE.search(body):
        return True
    for sm in re.finditer(r'"([^"\\]{8,})"', body):
        val = sm.group(1)
        if _shannon_entropy(val) >= 3.5 and re.search(
                r"(key|secret|token|password)", val, re.I):
            return True
    return False


def all_function_names(path: str) -> list[str]:
    """返回文件内**所有函数定义**的名字（不做名称规则过滤）。

    用于「整文件保护」：白名单按文件全量取名，覆盖 `sm4_key_expand` 这类名字
    不含 crypto 关键词的内部辅助函数（见 经验记录 gap#7）。非函数误报无副作用
    ——引擎按真实 IR 函数名匹配，多余的条目被忽略。
    """
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return []
    return [m.group(1) for m in _FUNC_RE.finditer(text)]


def _scan_file(path: str) -> list[dict]:
    """返回该文件的候选资产（未分级）。"""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return []
    out: list[dict] = []

    # 函数级
    for m in _FUNC_RE.finditer(text):
        name = m.group(1)
        line = text.count("\n", 0, m.start()) + 1
        for typ, rx in _NAME_RULES:
            if rx.search(name):
                ev = [f"fn.name:{rx.pattern}"]
                body = _function_body(text, m.end() - 1)
                if _looks_like_key_material(body):
                    ev.append("dataflow.key_material")
                out.append({"path": path, "symbol": name, "line": line,
                            "type": typ, "evidence": ev})
                break

    # 字符串类（密钥/Token 模式）
    for rx in _SECRET_PATTERNS:
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            out.append({"path": path, "line": line, "type": "secret",
                        "evidence": [f"str.pattern:{rx.pattern}"]})

    # 数据流类（简易：高熵字符串常量 + 关键词）
    for m in re.finditer(r'"([^"\\]{16,})"', text):
        val = m.group(1)
        if _shannon_entropy(val) >= 4.0 and re.search(
                r"(key|token|secret|password)", val, re.I):
            line = text.count("\n", 0, m.start()) + 1
            out.append({"path": path, "line": line, "type": "secret",
                        "evidence": ["str.entropy+keyword"]})
    return out


def _score(asset: dict) -> tuple[int, str]:
    t = _TYPE_WEIGHT.get(asset["type"], 0.1)
    c = 0.9 if asset.get("evidence") else 0.5
    e = 1.0 if asset["type"] == "secret" else 0.6
    d = 0.5 if any(("entropy" in x) or ("key_material" in x)
                   for x in asset.get("evidence", [])) else 0.0
    score = 100 * (0.35 * t + 0.25 * c + 0.20 * e + 0.20 * d)
    if asset["type"] == "open_source":
        return int(score), "P3"
    if score >= 80:
        return int(score), "P0"
    if score >= 60:
        return int(score), "P1"
    if score >= 40:
        return int(score), "P2"
    return int(score), "P3"


def _ownership_ok(root: str, allow_unknown: bool) -> bool:
    if allow_unknown:
        return True
    d = os.path.abspath(root)
    while True:
        if os.path.isdir(os.path.join(d, ".git")):
            return True
        if os.path.isfile(os.path.join(d, "LICENSE")) or \
           os.path.isfile(os.path.join(d, "LICENSE.txt")):
            return True
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent


def scan(root: str, options: dict | None = None) -> dict:
    """扫描工程，产出符合 asset_manifest schema 的清单（dict）。"""
    options = options or {}
    if not os.path.isdir(root):
        raise ValueError("E_INVALID_INPUT: root 不是目录: %s" % root)

    allow_unknown = bool(options.get("allow_unknown_owner", False))
    if not _ownership_ok(root, allow_unknown):
        raise PermissionError("E_REFUSED: 所有权不明，拒绝执行（可用 --allow-unknown-owner 覆盖）")

    project = _detect_project(root, options)
    include = set(options.get("include", []) or [])
    exclude = set(options.get("exclude", []) or [])

    candidates: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _DEFAULT_EXCLUDE]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in _LANG_EXT_SOURCES:
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            if include and not any(rel.startswith(i) for i in include):
                continue
            if exclude and any(rel.startswith(e) for e in exclude):
                continue
            candidates.extend(_scan_file(p))

    # 去重 + 分级
    seen = set()
    assets: list[dict] = []
    for cand in candidates:
        key = (cand["path"], cand.get("symbol"), cand.get("line"), cand["type"])
        if key in seen:
            continue
        seen.add(key)
        score, sens = _score(cand)
        rel = os.path.relpath(cand["path"], root)
        aid = "a-" + hashlib.sha1(
            f"{rel}#{cand.get('symbol','')}:{cand.get('line','')}:{cand['type']}".encode()
        ).hexdigest()[:8]
        asset = {
            "id": aid,
            "path": rel,
            "type": cand["type"],
            "sensitivity": sens,
            "skip_transform": cand["type"] == "open_source",
            "source": "auto",
            "evidence": cand.get("evidence", []) + [f"score:{score}"],
        }
        if cand.get("symbol"):
            asset["symbol"] = cand["symbol"]
        if cand.get("line"):
            asset["line"] = cand["line"]
        hint = _STRATEGY_BY_TYPE.get(cand["type"])
        if hint:
            asset["protection_hint"] = hint
        assets.append(asset)

    by_sens = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for a in assets:
        by_sens[a["sensitivity"]] += 1

    manifest = {
        "schema_version": common.SCHEMA_VERSION,
        "generated_at": common.now_iso(),
        "run_id": options.get("run_id") or common.new_run_id(),
        "project": project,
        "assets": assets,
        "summary": {
            "total": len(assets),
            "by_sensitivity": by_sens,
            "open_source_count": sum(1 for a in assets if a["type"] == "open_source"),
            "refused": False,
        },
    }
    common.validate(manifest, "asset_manifest.schema.json")
    return manifest


_LANG_EXT_SOURCES = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh",
                     ".rs", ".py", ".js", ".ts", ".java", ".cs"}
