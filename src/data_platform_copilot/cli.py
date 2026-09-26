from __future__ import annotations

import argparse
from pathlib import Path

from .copilot import DataPlatformCopilot
from .evaluation import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Grounded data-platform copilot")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--knowledge", type=Path, default=Path("knowledge"))
    parser.add_argument("--index", type=Path, help="Persistent retrieval index to load or build")
    parser.add_argument("--cache", type=Path, help="Persistent privacy-safe semantic response cache")
    parser.add_argument("--build-index", action="store_true")
    parser.add_argument("--evaluate", type=Path)
    args = parser.parse_args()
    if args.build_index:
        if not args.index:
            parser.error("--build-index requires --index")
        chunks = DataPlatformCopilot.create_index(args.knowledge, args.index)
        print(f"indexed chunks={chunks} output={args.index}")
        return
    copilot = DataPlatformCopilot(args.knowledge, args.index, cache_path=args.cache)
    if args.evaluate:
        print(evaluate(copilot, args.evaluate))
    elif args.question:
        print(copilot.ask(args.question).model_dump_json(indent=2))
    else:
        parser.error("provide a question or --evaluate")


if __name__ == "__main__":
    main()
