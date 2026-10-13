import argparse
import json

from . import audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare saved retrieval, context, and semantic answer stages offline.")
    for name in ("baseline", "changed", "no-memory", "answer-key"):
        parser.add_argument(f"--{name}", required=True, help="Path to the documented JSONL input.")
    parser.add_argument("--baseline-broadcast-draw", action="store_true", help="Reuse baseline records that omit draw over each changed draw.")
    parser.add_argument("--no-memory-broadcast-draw", action="store_true", help="Reuse no-memory records that omit draw over each changed draw.")
    args = parser.parse_args()
    try:
        report = audit(
            baseline=args.baseline, changed=args.changed, no_memory=args.no_memory,
            answer_key=args.answer_key,
            baseline_broadcast=("draw",) if args.baseline_broadcast_draw else (),
            no_memory_broadcast=("draw",) if args.no_memory_broadcast_draw else (),
        )
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(report.summary(), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
