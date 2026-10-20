"""JavaScript / TypeScript 反 REA 选项目录的一致性测试。

覆盖：`docs/js-anti-rea-options.yaml`（机器可读清单）的结构与自洽性、
`docs/js-anti-rea.md`（人读指南）存在、运行时/分发形态提示、以及
`skill.json` / `SKILL.md` 的接线。与 `test_java_options.py` / `test_dotnet_options.py` 同构。
"""
import json
import os
import unittest

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUIDE = os.path.join(REPO, "docs", "js-anti-rea.md")
CATALOG = os.path.join(REPO, "docs", "js-anti-rea-options.yaml")
SKILL_JSON = os.path.join(REPO, "skill.json")
SKILL_MD = os.path.join(REPO, "SKILL.md")

EXPECTED_IDS = ["JS0", "JS1", "JS2", "JS3", "JS4", "JS5", "JS6", "JS7", "JS8"]
REQUIRED_OPTION_KEYS = {
    "id", "name", "principle", "effect", "effectiveness",
    "pros", "cons", "impacts", "tools", "best_for", "verify",
}


class TestJsOptionsCatalog(unittest.TestCase):
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

    def test_runtime_notes_reference_known_options(self):
        known = {o["id"] for o in self.doc["options"]}
        runtimes = self.doc["runtimes"]
        for runtime in ("browser", "node", "electron", "react_native"):
            self.assertIn(runtime, runtimes)
            self.assertTrue(runtimes[runtime]["notes"])
            self.assertTrue(runtimes[runtime]["recommended"])
            self.assertFalse(set(runtimes[runtime]["recommended"]) - known,
                             "%s 推荐了未知选项" % runtime)

    def test_verification_methodology_present(self):
        ver = self.doc["verification"]
        self.assertIn("verify/attack_sim", ver["note"])
        names = {t["name"] for t in ver["tools"]}
        for expected in ("js-beautify / prettier", "webcrack", "de4js", "REstringer",
                         "wasm2wat / wasm-decompile", "asar", "hbctool / hermes-dec"):
            self.assertIn(expected, names)
        self.assertTrue(ver["steps"])
        self.assertTrue(ver["metrics"])

    def test_skill_json_wired(self):
        with open(SKILL_JSON, encoding="utf-8") as fh:
            skill = json.load(fh)
        js = skill["js_anti_rea"]
        self.assertFalse(js["ir_transforms"])
        self.assertEqual(js["guide"], "docs/js-anti-rea.md")
        self.assertEqual(js["catalog"], "docs/js-anti-rea-options.yaml")
        self.assertEqual([o["id"] for o in js["options"]], EXPECTED_IDS)
        self.assertEqual(skill["guides"]["js_anti_rea"], "docs/js-anti-rea.md")

    def test_skill_md_links_the_guide(self):
        with open(SKILL_MD, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("docs/js-anti-rea.md", text)
        self.assertIn("docs/js-anti-rea-options.yaml", text)
        self.assertIn("JS0", text)


class TestJsDocClaims(unittest.TestCase):
    """几条容易"说过头"的事实口径，固定为可回归的断言。"""

    @classmethod
    def setUpClass(cls):
        with open(GUIDE, encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_source_map_warning(self):
        self.assertIn("source map", self.text)
        self.assertIn("不外发", self.text)

    def test_asar_is_not_encryption(self):
        self.assertIn("ASAR 不是加密", self.text)

    def test_hermes_is_not_irreversible(self):
        self.assertIn("Hermes", self.text)
        self.assertIn("不是不可逆", self.text)

    def test_mentions_wasm_and_native_offload(self):
        self.assertIn("WebAssembly", self.text)
        self.assertIn("N-API", self.text)

    def test_tools_not_bundled(self):
        self.assertIn("不由本技能分发", self.text)


if __name__ == "__main__":
    unittest.main()
