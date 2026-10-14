import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from authz_agent.authorization import (  # noqa: E402
    DYNAMIC_SOURCE,
    STATIC_SNAPSHOT,
    AuthorizationError,
    AuthorizationEvent,
    full_scope,
    source_for,
)
from authz_agent.registry import CHECKS  # noqa: E402
from authz_agent.runner import run  # noqa: E402


class AuthorizationSourceTests(unittest.TestCase):
    def test_static_snapshot_refuses_later_withdrawals(self):
        source = source_for(STATIC_SNAPSHOT, full_scope())
        accepted = source.apply(AuthorizationEvent(2, "T02", "revoked", "test"))
        self.assertFalse(accepted)
        self.assertTrue(source.is_authorized("T02"))
        self.assertEqual(source.version(), 1)
        self.assertEqual(len(source.refused_events()), 1)

    def test_dynamic_source_applies_sequential_withdrawals(self):
        source = source_for(DYNAMIC_SOURCE, full_scope())
        self.assertTrue(source.apply(AuthorizationEvent(2, "T02", "revoked", "test")))
        self.assertFalse(source.is_authorized("T02"))
        self.assertEqual(source.version(), 2)

    def test_dynamic_source_rejects_non_sequential_versions(self):
        source = source_for(DYNAMIC_SOURCE, full_scope())
        with self.assertRaises(AuthorizationError):
            source.apply(AuthorizationEvent(5, "T02", "revoked", "out of order"))


class RunTests(unittest.TestCase):
    def execute(self, scenario="good", fixture=None, strategy=STATIC_SNAPSHOT, **kwargs):
        if fixture is None:
            fixture = json.loads(
                (ROOT / "lab" / "public-fixtures" / f"{scenario}.json").read_text(
                    encoding="utf-8"
                )
            )
        with tempfile.TemporaryDirectory() as directory:
            path = run(fixture, Path(directory), strategy=strategy, **kwargs)
            report = json.loads((path / "report.json").read_text(encoding="utf-8"))
            events = [
                json.loads(line)
                for line in (path / "events.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            for name, digest in json.loads(
                (path / "checksums.json").read_text(encoding="utf-8")
            ).items():
                self.assertEqual(
                    hashlib.sha256((path / name).read_bytes()).hexdigest(), digest
                )
        return report, events

    def test_good_run_executes_all_six_checks(self):
        report, _ = self.execute()
        self.assertEqual(report["actual_attempts"], 6)
        self.assertEqual({row["test_id"] for row in report["results"]}, set(CHECKS))
        self.assertTrue(
            all(row["conclusion"] == "NOT_CONFIRMED" for row in report["results"])
        )

    def test_known_bad_confirms_with_resolvable_evidence(self):
        report, events = self.execute("known-bad")
        finding = next(row for row in report["results"] if row["test_id"] == "T02")
        self.assertEqual(finding["conclusion"], "CONFIRMED")
        evidence = next(
            item for item in events if item["evidence_id"] in finding["evidence_ids"]
        )
        self.assertIn("TEACHING_DB", evidence["actual_result"]["body"])

    def test_timeout_is_inconclusive_and_reports_full_uncovered(self):
        report, events = self.execute("timeout")
        self.assertEqual(report["actual_attempts"], 1)
        self.assertEqual(report["stop_reason"], "execution_budget_exhausted")
        self.assertEqual(len(report["uncovered"]), 6)
        self.assertEqual(sum(item["event"] == "execution_started" for item in events), 1)

    def test_unregistered_target_never_executes(self):
        with patch("authz_agent.runner.Simulator.execute") as execute:
            report, events = self.execute(target_id="https://unregistered.invalid")
            execute.assert_not_called()
        self.assertEqual(report["actual_attempts"], 0)
        self.assertFalse(any(item["event"] == "execution_started" for item in events))

    def test_unregistered_action_never_executes(self):
        with patch("authz_agent.runner.Simulator.execute") as execute:
            report, events = self.execute(proposals=("SHELL",))
            execute.assert_not_called()
        self.assertEqual(report["actual_attempts"], 0)
        self.assertFalse(any(item["event"] == "execution_started" for item in events))

    def test_static_snapshot_ignores_mid_run_withdrawal(self):
        report, events = self.execute(
            strategy=STATIC_SNAPSHOT,
            revocations=[{"after_attempt": 1, "test_id": "T02", "reason": "withdraw"}],
        )
        self.assertEqual(report["actual_attempts"], 6)
        self.assertEqual(report["denied"], [])
        self.assertEqual(report["authorization"]["version_at_end"], 1)
        self.assertEqual(len(report["authorization"]["refused_events"]), 1)
        refusals = [item for item in events if item["event"] == "authorization_event"]
        self.assertFalse(refusals[0]["accepted"])

    def test_dynamic_source_stops_the_withdrawn_check(self):
        report, events = self.execute(
            strategy=DYNAMIC_SOURCE,
            revocations=[{"after_attempt": 1, "test_id": "T02", "reason": "withdraw"}],
        )
        self.assertIn("T02", report["denied"])
        self.assertNotIn("T02", [row["test_id"] for row in report["results"] if row["execution_status"] == "EXECUTED"])
        self.assertEqual(report["authorization"]["version_at_end"], 2)
        self.assertEqual(len(report["authorization"]["applied_events"]), 1)
        started = [item["test_id"] for item in events if item["event"] == "execution_started"]
        self.assertNotIn("T02", started)

    def test_withdrawn_check_never_reported_as_safe(self):
        report, _ = self.execute(
            strategy=DYNAMIC_SOURCE,
            revocations=[{"after_attempt": 1, "test_id": "T02", "reason": "withdraw"}],
        )
        denied_row = next(row for row in report["results"] if row["test_id"] == "T02")
        self.assertEqual(denied_row["conclusion"], "INCONCLUSIVE")
        self.assertIn("T02", report["uncovered"])

    def test_budget_cannot_be_increased_beyond_policy(self):
        with self.assertRaises(ValueError):
            run(
                {"fixture_id": "good", "version": "0.1"},
                Path(tempfile.mkdtemp()),
                strategy=STATIC_SNAPSHOT,
                max_attempts=9,
            )


if __name__ == "__main__":
    unittest.main()

