"""HTTP client for the local teaching-document service.

The agent never builds a URL of its own. Each registered check maps to one fixed
method, path and credential reference, and the trusted host supplies the
credential for that reference. There is no parameter for an arbitrary URL, path,
header or body, so this class cannot be turned into a general scanner.
"""

from __future__ import annotations

import urllib.error
import urllib.request

from .registry import TARGET_ID

# test_id -> (path, actor_ref)
ROUTES = {
    "T01": ("/documents/DA", "A"),
    "T02": ("/documents/DB", "A"),
    "T03": ("/documents/DA", "anonymous"),
    "T04": ("/documents/DB/attachment", "A"),
    "T05": ("/documents/DA", "revoked_A"),
    "T06": ("/documents/DA/attachment", "A"),
}


class TargetError(RuntimeError):
    pass


class LocalServiceTarget:
    """Only speaks to the one registered local service."""

    def __init__(
        self,
        base_url: str,
        credentials: dict[str, str],
        *,
        target_id: str = TARGET_ID,
        timeout: float = 5.0,
    ) -> None:
        if target_id != TARGET_ID:
            raise TargetError(f"refusing unregistered target: {target_id!r}")
        if not base_url.startswith("http://127.0.0.1:"):
            raise TargetError(f"refusing non-local base url: {base_url!r}")
        self.base_url = base_url.rstrip("/")
        self.credentials = dict(credentials)
        self.timeout = timeout
        self.calls: list[str] = []

    def execute(self, test_id: str) -> dict:
        route = ROUTES.get(test_id)
        if route is None:
            raise TargetError(f"refusing unregistered check: {test_id!r}")
        path, actor_ref = route
        self.calls.append(test_id)

        request = urllib.request.Request(self.base_url + path, method="GET")
        token = self.credentials.get(actor_ref)
        if token:
            request.add_header("Authorization", f"Bearer {token}")

        observation = {
            "request_id": None,
            "status_code": None,
            "body": None,
            "tool_error": None,
            "logical_seconds": 1,
        }
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                observation["status_code"] = response.status
                observation["body"] = response.read().decode("utf-8", "replace")
                observation["request_id"] = response.headers.get("X-Request-Id")
        except urllib.error.HTTPError as error:
            observation["status_code"] = error.code
            observation["body"] = error.read().decode("utf-8", "replace")
            observation["request_id"] = error.headers.get("X-Request-Id")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            observation["tool_error"] = f"{type(error).__name__}: {error}"
            observation["request_id"] = f"transport-failure-{len(self.calls):03d}"
        return observation

