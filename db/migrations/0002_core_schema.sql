-- 0002_core_schema.sql
-- Context Intelligence — core memory-contract schema (Phase 0).
--
-- Design notes:
--  * CI Core and CI-Metis run as SEPARATE deployments (separate DB + keys).
--    The `edition` column and `tenant_id` are defence-in-depth, not the
--    primary isolation boundary. A single DB must never mix editions.
--  * Every memory carries identity, scope, evidence, validation, lifecycle.
--  * Hierarchical scope: organisation > project > repository > agent/session.
--  * Promotion UPWARD requires validation; inheritance DOWNWARD is a read concern.

-- ---------------------------------------------------------------------------
-- Enumerated types
-- ---------------------------------------------------------------------------
CREATE TYPE ci_edition          AS ENUM ('core', 'metis');
CREATE TYPE ci_memory_type      AS ENUM ('working', 'episodic', 'semantic', 'procedural', 'relational');
CREATE TYPE ci_classification   AS ENUM ('observed', 'inferred', 'corroborated', 'verified');
CREATE TYPE ci_validation_status AS ENUM ('unvalidated', 'in_review', 'verified', 'rejected', 'superseded');
CREATE TYPE ci_lifecycle_status AS ENUM ('proposed', 'active', 'deprecated', 'retired');
CREATE TYPE ci_sensitivity      AS ENUM ('public', 'internal', 'confidential', 'restricted');

-- Guard: in a single database, pin which edition it is allowed to hold.
-- CI-Metis deployments set ci.edition = 'metis' in postgresql.conf / env.
-- (Enforced in application layer + the session table CHECK below.)

-- ---------------------------------------------------------------------------
-- Sessions: a unit of agent execution (live or historically ingested)
-- ---------------------------------------------------------------------------
CREATE TABLE sessions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition       ci_edition  NOT NULL DEFAULT 'core',
    source        TEXT        NOT NULL,              -- 'claude-code' | 'codex' | 'metis' | ...
    external_id   TEXT,                              -- id from the source system, if any
    agent         TEXT,                              -- agent/worker identifier
    organisation  TEXT        NOT NULL DEFAULT 'applied-computing',
    project       TEXT,                              -- 'metis' | 'nexus' | 'cyber-skill-extractor' | ...
    repository    TEXT,
    tenant_id     TEXT,                              -- client/engagement id (CI-Metis isolation)
    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    metadata      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- CI-Metis sessions must carry a tenant; Core sessions must not.
    CONSTRAINT tenant_required_for_metis
        CHECK ((edition = 'metis') = (tenant_id IS NOT NULL))
);
CREATE INDEX idx_sessions_scope  ON sessions (edition, project, repository);
CREATE INDEX idx_sessions_tenant ON sessions (tenant_id) WHERE tenant_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Events: raw execution evidence (tool calls, errors, outcomes). Untrusted.
-- ---------------------------------------------------------------------------
CREATE TABLE events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    edition       ci_edition NOT NULL DEFAULT 'core',
    seq           INTEGER NOT NULL,                  -- order within the session
    event_type    TEXT NOT NULL,                     -- 'message' | 'tool_execution' | 'error' | ...
    tool          TEXT,
    exit_code     INTEGER,
    error_class   TEXT,
    duration_ms   INTEGER,
    repository_commit TEXT,
    outcome       TEXT,                              -- 'success' | 'failure' | null
    input_hash    TEXT,                              -- sha256 of (redacted) input
    redacted      BOOLEAN NOT NULL DEFAULT false,    -- true once scrubbed
    evidence_uri  TEXT,                              -- s3/minio pointer to full (redacted) payload
    payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, seq)
);
CREATE INDEX idx_events_session ON events (session_id);
CREATE INDEX idx_events_type    ON events (event_type);

