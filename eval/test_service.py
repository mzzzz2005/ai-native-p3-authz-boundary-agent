import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from authz_agent.authorization import STATIC_SNAPSHOT  # noqa: E402
from authz_agent.runner import run  # noqa: E402
from authz_agent.target import LocalServiceTarget, TargetError  # noqa: E402
from doc_service.server import LocalTeachingDocsService  # noqa: E402

CORRECT = ROOT / "config" / "service.correct.json"
OVERPERMISSIVE = ROOT / "config" / "service.overpermissive.json"


def call(base_url: str, path: str, token: str | None = None) -> tuple[int, str]:
    request = urllib.request.Request(base_url + path)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


class ServiceAuthorizationTests(unittest.TestCase):
    def test_correct_deployment_enforces_authentication_and_ownership(self):
        with LocalTeachingDocsService(CORRECT) as service:
            base = service.base_url
            tokens = service.credentials()
            self.assertEqual(call(base, "/documents/DA", tokens["A"]), (200, "TEACHING_DA"))
            self.assertEqual(
                call(base, "/documents/DA/attachment", tokens["A"]),
                (200, "TEACHING_DA_ATTACHMENT"),
            )
            self.assertEqual(call(base, "/documents/DB", tokens["A"])[0], 403)
            self.assertEqual(call(base, "/documents/DB/attachment", tokens["A"])[0], 403)
            self.assertEqual(call(base, "/documents/DA")[0], 401)
            self.assertEqual(call(base, "/documents/DA", tokens["revoked_A"])[0], 401)
            self.assertEqual(call(base, "/documents/MISSING", tokens["A"])[0], 404)

    def test_forbidden_response_never_leaks_the_canary(self):
        with LocalTeachingDocsService(CORRECT) as service:
            status, body = call(
                service.base_url, "/documents/DB", service.credentials()["A"]
            )
            self.assertEqual(status, 403)
            self.assertNotIn("TEACHING_DB", body)

    def test_overpermissive_deployment_discloses_the_other_document(self):
        with LocalTeachingDocsService(OVERPERMISSIVE) as service:
            status, body = call(
                service.base_url, "/documents/DB", service.credentials()["A"]
            )
            self.assertEqual(status, 200)
            self.assertIn("TEACHING_DB", body)

    def test_overpermissive_deployment_still_blocks_the_attachment(self):
        with LocalTeachingDocsService(OVERPERMISSIVE) as service:
            status, body = call(
                service.base_url, "/documents/DB/attachment", service.credentials()["A"]
            )
            self.assertEqual(status, 403)
            self.assertNotIn("TEACHING_DB_ATTACHMENT", body)

    def test_revoked_credential_can_be_withdrawn_while_running(self):
        with LocalTeachingDocsService(CORRECT) as service:
            token = service.credentials()["B"]
            self.assertEqual(call(service.base_url, "/documents/DB", token)[0], 200)
            service.revoke("B")
            self.assertEqual(call(service.base_url, "/documents/DB", token)[0], 401)


class AgentAgainstServiceTests(unittest.TestCase):
    def execute(self, deployment: Path, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            service = LocalTeachingDocsService(deployment)
            with service:
                target = LocalServiceTarget(service.base_url, service.credentials())
                path = run(
                    {"fixture_id": f"local-{deployment.stem}", "version": "0.1"},
                    Path(directory),
                    strategy=STATIC_SNAPSHOT,
                    executor=target,
                    extra_metadata={"target_kind": "local_service"},
                    **kwargs,
                )
                report = json.loads((path / "report.json").read_text(encoding="utf-8"))
                events = [
                    json.loads(line)
                    for line in (path / "events.jsonl").read_text(encoding="utf-8").splitlines()
                ]
        return report, events

    def test_correct_deployment_confirms_nothing(self):
        report, _ = self.execute(CORRECT)
        self.assertEqual(report["actual_attempts"], 6)
        self.assertTrue(
            all(row["conclusion"] == "NOT_CONFIRMED" for row in report["results"])
        )
        self.assertEqual(report["uncovered"], [])

    def test_overpermissive_deployment_confirms_only_the_real_defect(self):
        report, _ = self.execute(OVERPERMISSIVE)
        confirmed = sorted(
            row["test_id"]
            for row in report["results"]
            if row["conclusion"] == "CONFIRMED"
        )
        self.assertEqual(confirmed, ["T02"])

    def test_confirmed_finding_quotes_a_real_http_response(self):
        report, events = self.execute(OVERPERMISSIVE)
        finding = next(row for row in report["results"] if row["test_id"] == "T02")
        observation = next(
            item for item in events if item["evidence_id"] in finding["evidence_ids"]
        )
        self.assertEqual(observation["actual_result"]["status_code"], 200)
        self.assertIn("TEACHING_DB", observation["actual_result"]["body"])
        self.assertTrue(
            observation["actual_result"]["request_id"].startswith("teaching-svc-")
        )

    def test_agent_refuses_arbitrary_url_and_unregistered_check(self):
        with self.assertRaises(TargetError):
            LocalServiceTarget("http://example.invalid", {"A": "x"})
        with LocalTeachingDocsService(CORRECT) as service:
            target = LocalServiceTarget(service.base_url, service.credentials())
            with self.assertRaises(TargetError):
                target.execute("CHK-EVERYTHING")

    def test_unregistered_target_never_reaches_the_service(self):
        with LocalTeachingDocsService(CORRECT) as service:
            target = LocalServiceTarget(service.base_url, service.credentials())
            with patch.object(LocalServiceTarget, "execute") as execute:
                run(
                    {"fixture_id": "local", "version": "0.1"},
                    Path(tempfile.mkdtemp()),
                    strategy=STATIC_SNAPSHOT,
                    target_id="http://elsewhere.invalid",
                    executor=target,
                )
                execute.assert_not_called()

    def test_transport_failure_is_inconclusive_not_a_finding(self):
        target = LocalServiceTarget("http://127.0.0.1:1", {"A": "unused"})
        observation = target.execute("T01")
        self.assertIsNotNone(observation["tool_error"])
        self.assertIsNone(observation["status_code"])


if __name__ == "__main__":
    unittest.main()

