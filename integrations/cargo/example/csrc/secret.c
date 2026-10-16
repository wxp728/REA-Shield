/* Crate 内的 C/FFI 敏感源（REA-Shield Cargo 集成样例，FR-D3）。
 * 独立程序：集成驱动对其施加保护并做差分验证。 */
#include <stdio.h>

int secret_mix(int x) {
    int y = x * 3 + 1;
    y ^= (y << 5);
    return y - 7;
}

int main(void) {
    printf("%d\n", secret_mix(11));
    return 0;
}
