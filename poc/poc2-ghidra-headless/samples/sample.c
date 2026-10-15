/* PoC-2 样例二进制源码：包含若干具代表性的函数（业务逻辑 / 算法 / 字符串）。 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int add(int a, int b) { return a + b; }

int collatz_steps(long n) {
    int s = 0;
    while (n != 1) { n = (n % 2 == 0) ? n / 2 : 3 * n + 1; s++; }
    return s;
}

long fib(int n) {
    long a = 0, b = 1;
    for (int i = 0; i < n; i++) { long t = a + b; a = b; b = t; }
    return a;
}

int gcd(int a, int b) { while (b) { int t = a % b; a = b; b = t; } return a < 0 ? -a : a; }

unsigned crc32_simple(const unsigned char *d, int n) {
    unsigned crc = 0xFFFFFFFFu;
    for (int i = 0; i < n; i++) {
        crc ^= d[i];
        for (int k = 0; k < 8; k++)
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

int is_palindrome(const char *s) {
    int i = 0, j = (int)strlen(s) - 1;
    while (i < j) { if (s[i] != s[j]) return 0; i++; j--; }
    return 1;
}

double poly_eval(const double *c, int n, double x) {
    double r = 0.0;
    for (int i = n - 1; i >= 0; i--) r = r * x + c[i];
    return r;
}

int count_words(const char *s) {
    int c = 0, in = 0;
    for (; *s; s++) {
        if (*s == ' ' || *s == '\t' || *s == '\n') in = 0;
        else if (!in) { in = 1; c++; }
    }
    return c;
}

int main(void) {
    printf("%d %d %ld %d\n", add(2, 3), collatz_steps(27), fib(20), gcd(1071, 462));
    printf("%u %d %d\n", crc32_simple((const unsigned char *)"hello", 5),
           is_palindrome("level"), count_words("the quick brown fox"));
    double c[3] = {1.0, 2.0, 3.0};
    printf("%.2f\n", poly_eval(c, 3, 2.0));
    return 0;
}
