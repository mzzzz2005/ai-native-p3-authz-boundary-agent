"""Three conclusion states, plus the rule that no evidence is never 'safe'."""

from .registry import CHECKS

CONFIRMED = "CONFIRMED"
NOT_CONFIRMED = "NOT_CONFIRMED"
INCONCLUSIVE = "INCONCLUSIVE"


def classify(test_id: str, observation: dict) -> tuple[str, str]:
    check = CHECKS[test_id]
    if observation.get("tool_error"):
        return INCONCLUSIVE, "tool_error"
    status = observation.get("status_code")
    body = observation.get("body")
    if type(status) is not int or not isinstance(body, str) or not observation.get("request_id"):
        return INCONCLUSIVE, "incomplete_observation"
    if check.expected_status != 200 and check.canary in body:
        return CONFIRMED, "protected_canary_disclosed"
    if status != check.expected_status:
        return INCONCLUSIVE, "unexpected_status_without_sufficient_evidence"
    if check.expected_status == 200 and check.canary not in body:
        return INCONCLUSIVE, "normal_path_missing_canary"
    return NOT_CONFIRMED, "expected_behavior_in_checked_scope"

