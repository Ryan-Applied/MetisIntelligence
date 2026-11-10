"""Runtime configuration, loaded from environment.

Stdlib-only so it imports without third-party deps. The one setting that
matters most for safety is `edition`: a process is pinned to exactly one
edition and must never serve the other.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .models import Edition


@dataclass(frozen=True)
class Settings:
    edition: Edition
    postgres_dsn: str
    redis_url: str
    minio_endpoint: str
    minio_bucket: str
    gateway_host: str
    gateway_port: int
    log_level: str

    @staticmethod
    def from_env() -> "Settings":
        edition = Edition(os.environ.get("CI_EDITION", "core"))
        pg = (
            f"postgresql://{os.environ.get('POSTGRES_USER', 'ci')}:"
            f"{os.environ.get('POSTGRES_PASSWORD', 'ci_dev_password_change_me')}@"
            f"{os.environ.get('POSTGRES_HOST', 'localhost')}:"
            f"{os.environ.get('POSTGRES_PORT', '5432')}/"
            f"{os.environ.get('POSTGRES_DB', 'context_intelligence')}"
        )
        redis = (
            f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:"
            f"{os.environ.get('REDIS_PORT', '6379')}/0"
        )
        return Settings(
            edition=edition,
            postgres_dsn=pg,
            redis_url=redis,
            minio_endpoint=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
            minio_bucket=os.environ.get("MINIO_BUCKET", "ci-evidence"),
            gateway_host=os.environ.get("GATEWAY_HOST", "0.0.0.0"),
            gateway_port=int(os.environ.get("GATEWAY_PORT", "8000")),
            log_level=os.environ.get("GATEWAY_LOG_LEVEL", "info"),
        )
