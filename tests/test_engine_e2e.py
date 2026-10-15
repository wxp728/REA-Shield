"""集成测试：变换引擎 + 端到端流水线（FR-C1/C2/C3/C6、FR-E1）。

若工具链/插件不可用则跳过（CI 中应先构建 engine/）。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import common  # noqa: E402
from core.scanner import scan  # noqa: E402
from core.strategy import plan  # noqa: E402
from core.transform import protect, _clang, _find_plugin  # noqa: E402
from core.evaluate import verify  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(REPO, "tests", "samples")
HELLO = os.path.join(SAMPLES, "hello.c")

_LLVM_BIN = "/opt/anti-rea-toolchain/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04/bin"


def _opt() -> str | None:
    o = shutil.which("opt") or os.path.join(_LLVM_BIN, "opt")
    return o if os.path.exists(o) else None


def _have_toolchain() -> bool:
    try:
        _find_plugin()
        _clang()
        return True
    except Exception:
        return False


@unittest.skipUnless(_have_toolchain(), "需要已构建的 engine 插件与 clang")
class TestEndToEnd(unittest.TestCase):
    def test_full_pipeline(self):
        with tempfile.TemporaryDirectory() as out:
            manifest = scan(SAMPLES)
            common.validate(manifest, "asset_manifest.schema.json")
            policy = plan(manifest, {"max_overhead": 0.2}, seed=3)
            policy["_run_id"] = manifest["run_id"]
            meta = protect(policy, [HELLO], out, root=SAMPLES, seed=3)
            self.assertEqual(meta["whitelist"], ["secret_mix"])  # 选择性（FR-C6）
            report = verify(out)
            self.assertTrue(report["functional_pass"], report)
            common.validate(report, "verification_report.schema.json")

    def test_transform_markers_and_selectivity(self):
        opt = _opt()
        if not opt:
            self.skipTest("无 opt")
        plug = _find_plugin()
        with tempfile.TemporaryDirectory() as t:
            ir = os.path.join(t, "hello.ll")
            subprocess.run([_clang(), "-O0", "-S", "-emit-llvm", HELLO, "-o", ir],
                           check=True, capture_output=True)
            env = dict(os.environ)
            env["ANTI_REA_WHITELIST"] = "*"
            env["ANTI_REA_STRATEGIES"] = "cff,mba,opaque"
            out = os.path.join(t, "prot.ll")
            subprocess.run([opt, "-load-pass-plugin=" + plug,
                            "-passes=reg2mem,anti-rea", ir, "-S", "-o", out],
                           check=True, capture_output=True, env=env)
            with open(out, encoding="utf-8") as fh:
                text = fh.read()
            self.assertGreater(text.count("cff.dispatch"), 0)   # FR-C1
            self.assertGreater(text.count("mba."), 0)           # FR-C2
            self.assertGreater(text.count("opq.t"), 0)          # FR-C3

            # 白名单不含任何函数 -> 零变换（FR-C6）
            env["ANTI_REA_WHITELIST"] = "nonexistent_symbol"
            out2 = os.path.join(t, "noop.ll")
            subprocess.run([opt, "-load-pass-plugin=" + plug,
                            "-passes=reg2mem,anti-rea", ir, "-S", "-o", out2],
                           check=True, capture_output=True, env=env)
            with open(out2, encoding="utf-8") as fh:
                text2 = fh.read()
            self.assertEqual(text2.count("mba."), 0)
            self.assertEqual(text2.count("cff.dispatch"), 0)


if __name__ == "__main__":
    unittest.main()
