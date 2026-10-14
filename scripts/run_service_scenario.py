"""Run the agent against the real local teaching-document service.

``--deployment correct`` starts a service whose authorization rules are right.
``--deployment overpermissive`` starts a deliberately misconfigured service, so
the agent has a real chance of finding a real authorization defect.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from authz_agent.authorization import DYNAMIC_SOURCE, STATIC_SNAPSHOT  # noqa: E402
from authz_agent.runner import run  # noqa: E402
from authz_agent.target import LocalServiceTarget  # noqa: E402
from doc_service.server import LocalTeachingDocsService  # noqa: E402

DEPLOYMENTS = {
    "correct": ROOT / "config" / "service.correct.json",
    "overpermissive": ROOT / "config" / "service.overpermissive.json",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment", choices=tuple(DEPLOYMENTS), default="correct")
    parser.add_argument(
        "--strategy", choices=(STATIC_SNAPSHOT, DYNAMIC_SOURCE), default=STATIC_SNAPSHOT
    )
    parser.add_argument("--revoke-scope-after", type=int, default=None)
    parser.add_argument("--revoke-scope-test", default="T02")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "service")
    args = parser.parse_args()

    revocations = None
    if args.revoke_scope_after is not None:
        revocations = [
            {
                "after_attempt": args.revoke_scope_after,
                "test_id": args.revoke_scope_test,
                "reason": "teacher withdrew the agent's scope during the run",
            }
        ]

    service = LocalTeachingDocsService(DEPLOYMENTS[args.deployment])
    destination = args.output / args.deployment / args.strategy
    with service:
        target = LocalServiceTarget(service.base_url, service.credentials())
        path = run(
            {"fixture_id": f"local-service-{args.deployment}", "version": "0.1"},
            destination,
            strategy=args.strategy,
            revocations=revocations,
            executor=target,
            extra_metadata={
                "target_kind": "local_service",
                "service": service.policy.describe(),
            },
        )

    report = json.loads((path / "report.json").read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "run_dir": path.relative_to(ROOT).as_posix(),
                "run_id": report["run_id"],
                "deployment": args.deployment,
                "strategy": report["strategy"],
                "target_kind": report["target_kind"],
                "service_fingerprint": report["service"]["fingerprint"][:16],
                "actual_attempts": report["actual_attempts"],
                "stop_reason": report["stop_reason"],
                "conclusions": {
                    row["test_id"]: row["conclusion"] for row in report["results"]
                },
                "denied": report["denied"],
                "uncovered": report["uncovered"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

