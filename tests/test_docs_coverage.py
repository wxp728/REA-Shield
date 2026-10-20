"""跨文档覆盖：语言/产物菜单必须在主要入口与运维文档中可见。

新增菜单时最容易漏掉的不是菜单本身，而是 FAQ / 安装 / 按需获取 / 排障 / README
这些"入口文档"。本测试把这些交叉引用固定下来，避免能力只存在于单篇指南里。
"""
import json
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 语言/产物 -> (菜单前缀, 指南, 机器可读清单)
MENUS = {
    "java": ("J", "docs/java-anti-rea.md", "docs/java-anti-rea-options.yaml"),
    "dotnet": ("D", "docs/dotnet-anti-rea.md", "docs/dotnet-anti-rea-options.yaml"),
    "js": ("JS", "docs/js-anti-rea.md", "docs/js-anti-rea-options.yaml"),
    "go": ("G", "docs/go-anti-rea.md", "docs/go-anti-rea-options.yaml"),
    "python": ("PY", "docs/python-anti-rea.md", "docs/python-anti-rea-options.yaml"),
    "dart": ("DA", "docs/dart-anti-rea.md", "docs/dart-anti-rea-options.yaml"),
    "wasm": ("W", "docs/wasm-anti-rea.md", "docs/wasm-anti-rea-options.yaml"),
}

ENTRY_DOCS = [
    "SKILL.md",
    "README.md",
    "README.zh-CN.md",
    "docs/FAQ.md",
    "docs/INSTALL.md",
    "docs/PROVISIONING.md",
    "docs/troubleshooting.md",
]


def _read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


class TestMenuDocsCoverage(unittest.TestCase):
    def test_every_menu_has_guide_and_catalog(self):
        for name, (_, guide, catalog) in MENUS.items():
            self.assertTrue(os.path.exists(os.path.join(REPO, guide)), name)
            self.assertTrue(os.path.exists(os.path.join(REPO, catalog)), name)

    def test_menu_guides_are_linked_from_entry_docs(self):
        for rel in ENTRY_DOCS:
            text = _read(rel)
            # FAQ 等与指南同目录的文档使用相对文件名，README/SKILL 使用 docs/ 前缀；
            # 只要文件名出现即可，具体前缀由各文档的上下文决定。
            missing = [guide for _, guide, _ in MENUS.values()
                       if guide.rsplit("/", 1)[-1] not in text]
            self.assertFalse(missing, "%s 未链接：%s" % (rel, missing))

    def test_menu_ids_are_visible_in_skill_entry(self):
        text = _read("SKILL.md")
        for name, (prefix, _, _) in MENUS.items():
            self.assertIn("%s0" % prefix, text, "SKILL.md 未出现 %s 菜单" % name)
            self.assertIn("%s8" % prefix, text, "SKILL.md 未出现 %s 菜单上界" % name)

    def test_skill_json_wires_all_menus(self):
        with open(os.path.join(REPO, "skill.json"), encoding="utf-8") as fh:
            skill = json.load(fh)
        for name, (_, guide, catalog) in MENUS.items():
            block = skill.get("%s_anti_rea" % name)
            self.assertIsNotNone(block, "skill.json 缺 %s_anti_rea" % name)
            if name == "wasm":
                # WASM 的 wasm32 IR 路径是实验性，不能写成"已验证的 IR 变换"。
                self.assertIn("experimental", block["ir_transforms"])
            else:
                self.assertFalse(block["ir_transforms"], name)
            self.assertEqual(block["guide"], guide)
            self.assertEqual(block["catalog"], catalog)
            self.assertEqual(skill["guides"]["%s_anti_rea" % name], guide)
            self.assertEqual(len(block["options"]), 9, name)

    def test_scanner_languages_include_go_and_dart(self):
        with open(os.path.join(REPO, "skill.json"), encoding="utf-8") as fh:
            supported = json.load(fh)["supported"]["languages"]
        self.assertIn("go", supported["scan_only"])
        self.assertIn("dart", supported["scan_only"])


if __name__ == "__main__":
    unittest.main()
