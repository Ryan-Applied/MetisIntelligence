"""Context Intelligence — secret & PII redaction.

Used by every ingestion path. Nothing is written to the evidence store or the
memory store before it has been through `redact()`. Pure stdlib: no network,
no third-party dependencies, deterministic.
"""
from .scanner import (
    Finding,
    RedactionResult,
    Redactor,
    redact,
    scan,
    shannon_entropy,
)

__all__ = [
    "Finding",
    "RedactionResult",
    "Redactor",
    "redact",
    "scan",
    "shannon_entropy",
]
