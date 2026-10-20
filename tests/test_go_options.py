"""Go 反 REA 选项目录的一致性测试。

覆盖：`docs/go-anti-rea-options.yaml`（机器可读清单）的结构与自洽性、
`docs/go-anti-rea.md`（人读指南）存在、验证方法论、以及 `skill.json` / `SKILL.md` 的接线。
与 `test_java_options.py` / `test_dotnet_options.py` / `test_js_options.py` 同构。
"""
import json
import os
import unittest

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUIDE = os.path.join(REPO, "docs", "go-anti-rea.md")
CATALOG = os.path.join(REPO, "docs", "go-anti-rea-options.yaml")
SKILL_JSON = os.path.join(REPO, "skill.json")
SKILL_MD = os.path.join(REPO, "SKILL.md")

EXPECTED_IDS = ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]
REQUIRED_OPTION_KEYS = {
    "id", "name", "principle", "effect", "effectiveness",
    "pros", "cons", "impacts", "tools", "best_for", "verify",
}


class TestGoOptionsCatalog(unittest.TestCase):
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
        for expected in ("go tool nm / go tool objdump", "go version -m", "GoReSym",
                         "redress", "Ghidra"):
            self.assertIn(expected, names)
        self.assertTrue(ver["steps"])
        self.assertTrue(ver["metrics"])

    def test_skill_json_wired(self):
        with open(SKILL_JSON, encoding="utf-8") as fh:
            skill = json.load(fh)
        go = skill["go_anti_rea"]
        self.assertFalse(go["ir_transforms"])
        self.assertEqual(go["guide"], "docs/go-anti-rea.md")
        self.assertEqual(go["catalog"], "docs/go-anti-rea-options.yaml")
        self.assertEqual([o["id"] for o in go["options"]], EXPECTED_IDS)
        self.assertEqual(skill["guides"]["go_anti_rea"], "docs/go-anti-rea.md")

    def test_skill_md_links_the_guide(self):
        with open(SKILL_MD, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("docs/go-anti-rea.md", text)
        self.assertIn("docs/go-anti-rea-options.yaml", text)
        self.assertIn("G0", text)


class TestGoDocClaims(unittest.TestCase):
    """几条容易"说过头"的事实口径，固定为可回归的断言。"""

    @classmethod
    def setUpClass(cls):
        with open(GUIDE, encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_strip_is_not_protection(self):
        self.assertIn("-s -w", self.text)
        self.assertIn("pclntab", self.text)
        self.assertIn("GoReSym", self.text)

    def test_mentions_garble_and_cgo(self):
        self.assertIn("garble", self.text)
        self.assertIn("cgo", self.text)

    def test_tools_not_bundled(self):
        self.assertIn("不由本技能分发", self.text)


if __name__ == "__main__":
    unittest.main()
