/* Anti-REA quickstart 示例 —— 一个"你自己的"小项目，含敏感资产。
 *
 * 仅用于演示 Anti-REA 的 scan -> plan -> protect -> verify 流程。
 * 请只对你拥有或有权修改的代码使用本工具链。
 */
#include <stdio.h>
#include <string.h>

/* 硬编码密钥（会被扫描器识别为 P0 secret 资产） */
static const char *MASTER_KEY = "S3cr3t-M4ster-K3y-9f8a7b6c5d4e3f2a1b0c";

/* 许可证校验（license_check，敏感逻辑） */
static int verify_license(const char *input)
{
    return strcmp(input, MASTER_KEY) == 0;
}

/* 校验和算法（algorithm） */
static unsigned compute_checksum(const char *s)
{
    unsigned h = 2166136261u; /* FNV-1a */
    while (*s) {
        h = (h ^ (unsigned char)*s++) * 16777619u;
    }
    return h;
}

int main(int argc, char **argv)
{
    const char *lic = argc > 1 ? argv[1] : "";
    if (verify_license(lic)) {
        printf("licensed\n");
        return 0;
    }
    printf("unlicensed (checksum=%u)\n", compute_checksum(lic));
    return 1;
}
