"""对抗性诱导生成器测试（FR-C9）。"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adversarial  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P0_SECRET = os.path.join(REPO, "tests", "samples", "p0_secret.c")


def _clang() -> str | None:
    try:
        from core.transform import _clang
        return _clang()
    except Exception:
        return None


class TestAdversarial(unittest.TestCase):
    def test_variant_count_bounds(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                adversarial.generate_variants(P0_SECRET, d, count=0)
            with self.assertRaises(ValueError):
                adversarial.generate_variants(P0_SECRET, d, count=65)

    def test_variant_files_and_operators(self):
        with tempfile.TemporaryDirectory() as d:
            res = adversarial.generate_variants(P0_SECRET, d, ["secret_schedule"],
                                                count=2, seed=5)
            self.assertEqual(len(res["variants"]), 2)
            for v in res["variants"]:
                self.assertTrue(os.path.exists(v["path"]))
                with open(v["path"], encoding="utf-8") as fh:
                    txt = fh.read()
                self.assertIn("_induce", txt)          # 诱饵函数
                self.assertIn("TODO(security)", txt)   # 语义增强

    @unittest.skipUnless(_clang(), "需要 clang")
    def test_variants_functionally_equivalent(self):
        clang = _clang()
        with tempfile.TemporaryDirectory() as d:
            base_exe = os.path.join(d, "base")
            subprocess.run([clang, "-O0", P0_SECRET, "-o", base_exe],
                           check=True, capture_output=True)
            base = subprocess.run([base_exe], capture_output=True, text=True).stdout
            res = adversarial.generate_variants(P0_SECRET, d, ["secret_schedule"],
                                                count=3, seed=9)
            for v in res["variants"]:
                exe = v["path"] + ".exe"
                subprocess.run([clang, "-O0", v["path"], "-o", exe],
                               check=True, capture_output=True)
                out = subprocess.run([exe], capture_output=True, text=True).stdout
                self.assertEqual(base, out)  # 功能保持（NFR-03）


if __name__ == "__main__":
    unittest.main()
