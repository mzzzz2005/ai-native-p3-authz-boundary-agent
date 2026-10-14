"""Authorization sources: the experiment variable of this route.

Important distinction, and the reason this route is different from the paired
group's scheduling comparison:

* Actor state (A / anonymous / revoked_A) is *test data*. It describes which
  fictional identity holds a valid credential, and the simulator uses it to
  decide the expected status of a check.
* Authorization scope (this module) is *our own permission to test*. It says
  which registered checks the agent is currently allowed to start.

Strategy S freezes the scope once at run start. Strategy T reads a versioned
event source, so a withdrawal that happens mid-run takes effect before the next
check is admitted. Everything downstream is identical between the two, so any
difference in observed behaviour is attributable to the authorization source.
"""

from __future__ import annotations

from dataclasses import dataclass

AUTHORIZED = "authorized"
REVOKED = "revoked"
VALID_STATES = frozenset({AUTHORIZED, REVOKED})

STATIC_SNAPSHOT = "static_snapshot"
DYNAMIC_SOURCE = "dynamic_source"


class AuthorizationError(ValueError):
    pass


@dataclass(frozen=True)
class AuthorizationEvent:
    """A trusted change to our own testing scope, issued outside the agent."""

    version: int
    test_id: str
    state: str
    reason: str = ""

    def __post_init__(self) -> None:
        if self.state not in VALID_STATES:
            raise AuthorizationError(f"unsupported authorization state: {self.state!r}")


class AuthorizationSource:
    """Common interface. The controller only calls is_authorized() and version()."""

    strategy = "unset"

    def version(self) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    def is_authorized(self, test_id: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def apply(self, event: AuthorizationEvent) -> bool:  # pragma: no cover
        raise NotImplementedError

    def applied_events(self) -> list[AuthorizationEvent]:
        return []

    def refused_events(self) -> list[AuthorizationEvent]:
        return []


class StaticAuthorizationSnapshot(AuthorizationSource):
    """Scope read once at start. Later events are refused, never silently applied."""

    strategy = STATIC_SNAPSHOT

    def __init__(self, initial: dict[str, str]) -> None:
        self._scope = dict(initial)
        self._version = 1
        self._refused: list[AuthorizationEvent] = []

    def version(self) -> int:
        return self._version

    def is_authorized(self, test_id: str) -> bool:
        return self._scope.get(test_id, REVOKED) == AUTHORIZED

    def apply(self, event: AuthorizationEvent) -> bool:
        self._refused.append(event)
        return False

    def refused_events(self) -> list[AuthorizationEvent]:
        return list(self._refused)

    def snapshot(self) -> dict[str, str]:
        return dict(self._scope)


class DynamicAuthorizationSource(AuthorizationSource):
    """Versioned scope; the controller sees the latest value on every decision."""

    strategy = DYNAMIC_SOURCE

    def __init__(self, initial: dict[str, str]) -> None:
        self._scope = dict(initial)
        self._version = 1
        self._applied: list[AuthorizationEvent] = []

    def version(self) -> int:
        return self._version

    def is_authorized(self, test_id: str) -> bool:
        return self._scope.get(test_id, REVOKED) == AUTHORIZED

    def apply(self, event: AuthorizationEvent) -> bool:
        if event.version != self._version + 1:
            raise AuthorizationError(
                "authorization events must be sequential: "
                f"expected {self._version + 1}, got {event.version}"
            )
        self._scope[event.test_id] = event.state
        self._version = event.version
        self._applied.append(event)
        return True

    def applied_events(self) -> list[AuthorizationEvent]:
        return list(self._applied)

    def snapshot(self) -> dict[str, str]:
        return dict(self._scope)


def source_for(strategy: str, initial: dict[str, str]) -> AuthorizationSource:
    if strategy == STATIC_SNAPSHOT:
        return StaticAuthorizationSnapshot(initial)
    if strategy == DYNAMIC_SOURCE:
        return DynamicAuthorizationSource(initial)
    raise AuthorizationError(f"unknown strategy: {strategy!r}")


def full_scope() -> dict[str, str]:
    from .registry import CHECKS

    return {test_id: AUTHORIZED for test_id in CHECKS}

