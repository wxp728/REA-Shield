#include <stdio.h>

int secret_mix(int x) {
    return (x ^ (x << 3)) + 5;
}

int main(void) {
    printf("%d\n", secret_mix(9));
    return 0;
}
