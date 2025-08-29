"""Equivalent of EcoLang nested if/else sample; prints ECO_OPS for wrapper."""

def main() -> None:
    a = 2
    if a > 0:
        if a == 2:
            print("inner-yes")
        else:
            print("inner-no")
    else:
        print("outer-no")
    # Assignment + two comparisons + one print path = 4 logical ops
    print("ECO_OPS: 4")


if __name__ == "__main__":
    main()
