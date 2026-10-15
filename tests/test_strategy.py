"""Strategy 单元测试（FR-B1/B2/B6）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import common  # noqa: E402
from core.strategy import plan  # noqa: E402


def _manifest(assets):
    return {
        "schema_version": "1.0",
        "run_id": "run-test",
        "project": {"language": "c", "build_system": "cmake",
                    "target_platform": "linux-x86_64"},
        "assets": assets,
        "summary": {"total": len(assets)},
    }


class TestStrategy(unittest.TestCase):
    def test_policy_valid_and_matched(self):
        m = _manifest([
            {"id": "a1", "path": "k.c", "type": "secret", "sensitivity": "P0",
             "skip_transform": False, "source": "auto"},
            {"id": "a2", "path": "u.c", "type": "util", "sensitivity": "P3",
             "skip_transform": False, "source": "auto"},
        ])
        p = plan(m, {"max_overhead": 0.2}, seed=1)
        common.validate(p, "protection_policy.schema.json")
        self.assertEqual(len(p["assets"]), 2)  # 无遗漏（FR-B2）
        p0 = next(a for a in p["assets"] if a["path"] == "k.c")
        self.assertIn("code_virtualization", p0["strategies"])
        p3 = next(a for a in p["assets"] if a["path"] == "u.c")
        self.assertEqual(p3["strategies"], [])

    def test_skip_transform_forces_noop(self):
        m = _manifest([
            {"id": "a1", "path": "oss.c", "type": "open_source", "sensitivity": "P3",
             "skip_transform": True, "source": "auto"},
        ])
        p = plan(m)
        self.assertEqual(p["assets"][0]["strategies"], [])


if __name__ == "__main__":
    unittest.main()
