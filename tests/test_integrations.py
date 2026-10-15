"""构建集成测试（FR-D2…D5）：样例工程成功接入并产出保护产物。

相应工具链缺失时跳过（Cargo 需 rustc/cargo）。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INT = os.path.join(REPO, "integrations")
DRIVER = os.path.join(INT, "anti-rea")


def _env() -> dict:
    e = dict(os.environ)
    e["ANTI_REA_PYTHON"] = sys.executable
    e["ANTI_REA_DRIVER"] = DRIVER
    return e


def _report_ok(out_dir: str) -> None:
    rp = os.path.join(out_dir, "verification_report.json")
    assert os.path.exists(rp), "缺少 verification_report.json"
    with open(rp, encoding="utf-8") as fh:
        rep = json.load(fh)
    assert rep["functional_pass"], rep
    assert rep["overall_pass"], rep
    assert os.path.isdir(os.path.join(out_dir, "artifacts"))


@unittest.skipUnless(shutil.which("cmake"), "无 cmake")
class TestCmakeIntegration(unittest.TestCase):
    def test_sample_project(self):
        src = os.path.join(INT, "cmake", "example")
        with tempfile.TemporaryDirectory() as b:
            subprocess.run(["cmake", "-S", src, "-B", b], check=True,
                           capture_output=True, env=_env())
            subprocess.run(["cmake", "--build", b], check=True,
                           capture_output=True, env=_env())
            _report_ok(os.path.join(b, "anti-rea"))


@unittest.skipUnless(shutil.which("npm"), "无 npm")
class TestNpmIntegration(unittest.TestCase):
    def test_sample_project(self):
        with tempfile.TemporaryDirectory() as t:
            pkg = os.path.join(t, "npm")
            shutil.copytree(os.path.join(INT, "npm"), pkg)
            proj = os.path.join(pkg, "example")
            subprocess.run(["npm", "run", "build"], cwd=proj, check=True,
                           capture_output=True, env=_env())
            _report_ok(os.path.join(proj, "anti-rea"))


@unittest.skipUnless(shutil.which("cargo") or shutil.which("rustc"),
                     "无 cargo/rustc")
class TestCargoIntegration(unittest.TestCase):
    def test_sample_project(self):
        with tempfile.TemporaryDirectory() as t:
            proj = os.path.join(t, "example")
            shutil.copytree(os.path.join(INT, "cargo", "example"), proj)
            shutil.copy(os.path.join(INT, "cargo", "build.rs"),
                        os.path.join(proj, "build.rs"))
            subprocess.run(["cargo", "build"], cwd=proj, check=True,
                           capture_output=True, env=_env())
            _report_ok(os.path.join(proj, "anti-rea"))


class TestPythonIntegration(unittest.TestCase):
    def _have_setuptools(self) -> bool:
        try:
            import setuptools  # noqa: F401
            return True
        except Exception:
            return False

    def test_sample_project(self):
        if not self._have_setuptools():
            self.skipTest("无 setuptools")
        with tempfile.TemporaryDirectory() as t:
            pkg = os.path.join(t, "python")
            shutil.copytree(os.path.join(INT, "python"), pkg)
            proj = os.path.join(pkg, "example")
            r = subprocess.run([sys.executable, "setup.py", "build_ext", "--inplace"],
                               cwd=proj, capture_output=True, text=True, env=_env())
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            _report_ok(os.path.join(proj, "anti-rea"))


if __name__ == "__main__":
    unittest.main()
