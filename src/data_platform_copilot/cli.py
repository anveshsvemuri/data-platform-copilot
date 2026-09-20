from __future__ import annotations

import argparse
from pathlib import Path

from .copilot import DataPlatformCopilot
from .evaluation import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Grounded data-platform copilot")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--knowledge", type=Path, default=Path("knowledge"))
    parser.add_argument("--evaluate", type=Path)
    args = parser.parse_args()
    copilot = DataPlatformCopilot(args.knowledge)
    if args.evaluate:
        print(evaluate(copilot, args.evaluate))
    elif args.question:
        print(copilot.ask(args.question).model_dump_json(indent=2))
    else:
        parser.error("provide a question or --evaluate")


if __name__ == "__main__":
    main()

