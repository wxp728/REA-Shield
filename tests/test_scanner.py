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

    def test_detects_allman_style_function(self):
        """Allman / PostgreSQL 风格（返回类型独占一行）也必须能识别（回归）。

        背景：原 _FUNC_RE 的返回类型段用 [\\w \\t\\*]，无法跨换行，导致
        `int\\nsecret_mix(...)` 这类大 C 工程主流写法被整体漏检、protect 白名单为空。
        """
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "pg_style.c"), "w") as fh:
                fh.write("int\n"
                         "secret_mix(int x)\n"
                         "{\n"
                         "    return x;\n"
                         "}\n")
            m = scan(d, {"allow_unknown_owner": True})
            syms = {a.get("symbol") for a in m["assets"]}
            self.assertIn("secret_mix", syms)

    def test_detects_dotnet_build_and_language(self):
        """`.csproj`/`.sln` 与 `.cs` 应识别为 dotnet 语言 + dotnet 构建（P0 画像）。"""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "App.csproj"), "w") as fh:
                fh.write("<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n")
            with open(os.path.join(d, "Program.cs"), "w") as fh:
                fh.write("class Program { static void Main() {} }\n")
            m = scan(d, {"allow_unknown_owner": True})
            self.assertEqual(m["project"]["language"], "dotnet")
            self.assertEqual(m["project"]["build_system"], "msbuild")

    def test_detects_go_build_and_language(self):
        """`go.mod` 与 `.go` 应识别为 go 语言 + go 构建（P0 画像）。"""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "go.mod"), "w") as fh:
                fh.write("module example.com/demo\n\ngo 1.22\n")
            with open(os.path.join(d, "main.go"), "w") as fh:
                fh.write("package main\n\nfunc main() {}\n")
            m = scan(d, {"allow_unknown_owner": True})
            self.assertEqual(m["project"]["language"], "go")
            self.assertEqual(m["project"]["build_system"], "go")

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
