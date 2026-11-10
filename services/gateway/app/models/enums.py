"""Enumerated types for the Context Intelligence memory contract.

Mirrors the Postgres enums in db/migrations/0002_core_schema.sql.
Pure stdlib so these import with no third-party dependencies.
"""
from __future__ import annotations

from enum import Enum


class Edition(str, Enum):
    """Deployment edition. The hard isolation boundary of the platform."""

    CORE = "core"    # CI Core — AC dev fleet
    METIS = "metis"  # CI-Metis — offensive-security, hard-isolated, per-client


class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    RELATIONAL = "relational"


class Classification(str, Enum):
    """Evidence strength. Promotion requires explicit evidence per level."""

    OBSERVED = "observed"
    INFERRED = "inferred"
    CORROBORATED = "corroborated"
    VERIFIED = "verified"


class ValidationStatus(str, Enum):
    UNVALIDATED = "unvalidated"
    IN_REVIEW = "in_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class LifecycleStatus(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class Sensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
