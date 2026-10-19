"""Java / Android 反 REA 选项目录的一致性测试。

覆盖：`docs/java-anti-rea-options.yaml`（机器可读清单）的结构与自洽性、
`docs/java-anti-rea.md`（人读指南）存在、以及 `skill.json` / `SKILL.md` 的接线。
保证"选项菜单"不会随文档演进悄悄破损（例如漏写字段、组合引用不存在的选项）。
"""
import json
import os
import unittest

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUIDE = os.path.join(REPO, "docs", "java-anti-rea.md")
CATALOG = os.path.join(REPO, "docs", "java-anti-rea-options.yaml")
SKILL_JSON = os.path.join(REPO, "skill.json")
SKILL_MD = os.path.join(REPO, "SKILL.md")

EXPECTED_IDS = ["J0", "J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8"]
REQUIRED_OPTION_KEYS = {
    "id", "name", "principle", "effect", "effectiveness",
    "pros", "cons", "impacts", "tools", "best_for", "verify",
}


class TestJavaOptionsCatalog(unittest.TestCase):
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
            # 商业工具/自研也要说明获取途径或明确 n/a
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
        for expected in ("jadx", "CFR", "Vineflower", "javap", "apktool"):
            self.assertIn(expected, names)
        self.assertTrue(ver["steps"])

    def test_skill_json_wired(self):
        with open(SKILL_JSON, encoding="utf-8") as fh:
            skill = json.load(fh)
        java = skill["java_anti_rea"]
        self.assertFalse(java["ir_transforms"])
        self.assertEqual(java["guide"], "docs/java-anti-rea.md")
        self.assertEqual(java["catalog"], "docs/java-anti-rea-options.yaml")
        self.assertEqual([o["id"] for o in java["options"]], EXPECTED_IDS)
        self.assertEqual(skill["guides"]["java_anti_rea"], "docs/java-anti-rea.md")

    def test_skill_md_links_the_guide(self):
        with open(SKILL_MD, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("docs/java-anti-rea.md", text)
        self.assertIn("docs/java-anti-rea-options.yaml", text)
        self.assertIn("Java / Android", text)


if __name__ == "__main__":
    unittest.main()
