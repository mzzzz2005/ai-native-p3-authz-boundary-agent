"""Start and stop the local service on an ephemeral 127.0.0.1 port."""

from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer
from itertools import count
from pathlib import Path

from .app import TeachingDocsHandler
from .policy import Policy


class TeachingDocsServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, policy: Policy) -> None:
        super().__init__(address, TeachingDocsHandler)
        self.policy = policy
        self._counter = count(1)
        self._lock = threading.Lock()

    def next_request_index(self) -> int:
        with self._lock:
            return next(self._counter)


class LocalTeachingDocsService:
    """Context manager. Binds to 127.0.0.1 only; never a public interface."""

    def __init__(self, policy_path: str | Path) -> None:
        self.policy = Policy.load(policy_path)
        self._server: TeachingDocsServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("service is not running")
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> str:
        if self._server is not None:
            raise RuntimeError("service is already running")
        self._server = TeachingDocsServer(("127.0.0.1", 0), self.policy)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.base_url

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def credentials(self) -> dict[str, str]:
        return {user.name: user.token for user in self.policy.users.values()}

    def revoke(self, user_name: str) -> None:
        """Teacher-side action: revoke a credential while the service is running."""
        user = self.policy.users[user_name]
        object.__setattr__(user, "state", "revoked")

    def __enter__(self) -> LocalTeachingDocsService:
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop()

