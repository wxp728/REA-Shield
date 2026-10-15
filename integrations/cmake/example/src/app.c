#include <stdio.h>

/* 敏感函数（名字含 secret -> 扫描为 P1，进入变换白名单） */
int secret_mix(int x) {
    int y = x * 3 + 1;
    y ^= (y << 5);
    return y - 7;
}

int main(void) {
    printf("%d\n", secret_mix(11));
    return 0;
}
