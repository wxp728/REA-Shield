"""作用域收窄（allowlist）与整文件保护测试（gap#7 修复）。

- `scan --include/--exclude`、`plan --only-path/--only-func` 的过滤语义；
- `protect --protect-all` 的白名单按文件全量取名（含内部辅助函数）。
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import common  # noqa: E402
from core import toolchain  # noqa: E402
from core.scanner import scan, scanner  # noqa: E402
from core.strategy import plan  # noqa: E402
from core.transform import protect, _whitelist_symbols, _clang, _find_plugin  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SAMPLE = """\
#include <stdint.h>

/* 名字不含任何扫描规则关键词的内部辅助函数（gap#7 的漏名来源） */
static int helper_xyz(int a) { return a * 3 + 1; }

/* 名字含 crypto 关键词的敏感函数 */
int secret_mix(int a) { return helper_xyz(a) ^ 0x5a; }
"""


def _write(d: str) -> str:
    p = os.path.join(d, "secret.c")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE)
    return p


def _have_toolchain() -> bool:
    try:
        _find_plugin()
        _clang()
        return True
    except Exception:
        return False


class TestScannerNames(unittest.TestCase):
    def test_all_function_names_covers_static_helpers(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d)
            alln = set(scanner.all_function_names(p))
            self.assertIn("helper_xyz", alln)   # 全量取名：覆盖内部辅助函数
            self.assertIn("secret_mix", alln)
            # 资产扫描按名称规则过滤 -> 不含 helper_xyz
            scanned = {c.get("symbol") for c in scanner._scan_file(p)}
            self.assertIn("secret_mix", scanned)
            self.assertNotIn("helper_xyz", scanned)


class TestScopeFilter(unittest.TestCase):
    def _manifest(self) -> dict:
        return {"run_id": "r", "project": {"language": "c"},
                "assets": [
                    {"path": "src/a/crypto.c", "symbol": "secret_mix",
                     "sensitivity": "P0", "type": "crypto", "line": 1, "evidence": []},
                    {"path": "src/a/util.c", "symbol": "plain_add",
                     "sensitivity": "P3", "type": "util", "line": 1, "evidence": []},
                    {"path": "src/b/other.c", "symbol": "secret_mix",
                     "sensitivity": "P0", "type": "crypto", "line": 1, "evidence": []},
                ]}

    def test_only_path(self):
        pol = plan(self._manifest(), scope={"only_path": ["src/a/*"]})
        paths = {a["path"] for a in pol["assets"]}
        self.assertEqual(paths, {"src/a/crypto.c", "src/a/util.c"})

    def test_only_func(self):
        pol = plan(self._manifest(), scope={"only_func": ["^secret_"]})
        self.assertEqual({a["path"] for a in pol["assets"]},
                         {"src/a/crypto.c", "src/b/other.c"})

    def test_no_scope_keeps_all(self):
        pol = plan(self._manifest())
        self.assertEqual(len(pol["assets"]), 3)

    def test_scan_include_exclude(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "keep"))
            os.makedirs(os.path.join(d, "drop"))
            for sub in ("keep", "drop"):
                with open(os.path.join(d, sub, "secret.c"), "w", encoding="utf-8") as fh:
                    fh.write(SAMPLE)
            m = scan(d, {"allow_unknown_owner": True, "include": ["keep"]})
            self.assertTrue(all(a["path"].startswith("keep") for a in m["assets"]), m["assets"])
            m2 = scan(d, {"allow_unknown_owner": True, "exclude": ["drop"]})
            self.assertTrue(all(a["path"].startswith("keep") for a in m2["assets"]))


class TestWhitelistProtectAll(unittest.TestCase):
    def test_whitelist_all_vs_named(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d)
            policy = {"assets": [{"path": "secret.c", "sensitivity": "P0",
                                  "strategies": ["control_flow_flattening"]}]}
            named = _whitelist_symbols(policy, d, "ir", False)
            self.assertIn("secret_mix", named)
            self.assertNotIn("helper_xyz", named)
            allw = _whitelist_symbols(policy, d, "ir", True)
            self.assertIn("secret_mix", allw)
            self.assertIn("helper_xyz", allw)


@unittest.skipUnless(_have_toolchain(), "需要已构建的 engine 插件与 clang")
class TestProtectAllEndToEnd(unittest.TestCase):
    SRC = """\
#include <stdint.h>
static const unsigned char tbl[8] = {1,2,3,4,5,6,7,8};
static int helper_xyz(int a) { return (int)tbl[a & 7] * 3 + 1; }
int secret_mix(int a) { return helper_xyz(a) ^ 0x5a; }
int main(void) { return secret_mix(3) == secret_mix(3) ? 0 : 1; }
"""

    def test_internal_names_hidden(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "s.c")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(self.SRC)
            policy = {"seed": 5, "assets": [{"path": "s.c", "sensitivity": "P0",
                      "strategies": ["control_flow_flattening", "identifier_renaming",
                                     "string_encryption", "function_boundary_perturbation"]}]}
            out = os.path.join(d, "out")
            meta = protect(policy, [src], out, root=d, seed=5, protect_all=True)
            self.assertIn("helper_xyz", meta["whitelist"])
            nm = subprocess.run(["nm", os.path.join(out, "artifacts", "protected")],
                                capture_output=True, text=True).stdout
            # 内部辅助函数与常量表名（原样或带后缀）均不应出现
            self.assertNotIn("helper_xyz", nm)
            self.assertNotIn("tbl", nm)


if __name__ == "__main__":
    unittest.main()
