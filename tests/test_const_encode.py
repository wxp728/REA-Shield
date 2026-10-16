"""常数编码（string_encryption 下的常量池）测试。

覆盖三件事：
1. 算法指纹立即数（SM4 FK / SM3 IV 这类 `#define` 常量）在产物里消失，且语义不变；
2. **常量索引**访问的常量表（GEP 会被 LLVM 折叠成 ConstantExpr）仍能正确解密——
   这是「常量池按索引取值」曾把索引丢掉、恒读元素 0 的回归点；
3. **常量向量**操作数（clang -O2 会把 SM3 IV 的 8 个连续常量存储合并成 `<4 x i32>`
   常量向量）同样要进池——只认 ConstantInt 的旧实现会把这种形态整片漏掉。
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.transform import protect, _clang, _find_plugin  # noqa: E402

SRC = """\
#include <stdint.h>
#include <stdio.h>

/* 常量表：既被「变量索引」访问（真实 GEP 指令），也被「常量索引」访问（折叠成 ConstantExpr） */
static const uint32_t ktab[4] = { 0x11111111u, 0x22222222u, 0x33333333u, 0x44444444u };

/* 常量索引访问 */
static uint32_t pick_const(void) { return ktab[2] ^ 0xa3b1bac6u; }

/* SM3 IV 形态：常量出现在「非二元运算」的使用点（volatile 存储，避免被折叠掉） */
static volatile uint32_t sink;
static void iv_store(void) { sink = 0x7380166fu; }

uint32_t secret_mix(uint32_t x)
{
    return (x ^ 0xa3b1bac6u) + (x ^ 0x56aa3350u) + ktab[x & 3] + pick_const();
}

int main(void)
{
    uint32_t acc = 0;
    unsigned i;
    iv_store();
    for (i = 0; i < 8; i++)
        acc = secret_mix(acc + i * 0x1234567u);
    printf("%08x\\n", acc + sink);
    return 0;
}
"""

# SM4 FK0 / FK1（小端字节序）——算法指纹
FK0 = b"\xc6\xba\xb1\xa3"
FK1 = b"\x50\x33\xaa\x56"
SM3_IV0 = b"\x6f\x16\x80\x73"

# 常量向量形态：`-O2` 下 clang 把 SM3 IV 的连续常量存储 SLP 合成 `<4 x i32>` 常量向量。
# 这里用显式 vector 类型在 `-O1` 稳定复现同一 IR 形态（clang -O1 的 SLP 未开启）。
SRC_VEC = """\
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef uint32_t v4u __attribute__((vector_size(16)));

void iv_store(v4u *p)
{
    v4u v = { 0x7380166fu, 0x4914b2b9u, 0x172442d7u, 0xda8a0600u };
    *p = v;
}

static uint32_t mix(v4u v)
{
    v4u k = { 0xa3b1bac6u, 0x56aa3350u, 0x677d9197u, 0xb27022dcu };
    v = v + k;
    return v[0] ^ v[1] ^ v[2] ^ v[3];
}

int main(void)
{
    v4u *p = (v4u *)malloc(16);
    uint32_t acc;
    iv_store(p);
    acc = mix(*p);
    printf("%08x\\n", acc);
    free(p);
    return 0;
}
"""


def _have_toolchain() -> bool:
    try:
        _find_plugin()
        _clang()
        return True
    except Exception:
        return False


@unittest.skipUnless(_have_toolchain(), "需要已构建的 engine 插件与 clang")
class TestConstEncode(unittest.TestCase):
    def _build(self, src_text=SRC):
        d = tempfile.mkdtemp()
        src = os.path.join(d, "c.c")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(src_text)
        base = os.path.join(d, "base")
        subprocess.run([_clang(), "-O1", src, "-o", base], check=True,
                       capture_output=True)
        policy = {"seed": 7, "assets": [{"path": "c.c", "sensitivity": "P0",
                  "strategies": ["string_encryption", "identifier_renaming"]}]}
        out = os.path.join(d, "out")
        protect(policy, [src], out, root=d, seed=7, protect_all=True)
        prot = os.path.join(out, "artifacts", "protected")
        self.assertTrue(os.path.exists(prot), prot)
        return d, base, prot

    def test_semantics_preserved(self):
        _, base, prot = self._build()
        rb = subprocess.run([base], capture_output=True, text=True)
        rp = subprocess.run([prot], capture_output=True, text=True)
        self.assertEqual(rp.returncode, 0, rp.stderr)
        self.assertEqual(rp.stdout, rb.stdout)

    def test_fingerprints_hidden(self):
        _, _, prot = self._build()
        with open(prot, "rb") as fh:
            blob = fh.read()
        for name, pat in (("SM4 FK0", FK0), ("SM4 FK1", FK1), ("SM3 IV0", SM3_IV0)):
            self.assertEqual(blob.count(pat), 0, "%s 仍以明文出现在产物中" % name)

    def test_vector_constant_hidden(self):
        """常量向量（<4 x i32>）操作数同样入池（-O2 下 SM3 IV 的实际形态）。"""
        _, base, prot = self._build(SRC_VEC)
        with open(base, "rb") as fh:
            self.assertGreater(fh.read().count(SM3_IV0), 0,
                               "基线未呈现常量向量形态，本用例失去意义")
        with open(prot, "rb") as fh:
            self.assertEqual(fh.read().count(SM3_IV0), 0,
                             "SM3 IV 常量向量仍以明文出现在产物中")
        rb = subprocess.run([base], capture_output=True, text=True)
        rp = subprocess.run([prot], capture_output=True, text=True)
        self.assertEqual(rp.returncode, 0, rp.stderr)
        self.assertEqual(rp.stdout, rb.stdout)


if __name__ == "__main__":
    unittest.main()
