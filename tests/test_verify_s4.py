"""S4 系统验证工具测试（M6）。"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.verify import (differential, overhead, independent,  # noqa: E402
                         reproducibility, robustness, matrix)
from core.scanner import scan  # noqa: E402
from core.strategy import plan  # noqa: E402
from core.transform import _clang, _find_plugin  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(REPO, "tests", "samples")
P0_SECRET = os.path.join(SAMPLES, "p0_secret.c")


def _have_toolchain() -> bool:
    try:
        _find_plugin()
        _clang()
        return True
    except Exception:
        return False


class TestDifferential(unittest.TestCase):
    def test_identical_binaries_no_mismatch(self):
        r = differential.run("/bin/true", "/bin/true", n=200, batch=20)
        self.assertTrue(r["pass"])
        self.assertEqual(r["iterations"], 200)

    def test_different_binaries_detected(self):
        r = differential.run("/bin/true", "/bin/false", n=200, batch=20)
        self.assertFalse(r["pass"])
        self.assertGreater(r["mismatches"], 0)
        self.assertIsNotNone(r["first_mismatch"])


class TestRobustness(unittest.TestCase):
    def test_timeout_controlled(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertTrue(robustness.timeout_probe(t)["timed_out"])

    def test_abnormal_inputs_controlled(self):
        with tempfile.TemporaryDirectory() as t:
            cases = robustness.abnormal_inputs(SAMPLES, t)
            self.assertTrue(all(c["controlled"] for c in cases), cases)

    def test_large_project(self):
        with tempfile.TemporaryDirectory() as t:
            r = robustness.large_project(t, n=30)
            self.assertTrue(r["pass"])
            self.assertTrue(r["schema_ok"])


class TestOverhead(unittest.TestCase):
    def test_measure_self_zero_overhead(self):
        r = overhead.measure("/bin/true", "/bin/true", reps=5, warmup=1)
        self.assertIn("overhead", r)
        self.assertEqual(r["reps"], 5)

    def test_budget_matches_srs(self):
        self.assertEqual(overhead.BUDGET["P0"], 0.40)   # NFR-01
        self.assertEqual(overhead.BUDGET["P1"], 0.15)
        self.assertEqual(overhead.BUDGET["P2"], 0.05)


class TestIndependent(unittest.TestCase):
    @unittest.skipUnless(shutil.which("objdump"), "无 objdump")
    def test_symbol_and_string_leak(self):
        with tempfile.TemporaryDirectory() as t:
            exe = os.path.join(t, "h")
            import subprocess
            subprocess.run([_clang(), os.path.join(SAMPLES, "hello.c"), "-o", exe],
                           check=True, capture_output=True)
            self.assertIn("secret_mix", independent.symbol_names(exe))
            self.assertTrue(independent.string_present(exe, "%d %d %d"))
            r = independent.verify(exe, exe, targets=["secret_mix"],
                                   needles=["%d %d %d"])
            self.assertFalse(r["independent_pass"])          # 同名 -> 泄漏
            self.assertTrue(independent.agrees_with_builtin(False, r))


@unittest.skipUnless(_have_toolchain(), "需要已构建的 engine 插件与 clang")
class TestReproducibilityAndMatrix(unittest.TestCase):
    def test_reproducible(self):
        with tempfile.TemporaryDirectory() as t:
            manifest = scan(SAMPLES)
            policy = plan(manifest, {"max_overhead": 0.5}, seed=7)
            r = reproducibility.check(policy, [P0_SECRET], SAMPLES, 7, t)
            self.assertTrue(r["identical"], r)

    def test_matrix_cross_probe(self):
        with tempfile.TemporaryDirectory() as t:
            rows = matrix.cross_target_probe(os.path.join(SAMPLES, "fuzz_target.c"), t)
            self.assertTrue(rows)
            self.assertTrue(any(r["ok"] for r in rows), rows)


if __name__ == "__main__":
    unittest.main()
