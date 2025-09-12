"""Equivalent of EcoLang nested if/else sample; scaled by N iterations.

Prints final check result and ECO_OPS = N * ops_per_iter.
"""
import os


def main() -> None:
    N = int(os.environ.get("ECO_BENCH_N", "1000000"))
    a = 2
    s = 0
    for _ in range(N):
        if a > 0:
            if a == 2:
                s += 1
            else:
                s -= 1
        else:
            s -= 2
    print(s)  # optional: ensures loop isn't optimized away
    # Two comparisons + one update per iteration
    ops_per_iter = 3
    print(f"ECO_OPS: {N * ops_per_iter}")


if __name__ == "__main__":
    main()
