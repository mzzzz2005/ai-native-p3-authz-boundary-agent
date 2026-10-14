"""Independent controller. Re-reads the authorization scope on every decision."""

from dataclasses import dataclass, field

from .authorization import AuthorizationSource
from .registry import CHECKS, TARGET_ID


@dataclass
class Decision:
    allowed: bool
    reason: str
    authz_version: int
    test_id: str | None = None


@dataclass
class Controller:
    source: AuthorizationSource
    max_attempts: int = 8
    max_rounds: int = 8
    logical_budget: int = 90
    attempts: int = 0
    rounds: int = 0
    logical_time: int = 0
    completed: set[str] = field(default_factory=set)
    healthy: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 8:
            raise ValueError("max_attempts must be in 1..8")
        if not 1 <= self.max_rounds <= 8:
            raise ValueError("max_rounds must be in 1..8")
        if not 1 <= self.logical_budget <= 90:
            raise ValueError("logical_budget must be in 1..90")

    def admit(self, target_id: str, test_id: str) -> Decision:
        policy_version = self.source.version()
        if self.rounds >= self.max_rounds:
            return Decision(False, "decision_budget_exhausted", policy_version)
        self.rounds += 1
        if target_id != TARGET_ID or test_id not in CHECKS:
            return Decision(False, "unregistered_target_or_action", policy_version)
        check = CHECKS[test_id]
        # The scope read happens here, on every admitted attempt. This is the
        # route's whole point: a static snapshot and a dynamic source disagree
        # exactly at this line.
        if not self.source.is_authorized(test_id):
            return Decision(False, "authorization_denied", policy_version, test_id)
        if self.attempts >= self.max_attempts or self.logical_time >= self.logical_budget:
            return Decision(False, "execution_budget_exhausted", policy_version, test_id)
        if test_id in self.completed:
            return Decision(False, "duplicate_check", policy_version, test_id)
        if check.prerequisite and check.prerequisite not in self.healthy:
            return Decision(False, "prerequisite_unavailable", policy_version, test_id)
        self.attempts += 1
        return Decision(True, "authorized_registered_check", policy_version, test_id)

    def observe(self, test_id: str, elapsed: int, healthy: bool) -> None:
        self.logical_time += elapsed
        self.completed.add(test_id)
        if healthy:
            self.healthy.add(test_id)

