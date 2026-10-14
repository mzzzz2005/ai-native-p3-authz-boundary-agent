"""The route's experiment: same fixture, same checks, only the scope source differs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from authz_agent.authorization import DYNAMIC_SOURCE, STATIC_SNAPSHOT  # noqa: E402
from authz_agent.runner import run  # noqa: E402


def summarise(report: dict) -> dict:
    return {
        "strategy": report["strategy"],
        "stop_reason": report["stop_reason"],
        "actual_attempts": report["actual_attempts"],
        "denied": report["denied"],
        "uncovered": report["uncovered"],
        "authz_version_at_end": report["authorization"]["version_at_end"],
        "applied_events": len(report["authorization"]["applied_events"]),
        "refused_events": len(report["authorization"]["refused_events"]),
        "scope_revoked_tests": sorted(
            test_id
            for test_id, state in report["authorization"]["scope_at_end"].items()
            if state != "authorized"
        ),
        "boundary_notes": report["authorization"]["boundary_notes"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="good")
    parser.add_argument("--after-attempt", type=int, default=2)
    parser.add_argument("--revoke-test", default="T02")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "experiment")
    args = parser.parse_args()

    fixture = json.loads(
        (ROOT / "lab" / "public-fixtures" / f"{args.scenario}.json").read_text(encoding="utf-8")
    )
    revocations = [
        {
            "after_attempt": args.after_attempt,
            "test_id": args.revoke_test,
            "reason": "controlled withdrawal at a fixed point",
        }
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for strategy in (STATIC_SNAPSHOT, DYNAMIC_SOURCE):
        destination = run(
            fixture,
            args.output / strategy,
            strategy=strategy,
            revocations=revocations,
        )
        report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
        summary = summarise(report)
        summary["run_id"] = report["run_id"]
        summary["run_dir"] = destination.relative_to(ROOT).as_posix()
        summaries.append(summary)

    result = {
        "experiment": "static_snapshot_vs_dynamic_source",
        "fixture": fixture["fixture_id"],
        "withdrawal_after_attempt": args.after_attempt,
        "withdrawn_test": args.revoke_test,
        "runs": summaries,
        "note": (
            "Both runs share contract, fixture, checks and budgets. The only "
            "difference is the authorization source, so a behavioural "
            "difference is attributable to it."
        ),
    }
    (args.output / "experiment.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

