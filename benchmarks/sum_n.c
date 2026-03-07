#include <stdio.h>
int main() {
    long N = 50000;
    long total = 0;
    long i = 1;
    while (i <= N) {
        total += i;
        i++;
    }
    printf("%ld\n", total);
    return 0;
}
