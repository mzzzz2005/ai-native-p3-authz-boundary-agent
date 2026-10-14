"""Deployment policy for the teaching-document service.

The service reads this file at start-up. It is deployment configuration, not
something the testing agent inspects: the agent only ever sees HTTP responses.
That is what makes a misconfiguration a real finding rather than a scripted one.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class User:
    name: str
    token: str
    state: str


@dataclass(frozen=True)
class Document:
    doc_id: str
    owner: str
    body: str
    attachment: str


class Policy:
    def __init__(self, raw: dict, fingerprint: str, source: str) -> None:
        self._raw = raw
        self.fingerprint = fingerprint
        self.source = source
        self.service_id = raw["service_id"]
        self.version = raw["version"]
        self.users = {
            name: User(name=name, token=item["token"], state=item["state"])
            for name, item in raw["users"].items()
        }
        self.documents = {
            doc_id: Document(
                doc_id=doc_id,
                owner=item["owner"],
                body=item["body"],
                attachment=item["attachment"],
            )
            for doc_id, item in raw["documents"].items()
        }
        # Extra grants beyond ownership. Empty in a correct deployment.
        self.shared_with: dict[str, list[str]] = {
            doc_id: list(names) for doc_id, names in raw.get("shared_with", {}).items()
        }
        # A narrower grant that covers the document body but not its attachment.
        # This models the common real defect where only one endpoint received the
        # permission check.
        self.shared_body_only: dict[str, list[str]] = {
            doc_id: list(names)
            for doc_id, names in raw.get("shared_body_only", {}).items()
        }
        self._by_token = {user.token: user for user in self.users.values()}

    @classmethod
    def load(cls, path: str | Path) -> Policy:
        policy_path = Path(path)
        text = policy_path.read_text(encoding="utf-8")
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as error:
            raise PolicyError(f"policy is not valid JSON: {error}")
        return cls(
            raw,
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
            policy_path.as_posix(),
        )

    def user_for_token(self, token: str | None) -> User | None:
        if not token:
            return None
        return self._by_token.get(token)

    def may_read(self, user: User, doc_id: str, *, attachment: bool = False) -> bool:
        document = self.documents.get(doc_id)
        if document is None or user.state != "active":
            return False
        if document.owner == user.name:
            return True
        if user.name in self.shared_with.get(doc_id, []):
            return True
        if not attachment and user.name in self.shared_body_only.get(doc_id, []):
            return True
        return False

    def describe(self) -> dict:
        return {
            "service_id": self.service_id,
            "version": self.version,
            "fingerprint": self.fingerprint,
            "shared_with": self.shared_with,
            "shared_body_only": self.shared_body_only,
        }

