"""
Sample portable benchmark that prints ECO_OPS for the green wrapper.
"""
import os


def run(n: int = 5_000_000) -> int:
    s = 0
    for i in range(n):
        s += i & 1
    return s


if __name__ == "__main__":
    N = int(os.environ.get("ECO_BENCH_N", "5000000"))
    s = run(N)
    # Optional correctness output
    print(s)
    # Required for wrapper 
    print(f"ECO_OPS: {N}")
