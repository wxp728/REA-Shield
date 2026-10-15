"""S5 Beta 试点工程测试（M7）。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scanner import scan  # noqa: E402
from core.transform import _clang, _find_plugin  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PILOTS = {
    "crypto-lib": {"root": "pilots/crypto-lib", "source": "src/license.c",
                   "symbols": {"secret_key_schedule", "verify_license"}},
    "protocol-svc": {"root": "pilots/protocol-svc", "source": "src/decode.cpp",
                     "symbols": {"secret_decode_frame", "derive_frame"}},
    "python-ext": {"root": "pilots/python-ext", "source": "src/transform.c",
                   "symbols": {"secret_key_schedule"}},
}


def _have_toolchain() -> bool:
    try:
        _find_plugin()
        _clang()
        return True
    except Exception:
        return False


class TestPilotLayout(unittest.TestCase):
    def test_layout(self):
        for name, p in PILOTS.items():
            d = os.path.join(REPO, p["root"])
            self.assertTrue(os.path.exists(os.path.join(d, "LICENSE")), name)
            self.assertTrue(os.path.exists(os.path.join(d, "README.md")), name)
            self.assertTrue(os.path.exists(os.path.join(d, p["source"])), name)


class TestPilotDetection(unittest.TestCase):
    def test_scan_detects_sensitive_symbols(self):
        for name, p in PILOTS.items():
            m = scan(os.path.join(REPO, p["root"]))
            found = {a.get("symbol") for a in m["assets"]}
            self.assertTrue(p["symbols"] <= found,
                            "%s: 期望 %s，实际 %s" % (name, p["symbols"], found))


@unittest.skipUnless(_have_toolchain(), "需要已构建的 engine 插件与 clang")
class TestPilotLoop(unittest.TestCase):
    def test_crypto_lib_loop(self):
        from tools import run_s5
        with tempfile.TemporaryDirectory() as t:
            pilot = next(p for p in run_s5.PILOTS if p["id"] == "crypto-lib")
            r = run_s5._run_native(pilot, t)
            self.assertTrue(r["functional_pass"], r)
            self.assertTrue(r["attack_verdict_pass"], r)
            self.assertIn("secret_key_schedule", r["whitelist"])


if __name__ == "__main__":
    unittest.main()
