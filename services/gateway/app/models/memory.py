"""The memory contract — every memory carries identity, scope, evidence,
validation and lifecycle metadata.

Pure-stdlib dataclass form so it is importable by the gateway, the ingestion
pipeline and tests without third-party dependencies. A Pydantic request/response
layer is added on top in the API module (Phase 2).
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .enums import (
    Classification,
    LifecycleStatus,
    MemoryType,
    Sensitivity,
    ValidationStatus,
)
from .scope import Scope


def compute_content_hash(content: str) -> str:
    """Stable integrity/dedup hash of a memory's content."""
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class EvidenceRef:
    session_id: str
    event_id: str
    note: Optional[str] = None


@dataclass
class Memory:
    # identity
    type: MemoryType
    title: str
    content: str
    scope: Scope

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_hash: str = ""

    # trust & classification
    classification: Classification = Classification.OBSERVED
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED
    validation_method: Optional[str] = None
    validated_at: Optional[datetime] = None
    confidence: float = 0.0

    # applicability & sensitivity
    applicability: dict[str, Any] = field(default_factory=dict)
    sensitivity: Sensitivity = Sensitivity.INTERNAL

    # lifecycle & versioning (optimistic concurrency via `version`)
    lifecycle_status: LifecycleStatus = LifecycleStatus.PROPOSED
    version: int = 1
    supersedes: Optional[str] = None
    expires_at: Optional[datetime] = None

    # provenance & outcomes
    evidence: list[EvidenceRef] = field(default_factory=list)
    outcome_metrics: dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = compute_content_hash(self.content)
        self._check_invariants()

    def _check_invariants(self) -> None:
        if not self.title.strip():
            raise ValueError("memory.title must not be empty")
        if not self.content.strip():
            raise ValueError("memory.content must not be empty")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("memory.confidence must be in [0, 1]")
        # Verified classification must be backed by a verified validation.
        if (
            self.classification == Classification.VERIFIED
            and self.validation_status != ValidationStatus.VERIFIED
        ):
            raise ValueError(
                "classification 'verified' requires validation_status 'verified'"
            )

    # -- behaviour ----------------------------------------------------------
    def with_content(self, new_content: str) -> "Memory":
        """Return a bumped-version copy with recomputed hash (CAS-friendly)."""
        self.content = new_content
        self.content_hash = compute_content_hash(new_content)
        self.version += 1
        self.updated_at = _now()
        return self

    def readable_by(self, reader_scope: Scope) -> bool:
        return reader_scope.can_read(self.scope)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "edition": self.scope.edition.value,
            "scope": {
                "organisation": self.scope.organisation,
                "project": self.scope.project,
                "repository": self.scope.repository,
                "agent": self.scope.agent,
                "tenant_id": self.scope.tenant_id,
            },
            "title": self.title,
            "content": self.content,
            "content_hash": self.content_hash,
            "classification": self.classification.value,
            "validation_status": self.validation_status.value,
            "validation_method": self.validation_method,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "confidence": self.confidence,
            "applicability": self.applicability,
            "sensitivity": self.sensitivity.value,
            "lifecycle_status": self.lifecycle_status.value,
            "version": self.version,
            "supersedes": self.supersedes,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "evidence": [
                {"session_id": e.session_id, "event_id": e.event_id, "note": e.note}
                for e in self.evidence
            ],
            "outcome_metrics": self.outcome_metrics,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
