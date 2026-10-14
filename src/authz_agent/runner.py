"""Authorization-state-driven run: propose -> admit -> execute -> evidence."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .authorization import (
    AUTHORIZED,
    REVOKED,
    AuthorizationEvent,
    AuthorizationSource,
    full_scope,
    source_for,
)
from .controller import Controller
from .executor import Simulator
from .registry import CHECKS, CONTRACT_VERSION, ORDER, REGISTRY_VERSION, TARGET_ID
from .reporting import INCONCLUSIVE, classify


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _source_provenance() -> tuple[str, bool | None]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            text=True,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=Path(__file__).resolve().parents[2],
                text=True,
            ).strip()
        )
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unavailable", None


def run(
    fixture: dict,
    output_root: Path,
    *,
    strategy: str,
    target_id: str = TARGET_ID,
    proposals=ORDER,
    max_attempts: int = 8,
    logical_budget: int = 90,
    revocations: list[dict] | None = None,
    executor=None,
    extra_metadata: dict | None = None,
) -> Path:
    """Run once with one authorization strategy.

    ``revocations`` entries look like
    ``{"after_attempt": 2, "test_id": "T04", "reason": "teacher withdrew scope"}``
    and are applied only after that many checks have actually executed.
    """

    source: AuthorizationSource = source_for(strategy, full_scope())
    controller = Controller(
        source=source, max_attempts=max_attempts, logical_budget=logical_budget
    )
    simulator = executor if executor is not None else Simulator(fixture)
    run_id = "run-" + uuid.uuid4().hex
    destination = output_root / run_id
    destination.mkdir(parents=True, exist_ok=False)
    commit, dirty = _source_provenance()
    fixture_hash = hashlib.sha256(
        json.dumps(fixture, sort_keys=True).encode()
    ).hexdigest()

    metadata = {
        "run_id": run_id,
        "commit": commit,
        "working_tree_dirty_at_start": dirty,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contract_version": CONTRACT_VERSION,
        "registry_version": REGISTRY_VERSION,
        "strategy": strategy,
        "policy_version": f"authz-{strategy}-v0.1",
        "fixture_id": fixture["fixture_id"],
        "fixture_version": fixture["version"],
        "fixture_sha256": fixture_hash,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "target_id": target_id,
        "source": "fixture_demo",
        "evidence_level": "OBSERVED",
        "model_calls": 0,
        "human_signoff": "pending",
        "budgets": {
            "max_attempts": controller.max_attempts,
            "max_rounds": controller.max_rounds,
            "logical_seconds": controller.logical_budget,
            "concurrency": 1,
            "retries": 0,
        },
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    write_json(destination / "metadata.json", metadata)
    write_json(destination / "fixture.json", fixture)

    results = {
        test_id: {
            "test_id": test_id,
            "execution_status": "NOT_RUN",
            "conclusion": INCONCLUSIVE,
            "reason": "not_scheduled",
            "evidence_ids": [],
            "authz_version_at_decision": None,
        }
        for test_id in CHECKS
    }
    scope_at_start = (
        source.snapshot() if hasattr(source, "snapshot") else dict(full_scope())
    )
    pending_revocations = sorted(
        revocations or [], key=lambda item: item.get("after_attempt", 0)
    )
    boundary_notes: list[dict] = []
    started = time.perf_counter()
    sequence = 0
    stop_reason = "plan_finished"

    with (destination / "events.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        def event(kind: str, **fields):
            nonlocal sequence
            sequence += 1
            evidence_id = f"{run_id}:E{sequence:03d}"
            stream.write(
                json.dumps(
                    {
                        "run_id": run_id,
                        "evidence_id": evidence_id,
                        "sequence": sequence,
                        "event": kind,
                        **fields,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            stream.flush()
            return evidence_id

        for test_id in proposals:
            decision = controller.admit(target_id, test_id)
            decision_id = event(
                "controller_decision",
                test_id=test_id,
                allowed=decision.allowed,
                reason=decision.reason,
                authz_version=decision.authz_version,
            )
            if not decision.allowed:
                if (
                    test_id in results
                    and results[test_id]["execution_status"] == "NOT_RUN"
                ):
                    results[test_id].update(
                        execution_status="DENIED",
                        reason=decision.reason,
                        evidence_ids=[decision_id],
                        authz_version_at_decision=decision.authz_version,
                    )
                if "budget_exhausted" in decision.reason:
                    stop_reason = decision.reason
                    break
                continue

            check = CHECKS[test_id]
            event(
                "execution_started",
                test_id=test_id,
                attempt_index=1,
                actor_ref=check.actor,
                resource_ref=check.resource,
                authz_version=decision.authz_version,
            )
            observation = simulator.execute(test_id)
            observation_id = event(
                "observation", test_id=test_id, actual_result=observation
            )
            conclusion, reason = classify(test_id, observation)
            controller.observe(
                test_id,
                observation["logical_seconds"],
                conclusion == "NOT_CONFIRMED",
            )
            results[test_id].update(
                execution_status="EXECUTED",
                conclusion=conclusion,
                reason=reason,
                evidence_ids=[observation_id],
                authz_version_at_decision=decision.authz_version,
            )

            while (
                pending_revocations
                and pending_revocations[0].get("after_attempt", 0)
                <= controller.attempts
            ):
                change = pending_revocations.pop(0)
                authorization_event = AuthorizationEvent(
                    version=source.version() + 1,
                    test_id=change["test_id"],
                    state=REVOKED,
                    reason=change.get("reason", "scope withdrawn"),
                )
                accepted = source.apply(authorization_event)
                event(
                    "authorization_event",
                    test_id=change["test_id"],
                    state=REVOKED,
                    reason=authorization_event.reason,
                    version=authorization_event.version,
                    accepted=accepted,
                    effect="applies_to_next_admission" if accepted else "refused_by_snapshot",
                )
                boundary_notes.append(
                    {
                        "after_attempt": controller.attempts,
                        "test_id": change["test_id"],
                        "accepted": accepted,
                        "note": (
                            "withdrawal takes effect before the next admission"
                            if accepted
                            else "static snapshot refused the withdrawal; scope unchanged"
                        ),
                    }
                )

        event(
            "run_stopped", reason=stop_reason, actual_attempts=controller.attempts
        )

    for leftover in pending_revocations:
        boundary_notes.append(
            {
                "after_attempt": leftover.get("after_attempt"),
                "test_id": leftover.get("test_id"),
                "accepted": False,
                "note": "never reached the requested attempt index",
            }
        )

    scope_at_end = source.snapshot() if hasattr(source, "snapshot") else {}
    report = {
        **metadata,
        "results": list(results.values()),
        "stop_reason": stop_reason,
        "actual_attempts": controller.attempts,
        "planner_rounds": controller.rounds,
        "logical_seconds": controller.logical_time,
        "wall_seconds": time.perf_counter() - started,
        "uncovered": [
            test_id
            for test_id, value in results.items()
            if value["conclusion"] == INCONCLUSIVE
        ],
        "denied": [
            test_id
            for test_id, value in results.items()
            if value["execution_status"] == "DENIED"
        ],
        "authorization": {
            "strategy": strategy,
            "version_at_start": 1,
            "version_at_end": source.version(),
            "scope_at_start": scope_at_start,
            "scope_at_end": scope_at_end,
            "applied_events": [
                {
                    "version": item.version,
                    "test_id": item.test_id,
                    "state": item.state,
                    "reason": item.reason,
                }
                for item in source.applied_events()
            ],
            "refused_events": [
                {
                    "version": item.version,
                    "test_id": item.test_id,
                    "state": item.state,
                    "reason": item.reason,
                }
                for item in source.refused_events()
            ],
            "boundary_notes": boundary_notes,
        },
        "limits": (
            "Offline fixture only. No live target, no model planner, no "
            "independent peer verification. Simulated results must not be "
            "presented as real service acceptance."
        ),
    }
    write_json(destination / "report.json", report)
    files = ("metadata.json", "fixture.json", "events.jsonl", "report.json")
    write_json(
        destination / "checksums.json",
        {name: hashlib.sha256((destination / name).read_bytes()).hexdigest() for name in files},
    )
    return destination

