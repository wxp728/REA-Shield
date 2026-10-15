"""Scanner 单元测试（FR-A1/A2/A3/A5/A6）。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import common  # noqa: E402
from core.scanner import scan  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(REPO, "tests", "samples")


class TestScanner(unittest.TestCase):
    def test_scan_sample_valid_schema(self):
        m = scan(SAMPLES)
        common.validate(m, "asset_manifest.schema.json")  # 不抛即通过
        self.assertGreaterEqual(m["summary"]["total"], 1)
        self.assertEqual(m["project"]["language"], "c")

    def test_detects_sensitive_function(self):
        m = scan(SAMPLES)
        syms = {a.get("symbol") for a in m["assets"]}
        self.assertIn("secret_mix", syms)
        sm = next(a for a in m["assets"] if a.get("symbol") == "secret_mix")
        self.assertEqual(sm["type"], "secret")
        self.assertIn(sm["sensitivity"], ("P0", "P1"))
        self.assertTrue(sm["evidence"])  # 分级带证据（FR-A3）

    def test_refuse_unknown_owner(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "x.c"), "w") as fh:
                fh.write("int secret_fn(int x){return x;}\n")
            with self.assertRaises(PermissionError):
                scan(d, {"allow_unknown_owner": False})
            # 显式允许后可扫描
            m = scan(d, {"allow_unknown_owner": True})
            common.validate(m, "asset_manifest.schema.json")


if __name__ == "__main__":
    unittest.main()
