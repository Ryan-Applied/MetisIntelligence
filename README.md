# Context Intelligence

A continuous-learning / agent-memory platform for Applied Computing's AI agent
fleet (Claude Code, Codex, Metis, Nexus). It captures what agents discover,
retains what proves useful, and improves the context handed to every subsequent
run — without retraining any model.

- **Program plan:** [`PROJECT-PLAN.md`](PROJECT-PLAN.md)
- **Executive brief:** Claude Doc (shared separately)

Two editions from one codebase:

| Edition | Audience | Isolation |
|---|---|---|
| **CI Core** (`CI_EDITION=core`) | AC dev fleet | Internal |
| **CI-Metis** (`CI_EDITION=metis`) | Metis offensive-security engagements | Separate deployment, own keys/storage, per-tenant |

> The edition is a **hard boundary**. A process is pinned to one edition and
> must never serve the other. CI Core and CI-Metis run as separate deployments.

## Layout

```
.
├── docker-compose.yml        # Phase 0 data plane: Postgres+pgvector, Redis, MinIO
├── db/migrations/            # SQL schema (applied on first boot)
├── services/gateway/         # FastAPI context & memory gateway (MCP-aligned)
│   └── app/models/           # the memory contract (pure-stdlib dataclasses)
└── libs/redaction/           # deterministic secret & PII redaction (stdlib only)
```

## Quick start (Phase 0)

```bash
cp .env.example .env
docker compose up -d          # Postgres+pgvector, Redis, MinIO
docker compose ps
```

The schema in `db/migrations/` is applied automatically on first boot of an
empty Postgres volume.

## Running the tests

No services required — both suites are pure-stdlib + pytest:

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install pytest
(cd libs/redaction && python -m pytest -q)
(cd services/gateway && python -m pytest -q)
```

## Phase status

Phase 0 (foundations & governance) is in place: data-plane compose stack, the
memory-contract schema and typed models, the edition/tenant isolation boundary,
and the redaction library that gates every ingestion path. Phase 1 (historical
experience ingestion) is next — see `PROJECT-PLAN.md`.

## Safety

Nothing reaches the evidence or memory store before passing `libs/redaction`.
Ingestion is read-only; captured content is treated as untrusted until
validated. All work is governed under AC policy **ACT-DPP-POL-001**.
