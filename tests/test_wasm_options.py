"""WASM 反 REA 选项目录的一致性测试。

覆盖：`docs/wasm-anti-rea-options.yaml` 的结构与自洽性、`docs/wasm-anti-rea.md` 存在、
验证方法论、以及 `skill.json` / `SKILL.md` 的接线。与其它语言菜单测试同构。
"""
import json
import os
import unittest

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUIDE = os.path.join(REPO, "docs", "wasm-anti-rea.md")
CATALOG = os.path.join(REPO, "docs", "wasm-anti-rea-options.yaml")
SKILL_JSON = os.path.join(REPO, "skill.json")
SKILL_MD = os.path.join(REPO, "SKILL.md")

EXPECTED_IDS = ["W0", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]
REQUIRED_OPTION_KEYS = {
    "id", "name", "principle", "effect", "effectiveness",
    "pros", "cons", "impacts", "tools", "best_for", "verify",
}


class TestWasmOptionsCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CATALOG, encoding="utf-8") as fh:
            cls.doc = yaml.safe_load(fh)

    def test_guide_and_catalog_exist(self):
        self.assertTrue(os.path.exists(GUIDE))
        self.assertTrue(os.path.exists(CATALOG))

    def test_option_ids_and_order(self):
        ids = [o["id"] for o in self.doc["options"]]
        self.assertEqual(ids, EXPECTED_IDS)

    def test_each_option_is_complete(self):
        for opt in self.doc["options"]:
            missing = REQUIRED_OPTION_KEYS - set(opt)
            self.assertFalse(missing, "%s 缺字段：%s" % (opt.get("id"), sorted(missing)))
            self.assertTrue(opt["principle"].strip(), "%s principle 为空" % opt["id"])
            self.assertTrue(opt["pros"], "%s pros 为空" % opt["id"])
            self.assertTrue(opt["cons"], "%s cons 为空" % opt["id"])
            self.assertTrue(opt["impacts"], "%s impacts 为空" % opt["id"])
            for tool in opt["tools"]:
                self.assertIn("name", tool)
                self.assertIn("source", tool)

    def test_combinations_reference_known_options(self):
        known = {o["id"] for o in self.doc["options"]}
        self.assertTrue(self.doc["combinations"])
        for combo in self.doc["combinations"]:
            self.assertTrue(combo["scenario"])
            self.assertTrue(combo["options"])
            unknown = set(combo["options"]) - known
            self.assertFalse(unknown, "组合引用了未知选项：%s" % sorted(unknown))

    def test_verification_methodology_present(self):
        ver = self.doc["verification"]
        self.assertIn("verify/attack_sim", ver["note"])
        names = {t["name"] for t in ver["tools"]}
        for expected in ("wasm2wat / wasm-objdump", "wasm-decompile", "wasm2c",
                         "wasm-strip", "wasm-tools print"):
            self.assertIn(expected, names)
        self.assertTrue(ver["steps"])
        self.assertTrue(ver["metrics"])

    def test_skill_json_wired(self):
        with open(SKILL_JSON, encoding="utf-8") as fh:
            skill = json.load(fh)
        wasm = skill["wasm_anti_rea"]
        self.assertEqual(wasm["guide"], "docs/wasm-anti-rea.md")
        self.assertEqual(wasm["catalog"], "docs/wasm-anti-rea-options.yaml")
        self.assertEqual([o["id"] for o in wasm["options"]], EXPECTED_IDS)
        self.assertEqual(skill["guides"]["wasm_anti_rea"], "docs/wasm-anti-rea.md")

    def test_skill_md_links_the_guide(self):
        with open(SKILL_MD, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("docs/wasm-anti-rea.md", text)
        self.assertIn("docs/wasm-anti-rea-options.yaml", text)
        self.assertIn("W0", text)


class TestWasmDocClaims(unittest.TestCase):
    """几条容易“说过头”的事实口径，固定为可回归的断言。"""

    @classmethod
    def setUpClass(cls):
        with open(GUIDE, encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_host_can_read_memory(self):
        self.assertIn("不能对宿主保密", self.text)
        self.assertIn("线性内存", self.text)

    def test_name_section_and_strip(self):
        self.assertIn("name", self.text)
        self.assertIn("wasm-strip", self.text)
        self.assertIn("DWARF", self.text)

    def test_wasm32_is_experimental(self):
        self.assertIn("实验性", self.text)
        self.assertIn("端到端", self.text)

    def test_wasm2c_mentioned(self):
        self.assertIn("wasm2c", self.text)

    def test_tools_not_bundled(self):
        self.assertIn("不由本技能分发", self.text)


if __name__ == "__main__":
    unittest.main()
