-- 0001_extensions.sql
-- Context Intelligence — required Postgres extensions.
-- Applied first (lexical order) on an empty data volume.

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector: semantic layer embeddings
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- trigram index support for FTS/fuzzy
