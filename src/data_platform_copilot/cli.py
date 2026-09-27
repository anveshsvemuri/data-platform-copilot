from __future__ import annotations

import argparse
import json
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
    parser.add_argument(
        "--minimum-pass-rate",
        type=float,
        default=1.0,
        help="Exit with status 2 when evaluation falls below this rate",
    )
    args = parser.parse_args()
    if args.build_index:
        if not args.index:
            parser.error("--build-index requires --index")
        chunks = DataPlatformCopilot.create_index(args.knowledge, args.index)
        print(f"indexed chunks={chunks} output={args.index}")
        return
    copilot = DataPlatformCopilot(args.knowledge, args.index, cache_path=args.cache)
    if args.evaluate:
        if not 0 <= args.minimum_pass_rate <= 1:
            parser.error("--minimum-pass-rate must be between 0 and 1")
        metrics = evaluate(copilot, args.evaluate)
        print(json.dumps(metrics, sort_keys=True))
        if metrics["pass_rate"] < args.minimum_pass_rate:
            raise SystemExit(2)
    elif args.question:
        print(copilot.ask(args.question).model_dump_json(indent=2))
    else:
        parser.error("provide a question or --evaluate")


if __name__ == "__main__":
    main()
