"""Run one bundled public fixture with one authorization strategy."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from authz_agent.authorization import DYNAMIC_SOURCE, STATIC_SNAPSHOT  # noqa: E402
from authz_agent.runner import run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("good", "known-bad", "timeout"), default="good")
    parser.add_argument("--strategy", choices=(STATIC_SNAPSHOT, DYNAMIC_SOURCE), default=STATIC_SNAPSHOT)
    parser.add_argument("--revoke-after", type=int, default=None,
                        help="Withdraw scope for --revoke-test after this many executed checks")
    parser.add_argument("--revoke-test", default="T02")
    parser.add_argument("--max-attempts", type=int, choices=range(1, 9), default=8)
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "runs")
    args = parser.parse_args()

    fixture = json.loads(
        (ROOT / "lab" / "public-fixtures" / f"{args.scenario}.json").read_text(encoding="utf-8")
    )
    revocations = None
    if args.revoke_after is not None:
        revocations = [
            {
                "after_attempt": args.revoke_after,
                "test_id": args.revoke_test,
                "reason": "teacher withdrew scope during the run",
            }
        ]
    destination = run(
        fixture,
        args.output,
        strategy=args.strategy,
        max_attempts=args.max_attempts,
        revocations=revocations,
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

