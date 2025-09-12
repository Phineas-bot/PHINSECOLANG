#include <stdio.h>
#include <stdlib.h>

int main() {
    int N = 5000000;
    char* env = getenv("ECO_BENCH_N");
    if (env) {
        N = atoi(env);
    }
    long long s = 0;
    for (int i = 0; i < N; i++) {
        s += (i & 1);
    }
    printf("%lld\n", s);           // optional correctness output
    printf("ECO_OPS: %d\n", N);    // required
    return 0;
}
