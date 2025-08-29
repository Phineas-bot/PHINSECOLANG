#include <iostream>
#include <cstdlib>
using namespace std;

int main() {
    int N = 5000000;
    const char* env = getenv("ECO_BENCH_N");
    if (env) N = atoi(env);
    long long s = 0;
    for (int i = 0; i < N; i++) s += (i & 1);
    cout << s << "\n";                 // optional correctness output
    cout << "ECO_OPS: " << N << "\n"; // required
    return 0;
}
