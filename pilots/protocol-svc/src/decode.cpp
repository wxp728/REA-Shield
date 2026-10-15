/* 试点工程 2（C++ / 直接构建 / P1）：协议帧解析 + 秘密帧解码。
 * 刻意不使用 STL，避免交叉/裸链接依赖；仅演示用途。 */
#include <cstdio>
#include <cstdint>

extern "C" int secret_decode_frame(const unsigned char *buf, int len)
{
    uint32_t acc = 0xa5a5a5a5u;
    for (int i = 0; i < len; ++i) {
        acc ^= buf[i];
        acc = (acc << 5) | (acc >> 27);
        acc += 0x9e3779b9u;
    }
    return (int)(acc & 0x7fffffff);
}

int derive_frame(const char *s)
{
    int n = 0;
    for (const char *p = s; *p; ++p) {
        n = n * 31 + (unsigned char)*p;
    }
    return n & 0xffff;
}

int main(void)
{
    const unsigned char frame[] = {0x10, 0x20, 0x30, 0x40, 0x50};
    std::printf("%d %d\n", secret_decode_frame(frame, 5),
                derive_frame("FRAME-42"));
    return 0;
}
