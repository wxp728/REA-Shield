"""白盒密码模块测试（FR-C10）。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import wbc  # noqa: E402


def _have_clang() -> bool:
    try:
        from core.transform import _clang
        _clang()
        return True
    except Exception:
        return False


class TestWBC(unittest.TestCase):
    def test_generate_reproducible(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            m1 = wbc.generate(a, seed=11)
            m2 = wbc.generate(b, seed=11)
            with open(m1["path"], encoding="utf-8") as f1, \
                 open(m2["path"], encoding="utf-8") as f2:
                self.assertEqual(f1.read(), f2.read())  # 可复现（NFR-04）
            m3 = wbc.generate(os.path.join(a, "s2"), seed=12)
            with open(m1["path"], encoding="utf-8") as f1, \
                 open(m3["path"], encoding="utf-8") as f3:
                self.assertNotEqual(f1.read(), f3.read())  # 不同 seed 不同份额

    def test_reject_bad_key(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                wbc.generate(d, key=b"short")

    @unittest.skipUnless(_have_clang(), "需要 clang")
    def test_selftest_roundtrip_and_no_key_constant(self):
        with tempfile.TemporaryDirectory() as d:
            wbc.generate(d, seed=7)
            st = wbc.selftest(d)
            self.assertTrue(st["pass"], st["output"])
            self.assertIn("roundtrip", st["output"])
            self.assertTrue(wbc.check_no_key_constant(st["exe"], wbc.derive_key(7)))


if __name__ == "__main__":
    unittest.main()
