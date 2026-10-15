/* S4 差分 fuzz 目标：从 argv 读取整数序列，输出确定性的聚合结果。
 * 敏感函数名（secret_accumulate）便于扫描器识别为受保护资产并入白名单，
 * 使 10^5 级随机输入能真正覆盖被变换的代码路径（NFR-03 / FR-E1）。
 * 仅用于测试。 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int secret_accumulate(uint32_t seed, int v)
{
    uint32_t x = seed ^ (uint32_t)v;
    x = x * 0x9e3779b1u;
    x ^= x >> 15;
    x += 0x7f4a7c15u;
    x ^= x << 13;
    x += x >> 7;
    return (int)x;
}

int classify(int x)
{
    if (x > 100) return 2;
    if (x > 0) return 1;
    if (x == 0) return 0;
    return -1;
}

int main(int argc, char **argv)
{
    uint32_t acc = 0x1234abcdu;
    int last = 0;
    for (int i = 1; i < argc; i++) {
        int v = (int)strtol(argv[i], NULL, 10);
        last = secret_accumulate(acc, v);
        acc = (uint32_t)last ^ (acc << 1);
    }
    printf("%08x %d\n", acc, classify(last));
    return 0;
}
