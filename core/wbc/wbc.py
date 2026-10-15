"""白盒密码模块（WBC v0.1，FR-C10）。

设计：docs/design/ddd/dd-06-wbc.md（基于 PoC-4 的轻量查找表编码）
- 生成自包含的 AES-128 白盒实现（S-box 运行期生成，不硬编码）；
- 密钥以两份额存放，运行时重构、用后清零（二进制中无明文密钥常量）；
- 与标准 AES-128 输出一致（加解密自洽）。

威胁模型边界见 DD-06 §5：目标是提高密钥/算法提取成本，不承诺抵抗 DCA/侧信道。
"""
from __future__ import annotations

import hashlib
import os
import random
import subprocess
from string import Template

# 自包含白盒 AES-128 C 实现（$SHARE_A/$SHARE_B/$SEED 由生成器填入）
_C_TEMPLATE = Template(r'''/*
 * Anti-REA 白盒密码实现（AES-128，自动生成，勿手改）
 * 关联：FR-C10 / docs/design/ddd/dd-06-wbc.md / 移植自 PoC-4
 * - S-box 运行期由 GF(2^8) 逆 + 仿射变换生成（不硬编码明文 S-box）；
 * - SubBytes 经编码查找表 out_enc[sbox[in_enc[i]]] 承载；
 * - 密钥以两份额存放，运行时重构、用后清零；二进制中无明文密钥常量。
 */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static uint8_t gf_mul(uint8_t a, uint8_t b)
{
    uint8_t p = 0;
    for (int i = 0; i < 8; i++) {
        if (b & 1) p ^= a;
        uint8_t hi = a & 0x80;
        a <<= 1;
        if (hi) a ^= 0x1b;
        b >>= 1;
    }
    return p;
}
static uint8_t rotl8(uint8_t x, int n) { return (uint8_t)((x << n) | (x >> (8 - n))); }

static uint8_t g_sbox[256], g_inv_sbox[256];
static void gen_sbox(void)
{
    uint8_t inv[256];
    inv[0] = 0;
    for (int i = 1; i < 256; i++)
        for (int j = 1; j < 256; j++)
            if (gf_mul((uint8_t)i, (uint8_t)j) == 1) { inv[i] = (uint8_t)j; break; }
    for (int i = 0; i < 256; i++) {
        uint8_t x = inv[i];
        g_sbox[i] = (uint8_t)(x ^ rotl8(x, 1) ^ rotl8(x, 2) ^ rotl8(x, 3) ^ rotl8(x, 4) ^ 0x63);
    }
    for (int i = 0; i < 256; i++) g_inv_sbox[g_sbox[i]] = (uint8_t)i;
}

static void key_expand(const uint8_t key[16], uint8_t rk[176])
{
    memcpy(rk, key, 16);
    uint8_t rcon = 1;
    for (int i = 16; i < 176; i += 4) {
        uint8_t t[4];
        memcpy(t, rk + i - 4, 4);
        if (i % 16 == 0) {
            uint8_t tmp = t[0]; t[0] = t[1]; t[1] = t[2]; t[2] = t[3]; t[3] = tmp;
            for (int j = 0; j < 4; j++) t[j] = g_sbox[t[j]];
            t[0] ^= rcon; rcon = gf_mul(rcon, 2);
        }
        for (int j = 0; j < 4; j++) rk[i + j] = (uint8_t)(rk[i - 16 + j] ^ t[j]);
    }
}
static void add_round_key(uint8_t s[16], const uint8_t *rk)
{ for (int i = 0; i < 16; i++) s[i] ^= rk[i]; }
static void shift_rows(uint8_t s[16])
{
    uint8_t t;
    t = s[1]; s[1] = s[5]; s[5] = s[9]; s[9] = s[13]; s[13] = t;
    t = s[2]; s[2] = s[10]; s[10] = t; t = s[6]; s[6] = s[14]; s[14] = t;
    t = s[3]; s[3] = s[15]; s[15] = s[11]; s[11] = s[7]; s[7] = t;
}
static void inv_shift_rows(uint8_t s[16])
{
    uint8_t t;
    t = s[13]; s[13] = s[9]; s[9] = s[5]; s[5] = s[1]; s[1] = t;
    t = s[2]; s[2] = s[10]; s[10] = t; t = s[6]; s[6] = s[14]; s[14] = t;
    t = s[7]; s[7] = s[11]; s[11] = s[15]; s[15] = s[3]; s[3] = t;
}
static void mix_columns(uint8_t s[16])
{
    for (int c = 0; c < 4; c++) {
        uint8_t *p = s + 4 * c;
        uint8_t a0 = p[0], a1 = p[1], a2 = p[2], a3 = p[3];
        p[0] = (uint8_t)(gf_mul(a0, 2) ^ gf_mul(a1, 3) ^ a2 ^ a3);
        p[1] = (uint8_t)(a0 ^ gf_mul(a1, 2) ^ gf_mul(a2, 3) ^ a3);
        p[2] = (uint8_t)(a0 ^ a1 ^ gf_mul(a2, 2) ^ gf_mul(a3, 3));
        p[3] = (uint8_t)(gf_mul(a0, 3) ^ a1 ^ a2 ^ gf_mul(a3, 2));
    }
}
static void inv_mix_columns(uint8_t s[16])
{
    for (int c = 0; c < 4; c++) {
        uint8_t *p = s + 4 * c;
        uint8_t a0 = p[0], a1 = p[1], a2 = p[2], a3 = p[3];
        p[0] = (uint8_t)(gf_mul(a0, 14) ^ gf_mul(a1, 11) ^ gf_mul(a2, 13) ^ gf_mul(a3, 9));
        p[1] = (uint8_t)(gf_mul(a0, 9) ^ gf_mul(a1, 14) ^ gf_mul(a2, 11) ^ gf_mul(a3, 13));
        p[2] = (uint8_t)(gf_mul(a0, 13) ^ gf_mul(a1, 9) ^ gf_mul(a2, 14) ^ gf_mul(a3, 11));
        p[3] = (uint8_t)(gf_mul(a0, 11) ^ gf_mul(a1, 13) ^ gf_mul(a2, 9) ^ gf_mul(a3, 14));
    }
}

/* ---- 编码查找表 ---- */
static uint8_t g_in_enc[256], g_out_enc[256], g_etab[256];
static uint8_t g_in_enc_inv[256], g_out_enc_inv[256];
static uint8_t g_in_enc2[256], g_out_enc2[256], g_etab_inv[256];
static uint8_t g_in_enc2_inv[256], g_out_enc2_inv[256];

static uint32_t g_rng;
static uint32_t xorshift32(void)
{
    uint32_t x = g_rng;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    g_rng = x;
    return x;
}
static void shuffle(uint8_t *t, int n)
{
    for (int i = n - 1; i > 0; i--) {
        int j = (int)(xorshift32() % (uint32_t)(i + 1));
        uint8_t tmp = t[i]; t[i] = t[j]; t[j] = tmp;
    }
}
static void build_wbc_tables(uint32_t seed)
{
    g_rng = seed ? seed : 0x9e3779b9u;
    for (int i = 0; i < 256; i++) {
        g_in_enc[i] = (uint8_t)i; g_out_enc[i] = (uint8_t)i;
        g_in_enc2[i] = (uint8_t)i; g_out_enc2[i] = (uint8_t)i;
    }
    shuffle(g_in_enc, 256);  shuffle(g_out_enc, 256);
    shuffle(g_in_enc2, 256); shuffle(g_out_enc2, 256);
    for (int i = 0; i < 256; i++) {
        g_in_enc_inv[g_in_enc[i]] = (uint8_t)i;
        g_out_enc_inv[g_out_enc[i]] = (uint8_t)i;
        g_etab[i] = g_out_enc[g_sbox[g_in_enc[i]]];
        g_in_enc2_inv[g_in_enc2[i]] = (uint8_t)i;
        g_out_enc2_inv[g_out_enc2[i]] = (uint8_t)i;
        g_etab_inv[i] = g_out_enc2[g_inv_sbox[g_in_enc2[i]]];
    }
}
static void wbc_sub_bytes(uint8_t s[16])
{ for (int i = 0; i < 16; i++) s[i] = g_out_enc_inv[g_etab[g_in_enc_inv[s[i]]]]; }
static void wbc_inv_sub_bytes(uint8_t s[16])
{ for (int i = 0; i < 16; i++) s[i] = g_out_enc2_inv[g_etab_inv[g_in_enc2_inv[s[i]]]]; }

/* ---- 密钥份额：真实密钥 = share_a ^ share_b（无明文密钥常量） ---- */
static const uint8_t g_share_a[16] = { $SHARE_A };
static const uint8_t g_share_b[16] = { $SHARE_B };

static void secure_zero(void *p, size_t n)
{ volatile uint8_t *v = (volatile uint8_t *)p; while (n--) *v++ = 0; }

static void wbc_key(uint8_t key[16])
{ for (int i = 0; i < 16; i++) key[i] = (uint8_t)(g_share_a[i] ^ g_share_b[i]); }

static void wbc_encrypt_block(const uint8_t in[16], uint8_t out[16])
{
    uint8_t key[16], rk[176], s[16];
    wbc_key(key);
    key_expand(key, rk);
    memcpy(s, in, 16);
    add_round_key(s, rk);
    for (int r = 1; r <= 9; r++) {
        wbc_sub_bytes(s); shift_rows(s); mix_columns(s); add_round_key(s, rk + 16 * r);
    }
    wbc_sub_bytes(s); shift_rows(s); add_round_key(s, rk + 160);
    memcpy(out, s, 16);
    secure_zero(key, sizeof key); secure_zero(rk, sizeof rk);
}
static void wbc_decrypt_block(const uint8_t in[16], uint8_t out[16])
{
    uint8_t key[16], rk[176], s[16];
    wbc_key(key);
    key_expand(key, rk);
    memcpy(s, in, 16);
    add_round_key(s, rk + 160);
    for (int r = 9; r >= 1; r--) {
        inv_shift_rows(s); wbc_inv_sub_bytes(s); add_round_key(s, rk + 16 * r); inv_mix_columns(s);
    }
    inv_shift_rows(s); wbc_inv_sub_bytes(s); add_round_key(s, rk);
    memcpy(out, s, 16);
    secure_zero(key, sizeof key); secure_zero(rk, sizeof rk);
}

int main(void)
{
    gen_sbox();
    build_wbc_tables($SEED);

    int ok_rt = 1, ok_det = 1;
    srand(20261015u);
    uint8_t pt[16], ct1[16], ct2[16], back[16];
    for (int t = 0; t < 2000; t++) {
        for (int i = 0; i < 16; i++) pt[i] = (uint8_t)(rand() & 0xff);
        wbc_encrypt_block(pt, ct1);
        wbc_decrypt_block(ct1, back);
        if (memcmp(pt, back, 16) != 0) { ok_rt = 0; break; }
    }
    for (int i = 0; i < 16; i++) pt[i] = (uint8_t)i;
    wbc_encrypt_block(pt, ct1);
    wbc_encrypt_block(pt, ct2);
    ok_det = (memcmp(ct1, ct2, 16) == 0);

    printf("WBC roundtrip (2000 blocks): %s\n", ok_rt ? "PASS" : "FAIL");
    printf("WBC determinism            : %s\n", ok_det ? "PASS" : "FAIL");
    return (ok_rt && ok_det) ? 0 : 1;
}
''')


