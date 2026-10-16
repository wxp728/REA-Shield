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
CC_WRAPPER = os.path.join(INT, "cc-wrapper", "anti-rea-cc")

sys.path.insert(0, REPO)

from core.transform import scope_env as _scope_env, _clang, _find_plugin  # noqa: E402


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


@unittest.skipUnless(shutil.which("cargo") or shutil.which("rustc") or
                     os.path.exists(os.path.expanduser("~/.cargo/bin/cargo")),
                     "无 cargo/rustc")
class TestCargoIntegration(unittest.TestCase):
    def test_sample_project(self):
        with tempfile.TemporaryDirectory() as t:
            proj = os.path.join(t, "example")
            shutil.copytree(os.path.join(INT, "cargo", "example"), proj)
            env = _env()
            env["PATH"] = os.path.expanduser("~/.cargo/bin") + os.pathsep + env.get("PATH", "")
            env["CARGO_NET_OFFLINE"] = "true"
            cargo = shutil.which("cargo", path=env["PATH"]) or "cargo"
            subprocess.run([cargo, "build"], cwd=proj, check=True,
                           capture_output=True, env=env)
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


def _have_cc_toolchain() -> bool:
    try:
        _find_plugin()
        _clang()
        return os.path.exists(CC_WRAPPER)
    except Exception:
        return False


@unittest.skipUnless(_have_cc_toolchain(), "需要已构建的 engine 插件与 clang")
class TestCCWrapper(unittest.TestCase):
    """构建注入：CC 包装器在编译步骤挂插件、链接步骤透传（产出真实产物）。"""

    SRC = """\
#include <stdint.h>
static int helper_xyz(int a) { return a * 3 + 1; }
int secret_mix(int a) { return helper_xyz(a) ^ 0x5a; }
int main(void) { return secret_mix(1) == secret_mix(1) ? 0 : 1; }
"""

    def test_compile_injects_link_passthrough(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "s.c")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(self.SRC)
            policy = {"seed": 9, "assets": [{"path": "s.c", "sensitivity": "P0",
                      "strategies": ["control_flow_flattening", "identifier_renaming"]}]}
            env = dict(os.environ)
            env.update(_scope_env(policy, d, protect_all=True))
            env["ANTI_REA_REAL_CC"] = _clang()

            obj = os.path.join(d, "s.o")
            r = subprocess.run([CC_WRAPPER, "-O1", "-c", src, "-o", obj],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            nm = subprocess.run(["nm", obj], capture_output=True, text=True).stdout
            self.assertNotIn("helper_xyz", nm)   # 内部辅助函数已改名

            # 链接步骤（无 -c）应透传，产出可执行且功能保持
            exe = os.path.join(d, "s")
            r = subprocess.run([CC_WRAPPER, obj, "-o", exe],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(subprocess.run([exe]).returncode, 0)

            # -E 预处理不注入
            r = subprocess.run([CC_WRAPPER, "-E", src], capture_output=True,
                               text=True, env=env)
            self.assertEqual(r.returncode, 0)

    def test_disable_passthrough(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "s.c")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(self.SRC)
            env = dict(os.environ)
            env["ANTI_REA_DISABLE"] = "1"
            env["ANTI_REA_REAL_CC"] = _clang()
            obj = os.path.join(d, "s.o")
            r = subprocess.run([CC_WRAPPER, "-O0", "-c", src, "-o", obj],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            nm = subprocess.run(["nm", obj], capture_output=True, text=True).stdout
            self.assertIn("helper_xyz", nm)      # 未注入 -> 名字保留


if __name__ == "__main__":
    unittest.main()
