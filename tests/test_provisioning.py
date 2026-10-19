"""分级安装 / 按需获取（provisioning）的一致性测试。

覆盖：
  - `skill.json` 的 `provisioning` / `deploy` 与 `requirements`（核心 vs 按需）
  - `doctor` 自检项带 tier/when，并支持 `-tier` 过滤与分组报告
  - `requirements.txt`（T0）与 `requirements-optional.txt`（T3）的拆分
  - `tools/release.py` 的「最小技能包」不打包开发/审计材料
  - `docs/PROVISIONING.md` 存在且被 SKILL.md / skill.json / release 自检引用

保证"最小安装 + 按需下载"的策略不会随演进悄悄破损（例如又把 deap 塞回核心依赖，
或把 tests/poc 打进技能包）。
"""
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

GUIDE = os.path.join(REPO, "docs", "PROVISIONING.md")
SKILL_JSON = os.path.join(REPO, "skill.json")
SKILL_MD = os.path.join(REPO, "SKILL.md")

TIERS = ["T0", "T1", "T2", "T3", "T4"]


def _skill():
    with open(SKILL_JSON, encoding="utf-8") as fh:
        return json.load(fh)


class TestProvisioningManifest(unittest.TestCase):
    def test_guide_exists(self):
        self.assertTrue(os.path.exists(GUIDE), "缺少 docs/PROVISIONING.md")

    def test_tiers_declared_and_complete(self):
        prov = _skill()["provisioning"]
        self.assertEqual(sorted(prov["tiers"]), sorted(TIERS))
        for tier, info in prov["tiers"].items():
            for key in ("name", "when", "components", "bundled"):
                self.assertIn(key, info, "%s 缺字段 %s" % (tier, key))
            self.assertTrue(info["components"], "%s components 为空" % tier)
        # 第三方一律不打包：只有 T0 可以带"技能自身源码"
        self.assertNotEqual(_skill()["provisioning"]["tiers"]["T1"]["bundled"], True)
        for tier in ("T2", "T3", "T4"):
            self.assertFalse(prov["tiers"][tier]["bundled"], "%s 不应打包" % tier)

    def test_deferral_rules_present(self):
        prov = _skill()["provisioning"]
        self.assertTrue(prov["deferral_rules"])
        joined = " ".join(prov["deferral_rules"])
        self.assertIn("P0", joined)
        self.assertIn("P1", joined)

    def test_guide_wired_into_skill_json(self):
        skill = _skill()
        self.assertEqual(skill["guides"]["provisioning"], "docs/PROVISIONING.md")
        self.assertEqual(skill["provisioning"]["guide"], "docs/PROVISIONING.md")

    def test_deploy_sets_and_bundle_cmd(self):
        deploy = _skill()["deploy"]
        for key in ("minimal", "add_for_protect", "optional",
                    "dev_only_not_shipped", "bundle_cmd"):
            self.assertIn(key, deploy)
        # 最小集必须能跑 scan/plan/doctor
        for rel in ("SKILL.md", "skill.json", "core/", "schemas/", "policies/",
                    "requirements.txt"):
            self.assertIn(rel, deploy["minimal"])
        # 设计/开发材料明确"不下发"
        for rel in ("tests/", "poc/", "docs/design/"):
            self.assertIn(rel, deploy["dev_only_not_shipped"])


class TestRequirementsSplit(unittest.TestCase):
    def _read(self, name):
        with open(os.path.join(REPO, name), encoding="utf-8") as fh:
            return fh.read()

    def test_core_requirements_has_no_deap(self):
        core = self._read("requirements.txt")
        self.assertNotIn("deap", core.lower())
        self.assertIn("jsonschema", core)
        self.assertIn("PyYAML", core)

    def test_optional_requirements_has_deap(self):
        opt = self._read("requirements-optional.txt")
        self.assertIn("deap", opt)

    def test_skill_json_python_packages_are_core_only(self):
        req = _skill()["requirements"]
        self.assertEqual(sorted(req["python_packages"]),
                         ["PyYAML>=6.0", "jsonschema>=4.0"])
        self.assertIn("deap", req["optional"])
        self.assertEqual(req["tier"], "T0")

    def test_pyproject_extras(self):
        with open(os.path.join(REPO, "pyproject.toml"), encoding="utf-8") as fh:
            text = fh.read()
        deps = text.split("dependencies = [")[1].split("]")[0]
        self.assertNotIn("deap", deps)
        self.assertIn("evolve", text)
        self.assertIn("deap>=1.4", text)

    def test_makefile_targets(self):
        mk = self._read("Makefile")
        self.assertIn("install-extras", mk)
        self.assertIn("requirements-optional.txt", mk)