-- ---------------------------------------------------------------------------
-- Memories: the memory contract
-- ---------------------------------------------------------------------------
CREATE TABLE memories (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition        ci_edition        NOT NULL DEFAULT 'core',
    type           ci_memory_type    NOT NULL,

    -- Hierarchical scope (any level may be null => broader scope)
    organisation   TEXT              NOT NULL DEFAULT 'applied-computing',
    project        TEXT,
    repository     TEXT,
    agent          TEXT,
    tenant_id      TEXT,                              -- CI-Metis client isolation

    title          TEXT              NOT NULL,
    content        TEXT              NOT NULL,
    content_hash   TEXT              NOT NULL,        -- integrity + dedup (sha256 of content)

    -- Trust & classification
    classification ci_classification NOT NULL DEFAULT 'observed',
    validation_status ci_validation_status NOT NULL DEFAULT 'unvalidated',
    validation_method TEXT,
    validated_at   TIMESTAMPTZ,
    confidence     REAL              NOT NULL DEFAULT 0.0,   -- 0..1, calibrated

    -- Applicability (files/services/versions/environments this applies to)
    applicability  JSONB             NOT NULL DEFAULT '{}'::jsonb,
    sensitivity    ci_sensitivity    NOT NULL DEFAULT 'internal',

    -- Lifecycle & versioning (optimistic concurrency via `version`)
    lifecycle_status ci_lifecycle_status NOT NULL DEFAULT 'proposed',
    version        INTEGER           NOT NULL DEFAULT 1,
    supersedes     UUID              REFERENCES memories(id),
    expires_at     TIMESTAMPTZ,

    -- Outcome metrics (does this memory actually help?)
    outcome_metrics JSONB            NOT NULL DEFAULT '{}'::jsonb,

    -- Semantic layer (nullable until embedded; dim configurable, 1536 default)
    embedding      vector(1536),

    -- Full-text search vector over title+content
    search_tsv     tsvector GENERATED ALWAYS AS (
                       to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,''))
                   ) STORED,

    created_at     TIMESTAMPTZ       NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ       NOT NULL DEFAULT now(),

    -- CI-Metis memories must carry a tenant; Core memories must not.
    CONSTRAINT mem_tenant_required_for_metis
        CHECK ((edition = 'metis') = (tenant_id IS NOT NULL)),
    -- Verified classification implies a validation record.
    CONSTRAINT mem_verified_has_validation
        CHECK (classification <> 'verified' OR validation_status = 'verified')
);
CREATE INDEX idx_memories_scope   ON memories (edition, project, repository);
CREATE INDEX idx_memories_type    ON memories (type);
CREATE INDEX idx_memories_tenant  ON memories (tenant_id) WHERE tenant_id IS NOT NULL;
CREATE INDEX idx_memories_tsv     ON memories USING gin (search_tsv);
CREATE INDEX idx_memories_hash    ON memories (content_hash);
-- ANN index over embeddings (cosine). Built now; fills as embeddings land.
CREATE INDEX idx_memories_embed   ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ---------------------------------------------------------------------------
-- Memory evidence: link a memory to the events that justify it
-- ---------------------------------------------------------------------------
CREATE TABLE memory_evidence (
    memory_id   UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    event_id    UUID NOT NULL REFERENCES events(id)  ON DELETE CASCADE,
    note        TEXT,
    PRIMARY KEY (memory_id, event_id)
);

-- ---------------------------------------------------------------------------
-- Memory audit: append-only history of changes (immutable record)
-- ---------------------------------------------------------------------------
CREATE TABLE memory_audit (
    id          BIGSERIAL PRIMARY KEY,
    memory_id   UUID NOT NULL,
    version     INTEGER NOT NULL,
    action      TEXT NOT NULL,                        -- 'created' | 'updated' | 'promoted' | 'rejected' | 'rolled_back'
    actor       TEXT NOT NULL,                        -- 'librarian' | user id | agent id
    content_hash TEXT,
    detail      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_memory_audit_memory ON memory_audit (memory_id);

-- updated_at trigger
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_memories_updated_at
    BEFORE UPDATE ON memories
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
