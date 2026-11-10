"""Hierarchical scope and the edition isolation boundary.

Scope hierarchy (broad -> narrow):
    organisation > project > repository > agent

Rules enforced here:
  * Edition is a HARD boundary. A reader in one edition can never see memory
    from the other edition, regardless of scope. (Reinforces the primary
    control: CI Core and CI-Metis run as separate deployments.)
  * CI-Metis memory is tenant-scoped. A reader can only see memory for its
    own tenant (client/engagement).
  * Within an edition+tenant, a narrower reader inherits broader memory
    (org-level policy is visible to a repo-scoped task), but not vice versa.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .enums import Edition


class ScopeError(ValueError):
    """Raised when a scope violates the edition/tenant invariants."""


@dataclass(frozen=True)
class Scope:
    edition: Edition
    organisation: str = "applied-computing"
    project: Optional[str] = None
    repository: Optional[str] = None
    agent: Optional[str] = None
    tenant_id: Optional[str] = None

    def __post_init__(self) -> None:
        self.validate()

    # -- invariants ---------------------------------------------------------
    def validate(self) -> None:
        is_metis = self.edition == Edition.METIS
        has_tenant = self.tenant_id is not None
        if is_metis and not has_tenant:
            raise ScopeError("CI-Metis scope requires a tenant_id")
        if not is_metis and has_tenant:
            raise ScopeError("CI Core scope must not carry a tenant_id")
        # A narrower level cannot be set without its parent.
        if self.repository and not self.project:
            raise ScopeError("repository scope requires a project")
        if self.agent and not self.repository and not self.project:
            raise ScopeError("agent scope requires at least a project")

    # -- hierarchy ----------------------------------------------------------
    def contains(self, other: "Scope") -> bool:
        """True if `self` is the same or a BROADER scope than `other`
        within the same edition and tenant. A broader scope's memory is
        inheritable by a narrower reader."""
        if self.edition != other.edition:
            return False
        if self.tenant_id != other.tenant_id:
            return False
        if self.organisation != other.organisation:
            return False
        for mine, theirs in (
            (self.project, other.project),
            (self.repository, other.repository),
            (self.agent, other.agent),
        ):
            if mine is None:
                continue  # self unconstrained at this level => broader
            if mine != theirs:
                return False
        return True

    # -- the isolation check ------------------------------------------------
    def can_read(self, memory_scope: "Scope") -> bool:
        """Can a reader at `self` read memory stored at `memory_scope`?

        Enforces edition isolation and tenant isolation, then allows
        downward inheritance (reader narrower-or-equal to the memory's scope).
        """
        if self.edition != memory_scope.edition:
            return False  # HARD boundary — never cross editions
        if self.edition == Edition.METIS and self.tenant_id != memory_scope.tenant_id:
            return False  # tenant isolation within CI-Metis
        # The memory's scope must contain (be broader-or-equal to) the reader.
        return memory_scope.contains(self)
