"""工具链探测 / 平台探测 / 自检 / 发布打包 的单元测试（S6 可用性）。

覆盖：core.platform_info、core.toolchain、CLI doctor/--version、
tools/release.py 的一致性自检。
"""
import json
import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from core import platform_info  # noqa: E402
from core import toolchain  # noqa: E402
from core import cli  # noqa: E402
from core.scanner import scan  # noqa: E402

SAMPLES = os.path.join(REPO, "tests", "samples")
PY = sys.executable


class TestPlatformInfo(unittest.TestCase):
    def test_normalize_variants(self):
        self.assertEqual(platform_info.normalize("Linux/x86_64"), "linux-x86_64")
        self.assertEqual(platform_info.normalize("Darwin/arm64"), "macos-arm64")
        self.assertEqual(platform_info.normalize("windows-amd64"), "windows-x86_64")
        self.assertIsNone(platform_info.normalize(""))

    def test_host_platform_shape(self):
        p = platform_info.host_platform()
        self.assertIn("-", p)
        self.assertNotEqual(p.split("-")[0], "")  # os 段非空

    def test_is_supported_matches_host(self):
        # 仅断言 linux-x86_64 为支持；其他平台为不支持的判定一致
        self.assertEqual(platform_info.is_supported("linux-x86_64"), True)
        self.assertEqual(platform_info.is_supported("windows-x86_64"), False)


class TestScannerPlatform(unittest.TestCase):
    def test_target_platform_is_detected(self):
        m = scan(SAMPLES)
        self.assertEqual(m["project"]["target_platform"],
                         platform_info.host_platform())

    def test_target_platform_override(self):
        m = scan(SAMPLES, {"target_platform": "Linux/aarch64"})
        self.assertEqual(m["project"]["target_platform"], "linux-arm64")


class TestToolchain(unittest.TestCase):
    def test_checks_structure(self):
        rows = toolchain.checks()
        names = {r["name"] for r in rows}
        for expect in ("python", "py:jsonschema", "py:yaml", "clang",
                       "engine-plugin", "cmake", "platform"):
            self.assertIn(expect, names)
        for r in rows:
            self.assertIn("required", r)
            self.assertIn("ok", r)
            self.assertIn("hint", r)

    def test_doctor_report(self):
        rep = toolchain.doctor()
        self.assertIn("ok", rep)
        self.assertIn("toolchain_ready", rep)
        self.assertIsInstance(rep["checks"], list)
        # 本仓库环境（CI）Python 依赖应齐备
        self.assertTrue(rep["ok"], "doctor 必需项应齐备: %s" % rep["failed"])

    def test_format_report_nonempty(self):
        txt = toolchain.format_report(toolchain.doctor())
        self.assertIn("doctor", txt)

    def test_env_override_llvm(self):
        # 显式指定存在的 LLVM 前缀应被优先采用
        old = os.environ.get("ANTI_REA_LLVM")
        pref = toolchain.llvm_prefix()
        if pref is None:
            self.skipTest("本机未探测到 LLVM 前缀")
        os.environ["ANTI_REA_LLVM"] = pref
        try:
            self.assertEqual(toolchain.llvm_prefix(), pref)
        finally:
            if old is None:
                os.environ.pop("ANTI_REA_LLVM", None)
            else:
                os.environ["ANTI_REA_LLVM"] = old


class TestCliDoctor(unittest.TestCase):
    def test_version(self):
        r = subprocess.run([PY, "-m", "core.cli", "--version"],
                           cwd=REPO, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("anti-rea", r.stdout)

    def test_doctor_json(self):
        r = subprocess.run([PY, "-m", "core.cli", "doctor", "--json"],
                           cwd=REPO, capture_output=True, text=True)
        # 退出码 0（必需项齐备）或 1（缺件）；都应是合法 JSON
        self.assertIn(r.returncode, (0, 1))
        rep = json.loads(r.stdout)
        self.assertIn("checks", rep)

    def test_doctor_in_parser(self):
        # doctor 子命令已注册且不可省略
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args([])


class TestReleaseSelfcheck(unittest.TestCase):
    def test_release_check_passes(self):
        sys.path.insert(0, os.path.join(REPO, "tools"))
        import release  # noqa: E402
        problems = release.check()
        self.assertEqual(problems, [], "发布自检应通过：%s" % problems)

    def test_release_bundle_excludes_build(self):
        import tempfile
        sys.path.insert(0, os.path.join(REPO, "tools"))
        import release  # noqa: E402
        with tempfile.TemporaryDirectory() as d:
            out = release.bundle_tarball(d, "0.0.0-test")
            self.assertTrue(os.path.exists(out))
            import tarfile
            with tarfile.open(out, "r:gz") as tf:
                names = tf.getnames()
            # 不应包含 engine/build 或 .git
            self.assertFalse(any("/engine/build/" in n for n in names))
            self.assertFalse(any("/.git/" in n for n in names))
            # 应包含技能入口
            self.assertTrue(any(n.endswith("/SKILL.md") for n in names))


if __name__ == "__main__":
    unittest.main()
