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

    def test_variant_absolutizes_relative_includes(self):
        """变体副本被挪到 out_dir 后，相对引号 include 应改写为绝对路径（回归）。

        回归背景：源文件用 `#include "../../include/foo.h"` 时，副本挪位即断链
        （实测：PG 风格的 .c 全是这种写法，verify 的对抗步骤直接编译失败）。
        """
        with tempfile.TemporaryDirectory() as d:
            inc_dir = os.path.join(d, "inc")
            os.makedirs(inc_dir)
            hdr = os.path.join(inc_dir, "my.h")
            with open(hdr, "w", encoding="utf-8") as fh:
                fh.write("#define MY_X 1\n")
            src_dir = os.path.join(d, "src")
            os.makedirs(src_dir)
            src = os.path.join(src_dir, "a.c")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write('#include "../inc/my.h"\n'
                         '#include <stdio.h>\n'
                         'int secret_x(void){return MY_X;}\n'
                         'int main(void){return secret_x();}\n')
            out = os.path.join(d, "adv")
            res = adversarial.generate_variants(src, out, ["secret_x"], count=1, seed=1)
            with open(res["variants"][0]["path"], encoding="utf-8") as fh:
                txt = fh.read()
            self.assertIn(os.path.abspath(hdr), txt)   # 相对 -> 绝对
            self.assertIn("#include <stdio.h>", txt)   # 系统头原样
            clang = _clang()
            if clang:
                # 变体可单独编译（相对 include 已自足）
                subprocess.run([clang, "-O0", res["variants"][0]["path"], "-o",
                                os.path.join(d, "v.exe")], check=True, capture_output=True)

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
