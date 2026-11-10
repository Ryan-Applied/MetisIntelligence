"""Deterministic secret/PII detection and redaction.

Design:
  * A set of named detectors (regex), each redacting either the whole match or
    a specific capture group (so `api_key = "..."` keeps the key name visible).
  * Optional high-entropy fallback to catch unknown long tokens.
  * `redact()` never returns the matched secret; `Finding` stores only the
    span, category and a short fingerprint (sha256 prefix) for dedup/audit.

This is intentionally conservative on the built-in set: precision over recall,
with entropy scanning available (opt-in) for ingestion of untrusted logs.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional, Pattern


@dataclass(frozen=True)
class _Detector:
    category: str
    pattern: Pattern[str]
    redact_group: Optional[int] = None  # None => redact whole match


# Order matters only for reporting; spans are de-overlapped before redaction.
_DETECTORS: list[_Detector] = [
    _Detector("private_key", re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"
        r".*?-----END (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
        re.DOTALL)),
    _Detector("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    _Detector("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    _Detector("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    _Detector("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    _Detector("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    _Detector("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    _Detector("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    _Detector("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
    _Detector("bearer_token", re.compile(r"[Bb]earer\s+([A-Za-z0-9._-]{16,})"), redact_group=1),
    # Credentials embedded in a URL: scheme://user:password@host
    _Detector("url_credentials", re.compile(r"://[^/\s:@]+:([^/\s:@]+)@"), redact_group=1),
    # Generic "key = value" / "key: value" assignments for secret-ish names.
    _Detector("assigned_secret", re.compile(
        r"(?i)\b(?:api[_-]?key|secret(?:[_-]?key)?|access[_-]?token|auth[_-]?token|"
        r"password|passwd|pwd|client[_-]?secret)\b\s*[=:]\s*['\"]?([^'\"\s,;]{6,})"),
        redact_group=1),
    # PII: email addresses.
    _Detector("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]

_ENTROPY_TOKEN = re.compile(r"\b[A-Za-z0-9+/=_-]{20,}\b")

# When spans overlap, the higher-priority category wins (secrets beat PII).
_PRIORITY: dict[str, int] = {
    "high_entropy": 1,
    "email": 1,
    "assigned_secret": 5,
    "url_credentials": 6,
}
_DEFAULT_PRIORITY = 7  # concrete secret formats (keys, tokens, jwt, private_key)


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Finding:
    category: str
    start: int
    end: int
    fingerprint: str  # sha256 prefix of the matched secret — NOT the secret


@dataclass
class RedactionResult:
    text: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings


class Redactor:
    def __init__(
        self,
        *,
        redact_emails: bool = True,
        entropy_scan: bool = False,
        entropy_threshold: float = 4.0,
        placeholder: str = "[REDACTED:{category}]",
    ) -> None:
        self.redact_emails = redact_emails
        self.entropy_scan = entropy_scan
        self.entropy_threshold = entropy_threshold
        self.placeholder = placeholder

    def _spans(self, text: str) -> list[tuple[int, int, str]]:
        spans: list[tuple[int, int, str]] = []
        for det in _DETECTORS:
            if det.category == "email" and not self.redact_emails:
                continue
            for m in det.pattern.finditer(text):
                if det.redact_group is not None:
                    start, end = m.span(det.redact_group)
                else:
                    start, end = m.span()
                if end > start:
                    spans.append((start, end, det.category))
        if self.entropy_scan:
            for m in _ENTROPY_TOKEN.finditer(text):
                if shannon_entropy(m.group()) >= self.entropy_threshold:
                    spans.append((m.start(), m.end(), "high_entropy"))
        return spans

    @staticmethod
    def _dedupe(spans: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
        # Keep non-overlapping spans. On overlap prefer earlier start, then the
        # higher-priority category (a secret beats an overlapping email), then
        # the longer span. Result is returned in document order.
        def rank(cat: str) -> int:
            return _PRIORITY.get(cat, _DEFAULT_PRIORITY)

        ordered = sorted(
            spans, key=lambda s: (s[0], -rank(s[2]), -(s[1] - s[0]))
        )
        chosen: list[tuple[int, int, str]] = []
        last_end = -1
        for start, end, cat in ordered:
            if start >= last_end:
                chosen.append((start, end, cat))
                last_end = end
        return sorted(chosen, key=lambda s: s[0])

    def scan(self, text: str) -> list[Finding]:
        findings = []
        for start, end, cat in self._dedupe(self._spans(text)):
            findings.append(Finding(cat, start, end, _fingerprint(text[start:end])))
        return findings

    def redact(self, text: str) -> RedactionResult:
        findings = self.scan(text)
        if not findings:
            return RedactionResult(text=text, findings=[])
        out: list[str] = []
        cursor = 0
        for f in findings:
            out.append(text[cursor:f.start])
            out.append(self.placeholder.format(category=f.category))
            cursor = f.end
        out.append(text[cursor:])
        return RedactionResult(text="".join(out), findings=findings)


# Module-level convenience using default settings.
_default = Redactor()


def scan(text: str) -> list[Finding]:
    return _default.scan(text)


def redact(text: str) -> RedactionResult:
    return _default.redact(text)
