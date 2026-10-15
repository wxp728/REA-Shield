/* R2 样例：含硬编码密钥的高敏资产（P0），用于虚拟化 / 白盒 / 对抗诱导。
 * 注意：仅用于测试，密钥为演示用固定值，非真实凭据。
 * 密钥以整型字面量展开（避免全局数组访问），使目标函数对 VM v0.1 可虚拟化。 */
#include <stdio.h>

int secret_schedule(int x)
{
    /* 硬编码密钥字节（0x3b 0x7e 0x15 0x16 ...） */
    int k0 = 0x3b, k1 = 0x7e, k2 = 0x15, k3 = 0x16;
    int k4 = 0x28, k5 = 0xae, k6 = 0xd2, k7 = 0xa6;
    int y = x ^ k0;
    y = (y * 0x1b) + k1;
    y = y ^ k2;
    y = (y << 1) ^ k3;
    y = y + k4 - k5 + k6 - k7;
    return y;
}

int secret_roundtrip(int x)
{
    return secret_schedule(x) - secret_schedule(x ^ 0x20);
}

int main(void)
{
    printf("%d %d %d\n", secret_schedule(3), secret_roundtrip(5), secret_schedule(200));
    return 0;
}
