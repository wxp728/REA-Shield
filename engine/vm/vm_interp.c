/*
 * Anti-REA 自定义虚拟机 —— 解释器（R2 v0.1）
 * 设计：docs/design/ddd/dd-04-virtualization.md §4/§5
 *
 * 编译为 LLVM bitcode，与目标一起链接：
 *   clang -O2 -emit-llvm -c engine/vm/vm_interp.c -o engine/build/vm_interp.bc
 *
 * 入口（由变换 pass 生成调用）：
 *   uint64_t anti_rea_vm_run(const unsigned char *code, long code_len,
 *                            const uint64_t *args, int nargs,
 *                            uint32_t seed, uint32_t nregs);
 */
#include <stdint.h>
#include <stddef.h>

#include "vm_isa.h"

static inline uint16_t rd16(const unsigned char *c, size_t *p)
{
    uint16_t v;
    __builtin_memcpy(&v, c + *p, 2);
    *p += 2;
    return v;
}
static inline uint32_t rd32(const unsigned char *c, size_t *p)
{
    uint32_t v;
    __builtin_memcpy(&v, c + *p, 4);
    *p += 4;
    return v;
}
static inline uint64_t rd64(const unsigned char *c, size_t *p)
{
    uint64_t v;
    __builtin_memcpy(&v, c + *p, 8);
    *p += 8;
    return v;
}

__attribute__((noinline))
uint64_t anti_rea_vm_run(const unsigned char *code, long code_len,
                         const uint64_t *args, int nargs,
                         uint32_t seed, uint32_t nregs)
{
    unsigned char dec[32];
    uint64_t regs[ANTI_REA_VM_NREG];
    uint32_t i;
    size_t pc = 0;

    anti_rea_vm_tables(seed, (unsigned char[32]){0}, dec);

    if (nregs > ANTI_REA_VM_NREG) nregs = ANTI_REA_VM_NREG;
    for (i = 0; i < nregs; i++) regs[i] = 0;
    for (i = 0; i < (uint32_t)nargs && i < nregs; i++) regs[i] = args[i];

    for (;;) {
        unsigned char op;
        if (pc >= (size_t)code_len) return 0;
        op = dec[code[pc++]];
        switch (op) {
        case OP_NOP:
            break;
        case OP_MOVI: {
            uint16_t d = rd16(code, &pc);
            uint64_t imm = rd64(code, &pc);
            regs[d] = imm;
            break;
        }
        case OP_MOVE: {
            uint16_t d = rd16(code, &pc), a = rd16(code, &pc);
            regs[d] = regs[a];
            break;
        }
        case OP_ADD: case OP_SUB: case OP_MUL: case OP_AND:
        case OP_OR:  case OP_XOR: {
            uint16_t d = rd16(code, &pc), a = rd16(code, &pc), b = rd16(code, &pc);
            uint64_t x = regs[a], y = regs[b];
            uint64_t r = 0;
            switch (op) {
            case OP_ADD: r = x + y; break;
            case OP_SUB: r = x - y; break;
            case OP_MUL: r = x * y; break;
            case OP_AND: r = x & y; break;
            case OP_OR:  r = x | y; break;
            case OP_XOR: r = x ^ y; break;
            }
            regs[d] = r;
            break;
        }
        case OP_SHL: case OP_SHR: case OP_SRA: {
            uint16_t d = rd16(code, &pc), a = rd16(code, &pc);
            unsigned char sh = code[pc++];
            uint64_t x = regs[a];
            if (op == OP_SHL) regs[d] = x << (sh & 63);
            else if (op == OP_SHR) regs[d] = (uint64_t)(x >> (sh & 63));
            else regs[d] = (uint64_t)((int64_t)x >> (sh & 63));
            break;
        }
        case OP_SHLV: case OP_SHRV: case OP_SRAV: {
            uint16_t d = rd16(code, &pc), a = rd16(code, &pc), b = rd16(code, &pc);
            unsigned char sh = (unsigned char)(regs[b] & 63);
            uint64_t x = regs[a];
            if (op == OP_SHLV) regs[d] = x << sh;
            else if (op == OP_SHRV) regs[d] = (uint64_t)(x >> sh);
            else regs[d] = (uint64_t)((int64_t)x >> sh);
            break;
        }
        case OP_CMPEQ: case OP_CMPNE: case OP_CMPSLT:
        case OP_CMPSLE: case OP_CMPSGT: case OP_CMPSGE: {
            uint16_t d = rd16(code, &pc), a = rd16(code, &pc), b = rd16(code, &pc);
            uint64_t x = regs[a], y = regs[b];
            int64_t sx = (int64_t)x, sy = (int64_t)y;
            uint64_t r = 0;
            switch (op) {
            case OP_CMPEQ: r = (x == y); break;
            case OP_CMPNE: r = (x != y); break;
            case OP_CMPSLT: r = (sx < sy); break;
            case OP_CMPSLE: r = (sx <= sy); break;
            case OP_CMPSGT: r = (sx > sy); break;
            case OP_CMPSGE: r = (sx >= sy); break;
            }
            regs[d] = r;
            break;
        }
        case OP_JMP: {
            uint32_t t = rd32(code, &pc);
            pc = t;
            break;
        }
        case OP_JZ: case OP_JNZ: {
            uint16_t c = rd16(code, &pc);
            uint32_t t = rd32(code, &pc);
            int cond = (regs[c] != 0);
            if ((op == OP_JZ && !cond) || (op == OP_JNZ && cond)) pc = t;
            break;
        }
        case OP_RET: {
            uint16_t s = rd16(code, &pc);
            return regs[s];
        }
        case OP_HALT:
        default:
            return 0;
        }
    }
}
