/* R1 样例：供扫描器与变换引擎的测试使用 */
#include <stdio.h>

int add(int a, int b) { return a + b; }

int classify(int x) {
    if (x > 0) return 1;
    if (x == 0) return 0;
    return -1;
}

int secret_mix(int x) {
    int y = x ^ 0x5a;
    return y * 3 + 1;
}

int main(void) {
    printf("%d %d %d\n", add(2, 3), classify(-2), secret_mix(7));
    return 0;
}
