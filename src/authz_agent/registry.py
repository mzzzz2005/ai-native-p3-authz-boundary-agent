"""Shared contract with the paired group: target, actors, resources, checks.

The two groups share this contract so results can be compared, but each group
implements its own controller, executor, evidence writer and experiment. No
implementation code is shared.
"""

from dataclasses import dataclass
from types import MappingProxyType

TARGET_ID = "teaching-docs-sim"
CONTRACT_VERSION = "p3-authz-contract-v0.1"
REGISTRY_VERSION = "p3-authz-registry-v0.1"


@dataclass(frozen=True)
class Check:
    actor: str
    resource: str
    expected_status: int
    canary: str
    prerequisite: str | None = None


CHECKS = MappingProxyType(
    {
        "T01": Check("A", "DA", 200, "TEACHING_DA"),
        "T02": Check("A", "DB", 403, "TEACHING_DB", "T01"),
        "T03": Check("anonymous", "DA", 401, "TEACHING_DA", "T01"),
        "T04": Check("A", "DB_attachment", 403, "TEACHING_DB_ATTACHMENT", "T06"),
        "T05": Check("revoked_A", "DA", 401, "TEACHING_DA", "T01"),
        "T06": Check("A", "DA_attachment", 200, "TEACHING_DA_ATTACHMENT"),
    }
)

# The scheduler order is deliberately the same as the paired group's fixed
# baseline so that coverage can be compared check by check.
ORDER = ("T01", "T06", "T02", "T04", "T03", "T05")

# Initial authorization state handed to the authorization source at run start.
INITIAL_AUTHORIZATION = {"A": "granted", "anonymous": "unknown", "revoked_A": "revoked"}

