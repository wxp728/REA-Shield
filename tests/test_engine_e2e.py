"""集成测试：变换引擎 + 端到端流水线（FR-C1/C2/C3/C6、FR-E1）。

若工具链/插件不可用则跳过（CI 中应先构建 engine/）。
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import common  # noqa: E402
from core import toolchain  # noqa: E402
from core.scanner import scan  # noqa: E402
from core.strategy import plan  # noqa: E402
from core.transform import protect, _clang, _find_plugin  # noqa: E402
from core.evaluate import verify  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(REPO, "tests", "samples")
HELLO = os.path.join(SAMPLES, "hello.c")
P0_SECRET = os.path.join(SAMPLES, "p0_secret.c")


def _opt() -> str | None:
    return toolchain.find_opt()


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
            # 选择性（FR-C6）：命中的敏感函数入白名单，普通函数不入
            self.assertIn("secret_mix", meta["whitelist"])
            for plain in ("add", "classify", "main"):
                self.assertNotIn(plain, meta["whitelist"])
            report = verify(out)
            self.assertTrue(report["functional_pass"], report)
            common.validate(report, "verification_report.schema.json")

    def test_vm_virtualization_pipeline(self):
        """P0 资产经代码虚拟化（FR-C7）后功能保持。"""
        with tempfile.TemporaryDirectory() as out:
            manifest = scan(SAMPLES)
            policy = plan(manifest, {"max_overhead": 0.5}, seed=7)
            policy["_run_id"] = manifest["run_id"]
            meta = protect(policy, [P0_SECRET], out, root=SAMPLES, seed=7)
            self.assertIn("virtualize", meta["strategies"])
            self.assertTrue(meta["vmp_whitelist"], meta)
            report = verify(out)
            self.assertTrue(report["functional_pass"], report)

    def test_vm_ir_lowering_runs_correctly(self):
        """vm-virtualize：IR 含解释器调用，且链接后功能与基线一致。"""
        opt = _opt()
        if not opt:
            self.skipTest("无 opt")
        plug = _find_plugin()
        with tempfile.TemporaryDirectory() as t:
            ir = os.path.join(t, "p0.ll")
            subprocess.run([_clang(), "-O1", "-S", "-emit-llvm", P0_SECRET, "-o", ir],
                           check=True, capture_output=True)
            out_ll = os.path.join(t, "p0.prot.ll")
            env = dict(os.environ)
            env["ANTI_REA_SEED"] = "7"
            subprocess.run([opt, "-load-pass-plugin=" + plug,
                            "-passes=reg2mem,vm-virtualize", ir, "-S", "-o", out_ll],
                           check=True, capture_output=True, env=env)
            with open(out_ll, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("anti_rea_vm_run", text)          # FR-C7
            self.assertIn("__anti_rea_vm_code_", text)

            def build_and_run(src, exe):
                subprocess.run([_clang(), src, "-o", exe],
                               check=True, capture_output=True)
                p = subprocess.run([exe], capture_output=True, text=True)
                return p.stdout

            base = build_and_run(P0_SECRET, os.path.join(t, "base"))
            vm_bc = os.path.join(REPO, "engine", "build", "vm_interp.bc")
            vm_exe = os.path.join(t, "prot")
            subprocess.run([_clang(), out_ll, vm_bc, "-o", vm_exe],
                           check=True, capture_output=True)
            prot = subprocess.run([vm_exe], capture_output=True, text=True).stdout
            self.assertEqual(base, prot)                    # 功能保持（FR-C8）

    def test_r2_combo_protection(self):
        """组合防护（虚拟化 + 白盒 + 对抗诱导）功能测试通过（R2 出口）。"""
        with tempfile.TemporaryDirectory() as out:
            manifest = scan(SAMPLES)
            policy = plan(manifest, {"max_overhead": 0.5}, seed=7)
            policy["_run_id"] = manifest["run_id"]
            meta = protect(policy, [P0_SECRET], out, root=SAMPLES, seed=7)
            self.assertIn("virtualize", meta["strategies"])
            self.assertTrue(meta.get("wbc"))
            self.assertTrue(meta.get("adversarial"))
            report = verify(out)
            self.assertTrue(report["functional_pass"], report)
            self.assertTrue(report["overall_pass"], report)
            common.validate(report, "verification_report.schema.json")

    def test_func_split_and_noise(self):
        """FR-C4 函数边界扰动 / FR-C5 数据流噪声：生效且功能保持。"""
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
            env["ANTI_REA_STRATEGIES"] = "func_split,noise"
            env["ANTI_REA_SEED"] = "4"
            out = os.path.join(t, "prot.ll")
            subprocess.run([opt, "-load-pass-plugin=" + plug,
                            "-passes=reg2mem,anti-rea", ir, "-S", "-o", out],
                           check=True, capture_output=True, env=env)
            with open(out, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("noise.k", text)                       # FR-C5
            with open(ir, encoding="utf-8") as fh:
                base = fh.read()
            self.assertGreater(text.count("\ndefine "), base.count("\ndefine "))  # FR-C4

            # 功能保持：clang 插件路径编译并运行，与基线一致
            def build(src):
                exe = os.path.join(t, os.path.basename(src) + ".exe")
                subprocess.run([_clang(), "-O0", src, "-o", exe],
                               check=True, capture_output=True)
                return subprocess.run([exe], capture_output=True, text=True).stdout

            env2 = dict(os.environ)
            env2["ANTI_REA_WHITELIST"] = "*"
            env2["ANTI_REA_STRATEGIES"] = "func_split,noise"
            env2["ANTI_REA_SEED"] = "4"
            prot_exe = os.path.join(t, "prot_exe")
            subprocess.run([_clang(), "-O0", "-fpass-plugin=" + plug, HELLO,
                            "-o", prot_exe], check=True, capture_output=True, env=env2)
            base_out = build(HELLO)
            prot_out = subprocess.run([prot_exe], capture_output=True, text=True).stdout
            self.assertEqual(base_out, prot_out)

    def test_anchor_removal(self):
        """字符串加密 + 标识符重命名：移除 REA 的明文串/符号锚点，且功能保持。"""
        opt = _opt()
        if not opt:
            self.skipTest("无 opt")
        plug = _find_plugin()
        with tempfile.TemporaryDirectory() as t:
            ir = os.path.join(t, "h.ll")
            subprocess.run([_clang(), "-O1", "-S", "-emit-llvm", HELLO, "-o", ir],
                           check=True, capture_output=True)
            env = dict(os.environ)
            env["ANTI_REA_WHITELIST"] = "*"
            env["ANTI_REA_STRATEGIES"] = "string_encrypt,rename"
            env["ANTI_REA_SEED"] = "5"

            # 字符串加密：IR 层出现编码全局与解码异或；明文格式串消失
            se = os.path.join(t, "se.ll")
            subprocess.run([opt, "-load-pass-plugin=" + plug,
                            "-passes=string-encrypt", ir, "-S", "-o", se],
                           check=True, capture_output=True, env=env)
            with open(se, encoding="utf-8") as fh:
                setext = fh.read()
            self.assertIn("enc_", setext)          # 编码全局取不透明名（不带原表名）
            self.assertNotIn(".enc", setext)        # 不再用 "<原名>.enc"（避免后缀漏名）
            self.assertIn("xor i8", setext)
            self.assertNotIn('%d %d %d', setext)

            # 标识符重命名：白名单函数名不再出现（默认 ANTI_REA_RENAME_EXTERNAL=1，
            # 单 TU/整程序场景连外部链接函数一并抹名）
            rn = os.path.join(t, "rn.ll")
            subprocess.run([opt, "-load-pass-plugin=" + plug,
                            "-passes=ident-rename", ir, "-S", "-o", rn],
                           check=True, capture_output=True, env=env)
            with open(rn, encoding="utf-8") as fh:
                rntext = fh.read()
            self.assertNotIn("@secret_mix", rntext)
            self.assertIn("@sub_", rntext)

            # 功能保持 + 二进制锚点移除
            def build(src, extra):
                exe = os.path.join(t, "x." + str(len(os.listdir(t))))
                subprocess.run([_clang(), "-O1", "-fpass-plugin=" + plug, src, "-o", exe],
                               check=True, capture_output=True, env=extra)
                return exe

            prot = build(HELLO, env)
            base = build(HELLO, dict(os.environ))
            out_b = subprocess.run([base], capture_output=True, text=True).stdout
            out_p = subprocess.run([prot], capture_output=True, text=True).stdout
            self.assertEqual(out_b, out_p)
            strs = subprocess.run(["strings", prot], capture_output=True, text=True).stdout
            self.assertNotIn("%d %d %d", strs)
            nm = subprocess.run(["nm", prot], capture_output=True, text=True).stdout
            self.assertNotIn("secret_mix", nm)

    def test_rename_external_opt_out(self):
        """ANTI_REA_RENAME_EXTERNAL=0：外部链接函数保留（多 TU 链接安全），static 仍改名。

        protect 对多源（多编译单元）构建会自动置 0，避免他 TU 按原名引用导致
        undefined reference；本用例在引擎层直接验证该开关语义。
        """
        opt = _opt()
        if not opt:
            self.skipTest("无 opt")
        plug = _find_plugin()
        with tempfile.TemporaryDirectory() as t:
            src = os.path.join(t, "mix.c")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write("static int secret_mix(int x) { return x ^ 0x5a; }\n"
                         "int secret_api(int x) { return secret_mix(x) + 1; }\n"
                         "int main(void) { return secret_api(3); }\n")
            ir = os.path.join(t, "mix.ll")
            # 用 -O0 避免 static 函数被内联消除
            subprocess.run([_clang(), "-O0", "-S", "-emit-llvm", src, "-o", ir],
                           check=True, capture_output=True)
            env = dict(os.environ)
            env["ANTI_REA_WHITELIST"] = "*"
            env["ANTI_REA_STRATEGIES"] = "rename"
            env["ANTI_REA_SEED"] = "5"
            env["ANTI_REA_RENAME_EXTERNAL"] = "0"
            rn = os.path.join(t, "rn.ll")
            subprocess.run([opt, "-load-pass-plugin=" + plug,
                            "-passes=ident-rename", ir, "-S", "-o", rn],
                           check=True, capture_output=True, env=env)
            with open(rn, encoding="utf-8") as fh:
                txt = fh.read()
            self.assertNotIn("@secret_mix", txt)   # static -> 改名
            self.assertIn("@sub_", txt)
            self.assertIn("@secret_api", txt)      # 外部链接 -> 保留
            self.assertIn("@main", txt)            # main -> 保留

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
