"""SPI（FR-C11 / ADR-005）：示例外部插件可插拔 + 版本校验。

无工具链/插件时跳过。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.transform import _clang, _find_plugin  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELLO = os.path.join(REPO, "tests", "samples", "hello.c")
_LLVM_BIN = "/opt/anti-rea-toolchain/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04/bin"


def _opt() -> str | None:
    o = shutil.which("opt") or os.path.join(_LLVM_BIN, "opt")
    return o if os.path.exists(o) else None


def _example_plugin() -> str:
    return os.path.join(REPO, "engine", "build", "libanti_rea_example_plugin.so")


def _have() -> bool:
    try:
        _find_plugin()
        _clang()
    except Exception:
        return False
    return os.path.exists(_example_plugin())


@unittest.skipUnless(_have(), "需要已构建的 engine 插件 + 示例 SPI 插件")
class TestSPI(unittest.TestCase):
    def test_example_plugin_applies_and_preserves_behavior(self):
        """示例插件经 SPI 加载并施加；功能保持（免改核心引擎）。"""
        opt = _opt()
        if not opt:
            self.skipTest("无 opt")
        plug = _find_plugin()
        ex = _example_plugin()
        with tempfile.TemporaryDirectory() as t:
            ir = os.path.join(t, "h.ll")
            subprocess.run([_clang(), "-O1", "-S", "-emit-llvm", HELLO, "-o", ir],
                           check=True, capture_output=True)
            env = dict(os.environ)
            env["ANTI_REA_WHITELIST"] = "*"
            env["ANTI_REA_STRATEGIES"] = "example_marker"
            env["ANTI_REA_EXTRA_PLUGINS"] = ex
            out = os.path.join(t, "spi.ll")
            subprocess.run([opt, "-load-pass-plugin=" + plug,
                            "-passes=external-transforms", ir, "-S", "-o", out],
                           check=True, capture_output=True, env=env)
            with open(out, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("anti-rea-example", text)
            self.assertIn("anti_rea.example", text)

            # 功能保持：clang -fpass-plugin 路径
            def run(src, extra_env):
                e = os.path.join(t, "exe." + str(len(os.listdir(t))))
                subprocess.run([_clang(), "-O1", "-fpass-plugin=" + plug, src, "-o", e],
                               check=True, capture_output=True, env=extra_env)
                return subprocess.run([e], capture_output=True, text=True).stdout

            base = run(HELLO, dict(os.environ))
            got = run(HELLO, env)
            self.assertEqual(base, got)

    def test_incompatible_spi_version_rejected(self):
        """SPI_VERSION 不匹配 -> E_PLUGIN_INCOMPATIBLE，且不影响核心引擎。"""
        opt = _opt()
        if not opt:
            self.skipTest("无 opt")
        plug = _find_plugin()
        with tempfile.TemporaryDirectory() as t:
            bad_c = os.path.join(t, "bad.c")
            with open(bad_c, "w", encoding="utf-8") as fh:
                fh.write("int anti_rea_spi_version(void){return 999;}\n"
                         "void *anti_rea_register_plugin(void){return 0;}\n")
            bad = os.path.join(t, "libbad.so")
            subprocess.run([_clang(), "-shared", "-fPIC", bad_c, "-o", bad],
                           check=True, capture_output=True)
            ir = os.path.join(t, "h.ll")
            subprocess.run([_clang(), "-O1", "-S", "-emit-llvm", HELLO, "-o", ir],
                           check=True, capture_output=True)
            env = dict(os.environ)
            env["ANTI_REA_WHITELIST"] = "*"
            env["ANTI_REA_STRATEGIES"] = "example_marker"
            env["ANTI_REA_EXTRA_PLUGINS"] = bad
            p = subprocess.run([opt, "-load-pass-plugin=" + plug,
                                "-passes=external-transforms", ir, "-S",
                                "-o", os.path.join(t, "o.ll")],
                               capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 0)  # 拒载但不崩溃
            self.assertIn("E_PLUGIN_INCOMPATIBLE", p.stderr)


if __name__ == "__main__":
    unittest.main()
