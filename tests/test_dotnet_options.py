""".NET / Unity 反 REA 选项目录的一致性测试。

覆盖：`docs/dotnet-anti-rea-options.yaml`（机器可读清单）的结构与自洽性、
`docs/dotnet-anti-rea.md`（人读指南）存在、Unity/IL2CPP 特别路径、以及
`skill.json` / `SKILL.md` 的接线。与 `test_java_options.py` 同构，防止
"选项菜单"随文档演进悄悄破损。
"""
import json
import os
import unittest

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUIDE = os.path.join(REPO, "docs", "dotnet-anti-rea.md")
CATALOG = os.path.join(REPO, "docs", "dotnet-anti-rea-options.yaml")
SKILL_JSON = os.path.join(REPO, "skill.json")
SKILL_MD = os.path.join(REPO, "SKILL.md")

EXPECTED_IDS = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]
REQUIRED_OPTION_KEYS = {
    "id", "name", "principle", "effect", "effectiveness",
    "pros", "cons", "impacts", "tools", "best_for", "verify",
}


class TestDotnetOptionsCatalog(unittest.TestCase):
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

    def test_unity_path_present(self):
        unity = self.doc["unity"]
        for form in ("mono", "il2cpp", "webgl"):
            self.assertIn(form, unity)
            self.assertTrue(unity[form]["attack_surface"])
            self.assertTrue(unity[form]["recommendation"])
        known = {o["id"] for o in self.doc["options"]}
        for form in ("mono", "webgl"):
            self.assertFalse(set(unity[form]["recommendation"]) - known,
                             "%s 推荐了未知选项" % form)
        self.assertIn("Il2CppDumper", unity["il2cpp"]["attack_surface"] + unity["il2cpp"]["notes"])

    def test_verification_methodology_present(self):
        ver = self.doc["verification"]
        self.assertIn("verify/attack_sim", ver["note"])
        names = {t["name"] for t in ver["tools"]}
        for expected in ("ILSpy / ilspycmd", "dnSpyEx", "dotPeek", "de4dot",
                         "ildasm / monodis", "Il2CppDumper"):
            self.assertIn(expected, names)
        self.assertTrue(ver["steps"])
        self.assertTrue(ver["metrics"])

    def test_skill_json_wired(self):
        with open(SKILL_JSON, encoding="utf-8") as fh:
            skill = json.load(fh)
        dotnet = skill["dotnet_anti_rea"]
        self.assertFalse(dotnet["ir_transforms"])
        self.assertEqual(dotnet["guide"], "docs/dotnet-anti-rea.md")
        self.assertEqual(dotnet["catalog"], "docs/dotnet-anti-rea-options.yaml")
        self.assertEqual([o["id"] for o in dotnet["options"]], EXPECTED_IDS)
        self.assertEqual(skill["guides"]["dotnet_anti_rea"], "docs/dotnet-anti-rea.md")

    def test_skill_md_links_the_guide(self):
        with open(SKILL_MD, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("docs/dotnet-anti-rea.md", text)
        self.assertIn("docs/dotnet-anti-rea-options.yaml", text)
        self.assertIn(".NET", text)


class TestDotnetDocClaims(unittest.TestCase):
    """几条容易"说过头"的事实口径，固定为可回归的断言。"""

    @classmethod
    def setUpClass(cls):
        with open(GUIDE, encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_ready_to_run_is_not_protection(self):
        self.assertIn("ReadyToRun", self.text)
        self.assertIn("不算防护", self.text)

    def test_mentions_de4dot_risk(self):
        self.assertIn("de4dot", self.text)

    def test_mentions_nativeaot_and_il2cpp(self):
        self.assertIn("NativeAOT", self.text)
        self.assertIn("IL2CPP", self.text)

    def test_tools_not_bundled(self):
        self.assertIn("不由本技能分发", self.text)


if __name__ == "__main__":
    unittest.main()
