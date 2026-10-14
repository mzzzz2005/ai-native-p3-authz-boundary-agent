"""Pure in-memory simulator. No URL, no shell, no credential interface."""

from copy import deepcopy

from .registry import CHECKS


class Simulator:
    def __init__(self, fixture: dict) -> None:
        self.fixture = deepcopy(fixture)
        self.calls: list[str] = []

    def execute(self, test_id: str) -> dict:
        check = CHECKS[test_id]
        self.calls.append(test_id)
        allowed = check.expected_status == 200
        observation = {
            "request_id": f"authz-sim-{len(self.calls):03d}",
            "status_code": check.expected_status,
            "body": check.canary if allowed else "access denied",
            "tool_error": None,
            "logical_seconds": 1,
        }
        observation.update(deepcopy(self.fixture.get("overrides", {}).get(test_id, {})))
        return observation

