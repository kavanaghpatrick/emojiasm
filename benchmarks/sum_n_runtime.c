/* Reference C: N from command line, prevents constant folding */
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    long N = argc > 1 ? atol(argv[1]) : 50000;
    long total = 0;
    long i = 1;
    while (i <= N) {
        total += i;
        i++;
    }
    printf("%ld\n", total);
    return 0;
}
