"""HTTP surface. Authorization is decided here, on the server side."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from .policy import Policy


def _send(handler: BaseHTTPRequestHandler, status: int, body: str, request_id: str) -> None:
    payload = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("X-Request-Id", request_id)
    handler.end_headers()
    handler.wfile.write(payload)


class TeachingDocsHandler(BaseHTTPRequestHandler):
    server_version = "TeachingDocs/0.1"
    protocol_version = "HTTP/1.1"

    # The handler never logs to stderr; evidence is collected by the caller.
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    @property
    def policy(self) -> Policy:
        return self.server.policy  # type: ignore[attr-defined]

    def _request_id(self) -> str:
        index = self.server.next_request_index()  # type: ignore[attr-defined]
        return f"teaching-svc-{index:03d}"

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        request_id = self._request_id()
        path = self.path.split("?", 1)[0].rstrip("/")
        parts = [part for part in path.split("/") if part]

        if len(parts) == 2 and parts[0] == "documents":
            doc_id, want_attachment = parts[1], False
        elif len(parts) == 3 and parts[0] == "documents" and parts[2] == "attachment":
            doc_id, want_attachment = parts[1], True
        else:
            _send(self, 404, "not found", request_id)
            return

        document = self.policy.documents.get(doc_id)
        if document is None:
            _send(self, 404, "not found", request_id)
            return

        header = self.headers.get("Authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else None
        user = self.policy.user_for_token(token)
        if user is None:
            # No credential, unknown credential, or revoked credential.
            _send(self, 401, "authentication required", request_id)
            return
        if user.state != "active":
            _send(self, 401, "credential is no longer valid", request_id)
            return
        if not self.policy.may_read(user, doc_id, attachment=want_attachment):
            _send(self, 403, "forbidden", request_id)
            return

        _send(
            self,
            200,
            document.attachment if want_attachment else document.body,
            request_id,
        )

