/* 试点工程 1（C / CMake / P0）：许可校验 + 密钥调度。
 * 仅演示用；密钥为固定演示值，非真实凭据。 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

int secret_key_schedule(int seed)
{
    int k0 = 0x51, k1 = 0x2f, k2 = 0x9c, k3 = 0x04;
    int y = seed ^ k0;
    y = (y * 0x2b) + k1;
    y = y ^ k2;
    y = (y << 1) ^ k3;
    return y;
}

int verify_license(const char *token)
{
    unsigned acc = 0x811c9dc5u;
    for (const char *p = token; *p; ++p) {
        acc ^= (unsigned char)*p;
        acc *= 0x01000193u;
    }
    return (int)(acc % 97u) + 1;
}

int main(void)
{
    printf("%d %d\n", secret_key_schedule(7), verify_license("DEMO-1234"));
    return 0;
}