class TestDoctorTiers(unittest.TestCase):
    def setUp(self):
        from core import toolchain
        self.toolchain = toolchain

    def test_every_check_has_tier_and_when(self):
        tiers = set(self.toolchain.PROVISION_TIERS)
        for row in self.toolchain.checks():
            self.assertIn("tier", row, row["name"])
            self.assertIn(row["tier"], tiers, row["name"])
            self.assertTrue(row.get("when"), "%s 缺 when" % row["name"])

    def test_core_checks_are_python_only(self):
        rows = {r["name"]: r for r in self.toolchain.checks()}
        for name in ("python", "py:jsonschema", "py:yaml"):
            self.assertEqual(rows[name]["tier"], "T0")
            self.assertTrue(rows[name]["required"], "%s 应为必需" % name)
        self.assertEqual(rows["py:deap"]["tier"], "T3")
        self.assertFalse(rows["py:deap"]["required"])

    def test_native_checks_are_on_demand(self):
        rows = {r["name"]: r for r in self.toolchain.checks()}
        for name in ("clang", "opt", "engine-plugin", "cmake"):
            self.assertEqual(rows[name]["tier"], "T1", name)
            self.assertFalse(rows[name]["required"], "%s 不应强制" % name)

    def test_doctor_filter_by_tier(self):
        rep = self.toolchain.doctor("T1")
        self.assertEqual(rep["tier"], "T1")
        self.assertTrue(rep["checks"])
        self.assertTrue(all(r["tier"] == "T1" for r in rep["checks"]))
        # T1 全是按需项 → 不阻塞自检通过
        self.assertTrue(rep["ok"])

    def test_report_groups_tiers_and_explains(self):
        text = self.toolchain.format_report(self.toolchain.doctor())
        self.assertIn("doctor", text)
        # T1/T2/T3 是"按需"分级，必须分组显示并说明何时需要；
        # T4（永不下发）不参与自检，故不出现。
        for tier in ("T1", "T2", "T3"):
            self.assertIn(tier, text, "报告未分组 %s" % tier)
        self.assertIn("按需", text)
        self.assertNotIn("T4", text)


class TestSkillBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "release_tool", os.path.join(REPO, "tools", "release.py"))
        cls.release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.release)

    def test_skill_file_set_excludes_dev_material(self):
        files = self.release.skill_file_set()
        self.assertIn("SKILL.md", files)
        self.assertIn("core/cli.py", files)
        self.assertIn("engine/CMakeLists.txt", files)
        for rel in files:
            for bad in self.release.SKILL_EXCLUDE:
                self.assertFalse(rel == bad or rel.startswith(bad.rstrip("/") + "/"),
                                 "最小技能集不应包含 %s" % rel)

    def test_bundle_tarball_has_no_dev_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.release.skill_bundle(tmp, "0.0.0-test")
            self.assertTrue(os.path.exists(out))
            with tarfile.open(out) as tf:
                names = tf.getnames()
            self.assertTrue(any(n.endswith("/SKILL.md") for n in names))
            for bad in ("/tests/", "/poc/", "/pilots/", "/benchmarks/",
                        "/docs/design/", "/docs/release/"):
                self.assertFalse(any(bad in n for n in names),
                                 "技能包不应包含 %s" % bad)

    def test_release_check_requires_provisioning_docs(self):
        required = self.release.check()
        self.assertEqual(required, [])


class TestSkillMdWiring(unittest.TestCase):
    def test_skill_md_mentions_provisioning(self):
        with open(SKILL_MD, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("docs/PROVISIONING.md", text)
        self.assertIn("requirements-optional.txt", text)

    def test_cli_doctor_supports_tier_flag(self):
        py = sys.executable
        r = subprocess.run([py, "-m", "core.cli", "doctor", "--tier", "T0"],
                           cwd=REPO, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("T0", r.stdout)
        # 未知分级应报错
        r2 = subprocess.run([py, "-m", "core.cli", "doctor", "--tier", "T9"],
                            cwd=REPO, capture_output=True, text=True)
        self.assertNotEqual(r2.returncode, 0)


if __name__ == "__main__":
    unittest.main()
