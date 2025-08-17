r"""Small cleanup utility for local dev artifacts.

Usage:
  python scripts\clean_repo.py         # dry-run
  python scripts\clean_repo.py --yes   # actually delete

It will target: .venv, .venv-1, __pycache__, .pytest_cache, backend/ecolang.db
"""

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TARGETS = [
    ROOT / ".venv",
    ROOT.parent / ".venv-1",
    ROOT / ".pytest_cache",
    ROOT / "backend" / "ecolang.db",
]


def gather_extra_cache_dirs(path: Path):
    for p in path.rglob("__pycache__"):
        TARGETS.append(p)


def main(dry_run: bool):
    gather_extra_cache_dirs(ROOT)
    print("Found targets:")
    for t in TARGETS:
        print("  ", t)

    if dry_run:
        print(
            "\nDry-run mode; nothing will be deleted. Re-run with --yes to delete."
        )
        return 0

    for t in TARGETS:
        if not t.exists():
            continue
        try:
            if t.is_file():
                t.unlink()
            else:
                shutil.rmtree(t)
            print("Deleted", t)
        except Exception as e:
            print("Failed to delete", t, e)
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--yes", action="store_true", help="Actually delete targets"
    )
    args = p.parse_args()
    exit(main(not args.yes))

