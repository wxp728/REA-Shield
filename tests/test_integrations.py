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

from core.transform import (  # noqa: E402
    scope_env as _scope_env, _clang, _find_plugin, build_vm_object as _build_vm_object,
    export_map as _export_map)


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


class TestExports(unittest.TestCase):
    """导出收敛：由头文件生成版本脚本 + 包装器链接期应用 + strip。"""

    def test_export_map_from_header(self):
        with tempfile.TemporaryDirectory() as d:
            hdr = os.path.join(d, "api.h")
            with open(hdr, "w", encoding="utf-8") as fh:
                fh.write("int api_pub(int a);\nvoid internal_extra(void);\n")
            out = os.path.join(d, "exports.map")
            res = _export_map([hdr], out)
            self.assertIn("api_pub", res["symbols"])
            self.assertIn("internal_extra", res["symbols"])
            with open(out, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("global:", text)
            self.assertIn("local:", text)
            self.assertIn("api_pub;", text)

    @unittest.skipUnless(_have_cc_toolchain(), "需要 clang 与包装器")
    def test_version_script_and_strip_hide_nonapi(self):
        with tempfile.TemporaryDirectory() as d:
            lib = os.path.join(d, "l.c")
            hdr = os.path.join(d, "l.h")
            with open(lib, "w", encoding="utf-8") as fh:
                fh.write("int api_pub(int a){return a+1;}\n"
                         "int internal_extra(int a){return a*2;}\n")
            with open(hdr, "w", encoding="utf-8") as fh:
                fh.write("int api_pub(int a);\n")
            vmap = os.path.join(d, "exports.map")
            _export_map([hdr], vmap)
            obj = os.path.join(d, "l.o")
            subprocess.run([_clang(), "-O1", "-fPIC", "-c", lib, "-o", obj],
                           check=True, capture_output=True)
            so = os.path.join(d, "libl.so")
            env = dict(os.environ)
            env.update({"ANTI_REA_REAL_CC": _clang(),
                        "ANTI_REA_VERSION_SCRIPT": vmap, "ANTI_REA_STRIP": "1"})
            r = subprocess.run([CC_WRAPPER, "-shared", "-fPIC", obj, "-o", so],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            dyn = subprocess.run(["nm", "-D", so], capture_output=True,
                                 text=True).stdout
            self.assertIn("api_pub", dyn)          # 公共 API 保留
            self.assertNotIn("internal_extra", dyn)  # 非 API 本地化


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

    def test_vm_runtime_linked_into_shared_lib(self):
        """构建注入 + 代码虚拟化：产出真实 .so，链接期自动并入 VM 运行期，功能保持。"""
        lib = """\
static int helper_xyz(int a) { return a * 3 + 1; }
int compute(int a) { return helper_xyz(a) ^ 0x5a; }
"""
        drv = """\
extern int compute(int);
int main(void) { return compute(7) == 76 ? 0 : 1; }
"""
        with tempfile.TemporaryDirectory() as d:
            ls = os.path.join(d, "s.c")
            lm = os.path.join(d, "m.c")
            with open(ls, "w", encoding="utf-8") as fh:
                fh.write(lib)
            with open(lm, "w", encoding="utf-8") as fh:
                fh.write(drv)
            policy = {"seed": 11, "assets": [{"path": "s.c", "sensitivity": "P0",
                      "strategies": ["code_virtualization", "identifier_renaming"]}]}
            env = dict(os.environ)
            env.update(_scope_env(policy, d, protect_all=True))
            env["ANTI_REA_REAL_CC"] = _clang()
            env["ANTI_REA_VM_OBJ"] = _build_vm_object(os.path.join(d, "anti_rea_vm.o"))

            # 逐 TU 编译 + 链接成共享库（链接期自动并入 VM 对象）
            obj = os.path.join(d, "s.o")
            r = subprocess.run([CC_WRAPPER, "-O1", "-fPIC", "-c", ls, "-o", obj],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            so = os.path.join(d, "libs.so")
            r = subprocess.run([CC_WRAPPER, "-shared", "-fPIC", obj, "-o", so],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)

            exe = os.path.join(d, "m")
            r = subprocess.run([_clang(), lm, "-L" + d, "-ls", "-Wl,-rpath," + d, "-o", exe],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(subprocess.run([exe]).returncode, 0)   # compute(7)==76


if __name__ == "__main__":
    unittest.main()
