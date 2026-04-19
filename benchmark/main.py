import logging
import sys

from .runner import run_all
from .report import generate_report, generate_from_latest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        results = run_all()
        report = generate_report(results)
        print(report)
    elif cmd == "report":
        print(generate_from_latest())
    else:
        print("Usage: python -m benchmark [run|report]")
        sys.exit(1)


if __name__ == "__main__":
    main()
