/*
 * PoC-1 样例工程：含循环、条件、递归的若干函数 + 单元测试。
 * 通过测试说明 CFF 变换未破坏语义。
 */
#include <stdio.h>

int collatz_steps(long n) {
    int steps = 0;
    while (n != 1) {
        if (n % 2 == 0)
            n /= 2;
        else
            n = 3 * n + 1;
        steps++;
    }
    return steps;
}

long fib(int n) {
    if (n < 2)
        return n;
    return fib(n - 1) + fib(n - 2);
}

long sum_squares(int n) {
    long s = 0;
    for (int i = 1; i <= n; i++)
        s += (long)i * (long)i;
    return s;
}

int gcd(int a, int b) {
    while (b != 0) {
        int t = a % b;
        a = b;
        b = t;
    }
    return a < 0 ? -a : a;
}

int main(void) {
    int fails = 0;

    if (collatz_steps(27) != 111) { printf("collatz FAIL: %d\n", collatz_steps(27)); fails++; }
    if (fib(20) != 6765)          { printf("fib FAIL: %ld\n", fib(20)); fails++; }
    if (sum_squares(100) != 338350) { printf("sum_squares FAIL\n"); fails++; }
    if (gcd(1071, 462) != 21)     { printf("gcd FAIL\n"); fails++; }

    for (int i = 0; i < 50; i++) {
        long s = sum_squares(i), expect = 0;
        for (int j = 1; j <= i; j++) expect += (long)j * j;
        if (s != expect) fails++;
    }
    for (long n = 2; n < 40; n++)
        if (collatz_steps(n) <= 0) fails++;

    if (fails) { printf("FAIL (%d)\n", fails); return 1; }
    printf("OK\n");
    return 0;
}
