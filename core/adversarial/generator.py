"""对抗性诱导生成器（Adversarial Generator v0.1，FR-C9）。

设计：docs/design/ddd/dd-05-adversarial.md
R2 v0.1 采用**单轮算子应用**（未启用 GA 迭代，GA 需 DD-07 指标反馈，属 R3）：

- `decoy_functions`：植入「结构相近、语义相异」的诱饵函数（不可达、保留到二进制）；
- `context_semantic_aug`：植入误导性命名/注释/字符串，干扰语义判断；
- `constant_externalize`：将诱饵常量经不透明来源表达，弱化常量指纹。

约束：所有算子必须**功能保持**（NFR-03），不引入外部依赖（CQ-01）。
"""
from __future__ import annotations

import os
import random


def _decoy_fn(name: str, seed: int) -> str:
    r = random.Random(seed)
    a = r.randrange(3, 0x3F)
    b = r.randrange(3, 0x7F)
    c = r.randrange(1, 0x1F)
    return (
        "/* 诱饵：结构相近、语义相异（不可达，保留） */\n"
        "__attribute__((noinline, used)) int %s(int x)\n"
        "{\n"
        "    int y = (x * 0x%02x) + 0x%02x;\n"
        "    y ^= (y >> %d);\n"
        "    return y - 0x%02x;\n"
        "}\n" % (name, a, b, c, r.randrange(1, 0xFF))
    )


def _augment_comment(seed: int) -> str:
    r = random.Random(seed ^ 0x1234)
    tags = ["verify_license", "check_credentials", "decrypt_payload",
            "validate_token", "derive_master_key", "license_gate"]
    picks = r.sample(tags, 3)
    return (
        "/* --- 上下文语义增强（误导性命名/字符串，仅注释与死串）---\n"
        " * TODO(security): refactor %s -> %s before release\n"
        " * NOTE: hardware binding via %s (未启用)\n"
        " */\n" % (picks[0], picks[1], picks[2])
    )


def build_variant(src_text: str, symbols: list[str], index: int, seed: int) -> str:
    """在源码尾部注入单轮诱导算子，返回变体源码（功能保持）。"""
    rnd = random.Random(seed ^ (index * 0x9E3779B1))
    names = symbols or ["compute"]
    decoys = []
    for j in range(3):
        base = names[rnd.randrange(len(names))] if names else "compute"
        decoys.append(_decoy_fn("%s_induce%d" % (base, j), seed + index * 7 + j))

    tail = (
        "\n/* ==== Anti-REA 对抗性诱导变体 #%d ==== */\n" % index
        + _augment_comment(seed + index)
        + "".join(decoys)
        + "/* 不透明诱饵常量（不可达引用，避免被优化剔除） */\n"
        "__attribute__((used)) static const char *g_induce_%d = "
        "\"AKIA%08X00000000\";\n" % (index, rnd.randrange(1 << 32))
    )
    return src_text + "\n" + tail


def generate_variants(src_path: str, out_dir: str, symbols: list[str] | None = None,
                      count: int = 3, seed: int = 0) -> dict:
    """生成 count 个功能保持的诱导变体源码，返回清单。"""
    if count < 1:
        raise ValueError("E_INVALID_INPUT: count 须 >= 1")
    if count > 64:
        raise ValueError("E_INVALID_INPUT: count 超过 Schema 上限 64（OI-05）")
    os.makedirs(out_dir, exist_ok=True)
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    symbols = symbols or []
    stem, ext = os.path.splitext(os.path.basename(src_path))
    ext = ext or ".c"          # 保留源语言扩展名（.cpp 需按 C++ 编译）
    variants = []
    for i in range(count):
        text = build_variant(src, symbols, i, seed)
        vp = os.path.join(out_dir, "%s.induce%d%s" % (stem, i, ext))
        with open(vp, "w", encoding="utf-8") as fh:
            fh.write(text)
        variants.append({"index": i, "path": vp, "operators":
                         ["decoy_functions", "context_semantic_aug",
                          "constant_externalize"]})
    return {"source": src_path, "count": count, "seed": seed, "variants": variants}
