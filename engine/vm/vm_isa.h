/*
 * REA-Shield 自定义虚拟机 —— ISA 与随机化表（pass 与解释器共享的唯一事实来源）
 * 设计：docs/design/ddd/dd-04-virtualization.md §3
 *
 * 机器模型：
 *   - 寄存器文件 regs[0..NREG-1]（64-bit）；参数置入 regs[0..nargs-1]
 *   - 变长字节码：[opcode:1B][operands...]
 *   - 每实例 opcode 映射随机化：encoded = perm_seed(real)
 *
 * 说明（v0.1 边界）：仅整型；无浮点/聚合/指针运算；不支持函数调用
 *   （不支持者由 pass 跳过并回退 IR 变换）。
 */
#ifndef ANTI_REA_VM_ISA_H
#define ANTI_REA_VM_ISA_H

#include <stdint.h>

#define ANTI_REA_VM_NREG 256

enum {
    OP_NOP = 0,
    OP_MOVI,    /* dst:u16 imm:u64 */
    OP_MOVE,    /* dst:u16 src:u16 */
    OP_ADD,     /* dst:u16 a:u16 b:u16 */
    OP_SUB,
    OP_MUL,
    OP_AND,
    OP_OR,
    OP_XOR,
    OP_SHL,     /* dst:u16 a:u16 imm:u8 */
    OP_SHR,     /* 逻辑右移 */
    OP_SRA,     /* 算术右移 */
    OP_CMPEQ,   /* dst = (a == b) */
    OP_CMPNE,
    OP_CMPSLT,
    OP_CMPSLE,
    OP_CMPSGT,
    OP_CMPSGE,
    OP_JMP,     /* target:u32 */
    OP_JZ,      /* cond:u16 target:u32 */
    OP_JNZ,     /* cond:u16 target:u32 */
    OP_RET,     /* src:u16 */
    OP_HALT,
    OP_SHLV,    /* dst:u16 a:u16 b:u16（b 为移位量寄存器） */
    OP_SHRV,
    OP_SRAV,
    OP__COUNT = 32
};

static inline uint32_t anti_rea_vm_xs32(uint32_t *s)
{
    uint32_t x = *s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *s = x;
    return x;
}

/* 由 seed 生成 opcode 编码/解码表（32 项双射） */
static inline void anti_rea_vm_tables(uint32_t seed, unsigned char enc[32],
                                      unsigned char dec[32])
{
    unsigned char perm[32];
    uint32_t s = seed ? seed : 0x9e3779b9u;
    int i;
    for (i = 0; i < 32; i++) perm[i] = (unsigned char)i;
    for (i = 31; i > 0; i--) {
        uint32_t j = anti_rea_vm_xs32(&s) % (uint32_t)(i + 1);
        unsigned char t = perm[i];
        perm[i] = perm[j];
        perm[j] = t;
    }
    for (i = 0; i < 32; i++) {
        enc[i] = perm[i];
        dec[perm[i]] = (unsigned char)i;
    }
}

#endif /* ANTI_REA_VM_ISA_H */