def _emit_array(b: bytes) -> str:
    return ", ".join("0x%02x" % x for x in b)


def derive_key(seed: int, salt: str = "anti-rea-wbc") -> bytes:
    """由 seed 确定性派生 16 字节密钥（可复现，NFR-04）。"""
    return hashlib.sha256(("%s-%d" % (salt, seed)).encode()).digest()[:16]


def generate(out_dir: str, key: bytes | None = None, seed: int = 0,
             alg: str = "aes-128") -> dict:
    """生成白盒 AES-128 实现，返回元数据。"""
    os.makedirs(out_dir, exist_ok=True)
    if alg != "aes-128":
        raise ValueError("E_INVALID_INPUT: WBC v0.1 仅支持 aes-128")
    if key is None:
        key = derive_key(seed)
    key = bytes(key)
    if len(key) != 16:
        raise ValueError("E_INVALID_INPUT: AES-128 密钥须为 16 字节")

    rnd = random.Random(seed ^ 0xA5A5A5A5)
    share_b = bytes(rnd.randrange(256) for _ in range(16))
    share_a = bytes(a ^ b for a, b in zip(key, share_b))

    src = _C_TEMPLATE.substitute(SHARE_A=_emit_array(share_a),
                                 SHARE_B=_emit_array(share_b),
                                 SEED=(seed & 0xffffffff))
    path = os.path.join(out_dir, "wbc_aes.c")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(src)
    return {"path": path, "alg": alg, "seed": seed, "key_len": len(key)}


def check_no_key_constant(path: str, key: bytes) -> bool:
    """静态检查：目标二进制中不出现明文密钥常量（FR-C10）。"""
    with open(path, "rb") as fh:
        data = fh.read()
    return bytes(key) not in data


def selftest(out_dir: str, clang: str | None = None) -> dict:
    """编译并运行生成的白盒实现，返回 {pass, output, exe}。"""
    from ..transform import _clang
    clang = clang or _clang()
    src = os.path.join(out_dir, "wbc_aes.c")
    exe = os.path.join(out_dir, "wbc_selftest")
    subprocess.run([clang, "-O1", src, "-o", exe], check=True, capture_output=True)
    p = subprocess.run([exe], capture_output=True, text=True)
    return {"pass": p.returncode == 0, "output": p.stdout, "exe": exe}
