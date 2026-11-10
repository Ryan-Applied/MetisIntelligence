# Context Intelligence — Program Plan

**Owner:** Ryan (ryan@appliedcomputing.com)
**Status:** Draft v0.1 · 2026-11-10
**Scope decisions locked for this draft:**
- Initial ingestion = **Ryan's own Claude Code + Codex history**, piloted against one repo (`cyber-skill-extractor`), before any team or org-wide collection.
- Metis offensive-security edition = **one codebase, hard-isolated deployment** (feature-flagged "offsec edition"), *not* a divergent second repo.

---

## 0. What we are building

**Context Intelligence (CI)** is a standalone continuous-learning service for AI agents. It captures what agents discover, keeps what proves useful, spots recurring failures, and improves the context handed to every subsequent run — without retraining any model. It improves agents by changing the *information available at inference time*.

It ships in two editions from **one codebase**:

| Edition | Audience | Deployment | Data sensitivity |
|---|---|---|---|
| **CI Core** | AC dev fleet: Claude Code, Codex, Metis, Nexus | Shared AC environment | Internal / proprietary |
| **CI‑Metis** (offsec edition) | Metis offensive-security engagements only | Separate, hard-isolated environment, own keys/storage/tenancy | Per-client, highly sensitive |

The two editions share the engine (ingestion, memory store, retrieval, Librarian, graph) but are **operationally isolated**: separate databases, separate KMS keys, separate network boundaries, and a memory namespace that can never cross from CI‑Metis into CI Core.

### Guiding principles (non-negotiable)
1. **Separate memory from agents.** Agents *propose and consume*; a governed intelligence layer decides what is retained, how it's organised, when it's retrieved, and whether it's still trustworthy.
2. **All tool output is untrusted evidence until validated.** A transcript, README, or tool result can carry prompt-injection. Nothing an agent "discovers" becomes fleet-wide guidance without validation.
3. **Prove it before trusting it.** No autonomous fleet-wide instruction rewrites until the evaluation harness shows real gains.
4. **Isolation by default.** Project/client memory never leaks across unrelated repos or clients. Promotion upward requires validation; inheritance downward requires permission.
5. **Filesystem is the agent-facing abstraction.** Human-readable Markdown + Git on top; Postgres/pgvector/graph underneath as implementation detail.

---

## 1. The two things that make this plan different from the design notes

The architecture in the source notes is sound. This plan sequences it for delivery and adds the two pieces you asked for:

1. **Historical Experience Ingestion goes first.** Rather than launch with an empty store, we bootstrap from real AC development activity. Pilot = *your* history so we hit zero governance blockers and prove the pipeline, then expand on a governance gate.
2. **The Metis offsec fork is designed in from Phase 0**, not bolted on. Tenant isolation, engagement-scoped tokens, and the observed → hypothesis → verified memory classification are foundational for CI‑Metis, and we reuse the isolation/safety discipline already present in the `offsec-eng` toolchain (scope-safety-gate, tenant-isolation-gate).

---

## 2. Governance & data protection — the gate on everything

Ingesting developer transcripts touches credentials, customer data, proprietary code, and private conversation. This is explicitly in scope of AC's Data Protection and Privacy Policy (**ACT‑DPP‑POL‑001**). Governance is a **hard gate**, not a workstream to catch up later.

| Gate | When | What it unblocks |
|---|---|---|
| **G0 — Pilot (self) OK** | Before Phase 1 | Ingesting your own history on your own machine. Lightweight: personal data, single data subject, local processing. |
| **G1 — Team opt-in + DPIA-lite** | Before any second person's data | A named team opts in with transparent collection policy. |
| **G2 — Org-wide DPIA + sign-off** | Before fleet collection | Full DPIA, consent model, identity mapping, isolation, retention/deletion, audit. Contact privacy@appliedcomputing.com. |
| **G3 — Client-data handling (CI‑Metis)** | Before any engagement data enters CI‑Metis | Per-client isolation proven, engagement-scoped access, retention/deletion per client contract. |

**Controls required at every gate:**
- Local secret detection + redaction *before* anything leaves the workstation.
- Read-only ingestion — never execute a historical command or instruction.
- Quarantine untrusted transcript content; human review before any org-wide promotion.
- Encryption at rest + in transit, retention limits, deletion workflow, immutable audit log.
- Project/client isolation enforced in storage and in the "dreaming" (consolidation) jobs.

> Note: there is a documented Codex behaviour where local transcripts get recursively re-ingested into context. This is exactly why raw logs are processed by a **separate ingestion service**, never loaded wholesale into a live agent's working context.

---

## 3. Memory model (shared by both editions)

### 3.1 Five layers, not one vector DB
| Layer | Answers | Store |
|---|---|---|
| Working | "What am I doing right now?" | Redis / runtime |
| Episodic | "Have we hit this failure before?" | PostgreSQL |
| Semantic | "How does this system actually work?" | PostgreSQL + pgvector |
| Procedural | "What's the verified process?" | Markdown + Git |
| Relational | "What else does this change affect?" | Graph (Neo4j, added when it earns its place) |

### 3.2 Memory contract (every memory is a first-class object)
Each memory carries: `id`, `type`, hierarchical `scope` (org → project → repo → agent/session), `title`, `content`, `source` (session + evidence ids), `validation` (status/method/time), `lifecycle` (status/version/expiry), plus `confidence`, `applicability`, `supersedes`, `sensitivity`, `content_hash`, `outcome_metrics`.

### 3.3 Agent-facing filesystem
```
/memory
├── organisation/        (shared policies, verified knowledge)
├── projects/
│   ├── metis/  nexus/  cyber-skill-extractor/
│   │   ├── MEMORY.md    (concise index, not the knowledge itself)
│   │   ├── architecture/  procedures/  failures/  decisions/
├── skills/
└── sessions/            (agent/session-private experience)
```
`MEMORY.md` is a lightweight index (progressive disclosure): load the index first, fetch detail on demand.

### 3.4 Integrity & concurrency
Updates are an atomic **compare-and-swap** in the storage layer (check `content_hash`/version under lock, reject on mismatch, force reread). Agents decide *what* to propose; infrastructure deterministically enforces *how* it commits.

### 3.5 Classification (critical for CI‑Metis)
Every extracted experience is tagged **observed → inferred → corroborated → verified**, each with explicit evidence requirements. An agent's *interpretation* of a security finding never silently becomes a trusted fact just because it was written to memory.

---

## 4. Phased roadmap

Estimates are indicative engineering effort for a focused build, not commitments. CI Core and CI‑Metis share phases; CI‑Metis-specific work is called out.

### Phase 0 — Foundations & governance (Weeks 0–2)
- G0 sign-off for self-pilot.
- Monorepo + `docker compose` dev stack (Postgres + pgvector, Redis, MinIO, FastAPI gateway, Next.js UI).
- Postgres schema + migrations; the memory contract as a typed model.
- Secret-detection/redaction library (used by every ingestion path).
- Hierarchical scope + permission model stubbed; **CI‑Metis namespace + isolation boundary defined now**.
- **Exit:** compose stack boots; an empty, scoped memory store exists; redaction library passes tests.

### Phase 1 — Historical Experience Ingestion ("the leg up") (Weeks 1–4)
The starting deliverable you asked for.
- **Read-only inventory** collectors: `~/.claude/projects/*.jsonl`, `~/.codex/sessions` + `archived_sessions` (`.jsonl`/`.jsonl.zst`). Version-aware, tolerant of malformed/partial records.
- Normalise to a common **event schema** (tool calls, errors, outcomes, file changes, tokens, commit refs).
- **Two-pass extraction:** (A) deterministic parse/dedup/cluster; (B) selective LLM only on high-value clusters (repeated failures, long debugging runs, successful fixes, contradictory instructions).
- **Git correlation:** tie "I fixed X" claims to actual commit/diff/test/CI outcome → evidence chain → classification.
- Evidence store in MinIO/S3; redaction before storage.
- **Exit:** a reviewable candidate memory pack for `cyber-skill-extractor`, every memory linked to source evidence.

### Phase 2 — Memory store + retrieval gateway (Weeks 3–6)
- Memory filesystem abstraction over Git + Postgres; `MEMORY.md` indexes.
- **Selective retrieval / context packs:** hybrid keyword + vector, scope/ACL filters *before* retrieval, rerank by relevance × validation, de-dup/contradiction removal, pack to token budget, record what was retrieved/used.
  - Scoring heuristic to tune: `S = w1·relevance + w2·graph-proximity + w3·verification + w4·freshness − w5·cost`.
- **MCP server** so agents don't know how memory is stored: `context.get_task_pack`, `context.search`, `context.get_repository_map`, `memory.propose/get/list/report_outcome`, `session.record_event/complete`.
- Atomic CAS updates; Next.js **Memory Review** UI (approve/reject/edit/rollback with evidence).
- **Exit:** Claude Code + Codex connect via MCP and get useful, cited context for a real task; proposals reviewable in UI.

### Phase 3 — The Librarian (asynchronous "dreaming") (Weeks 6–9)
- Runs separately from task execution; **permission-aware** (only transcripts authorised for the destination scope; scoped service identity; re-validate permissions before promotion).
- Orchestrator fans out to specialised workers: **Failure Analyst, Knowledge-Gap Analyst, Tool Analyst, Memory Critic, Procedure Miner, Security Reviewer** (poisoning / sensitive-data / scope violations).
- Learns from **tool execution**, not just conversation (structured events: tool, exit code, error class, duration, commit, memories used).
- Evidence-backed, versioned proposals with transcript links + recurrence stats + diff; partial accept; rollback; canary.
- **Exit:** Librarian turns the Phase-1 history into ranked, evidence-backed proposals a human can approve/reject.

### Phase 4 — Repository & memory-graph intelligence (Weeks 9–12)
- Tree-sitter symbol extraction, dependency/call graph, incremental Git-aware indexing.
- Graph-assisted retrieval; **memory provenance** linking memories to the code they depend on.
- **Event-driven revalidation:** when a file/symbol changes, flag every memory that depends on it for recheck (not just scheduled dreaming).
- **Exit:** affected-component context packs; stale memories auto-flagged on relevant commits.

### Phase 5 — Evaluation harness (parallel from Phase 2, continuous)
The part we don't compromise on.
- Configs: **Baseline** (repo instructions only) · **Retrieval** (task-specific knowledge) · **Full memory** (retrieval + validated cross-session learning).
- Held-out task suite, repeated trials, controlled model/tool settings.
- Metrics: completion rate, time, token cost, repeated-error rate, correctness, security-policy compliance, context relevance.
- **Learning ROI:** `net benefit = avoided execution cost − learning infrastructure cost`; track sessions-to-payback per repo.
- **Exit:** a repeatable benchmark that says whether a memory set actually helps.

### Phase 6 — Fleet intelligence & governance (Week 12+)
- Gated by G1/G2. Multi-agent learning analytics, cross-project governance, canary rollout of shared memories, regression benchmarking, Metis/Nexus orchestration integration.

---

## 5. The Metis offensive-security edition (CI‑Metis)

A parallel track that reuses the engine under a hard isolation boundary. Same codebase; an "offsec edition" selected by config/feature flags and deployed separately.

### 5.1 Why it must be isolated
CI‑Metis holds attack techniques, exploit chains, verified attack-path evidence, and **per-client engagement data**. A leak between clients, or from CI‑Metis into CI Core, is a contractual and legal breach. Isolation is the product requirement, not a nice-to-have.

### 5.2 Isolation controls (foundational, from Phase 0)
- Separate deployment, database, object store, and **KMS keys** per environment; per-client KMS scoping within CI‑Metis.
- Network isolation between engagement sandboxes.
- **Engagement-scoped tokens**: tenant id + target allowlist + expiry, verified before any memory read/write tied to an engagement — mirrors the `offsec-eng` scope-safety / tenant-isolation gate discipline already in this environment.
- One-way boundary: CI‑Metis may *inherit* non-sensitive org policy from CI Core; nothing flows the other way.

### 5.3 Reuse what already exists
- **`cyber-skill-library`** + **`library-graph`** MCP servers → structured source of offensive techniques, tools, detections, and relationships; feed the relational/semantic layers rather than rebuilding.
- **`offsec-eng` agents/skills** (technique-architect, orchestration-engineer, scope-safety-gate, tenant-isolation-gate) → the autonomous loop and merge gates CI‑Metis learns from and protects.
- Metis integration is **direct to the orchestrator/task queue**, so the platform can correlate memory with agent, task, target, outcome, and evidence.

### 5.4 Offsec-specific Librarian priorities
Configure workers to weight: reliability of techniques/tools, verified attack-path evidence, misconfigured tooling, and recurring engagement failures — distinct from CI Core's build-failure/knowledge-gap focus. **Verified** classification is mandatory before any technique becomes trusted guidance.

### 5.5 CI‑Metis milestones (offset ~2 weeks behind Core)
- M0: isolation boundary + engagement-token model (rides Phase 0).
- M1: ingest a single sanitised Metis engagement's history behind G3.
- M2: offsec retrieval pack into the Metis orchestrator.
- M3: offsec Librarian workers + security-reviewer gate.
- M4: per-engagement eval (did memory improve attack-path success / reduce wasted steps?).

---

## 6. Technology stack
FastAPI (Python) backend · PostgreSQL (sessions/memory/provenance/permissions) · pgvector (semantic) · Postgres FTS (exact terms/symbols/errors) · Redis + Dramatiq (async extraction/consolidation) · MinIO/S3 (evidence) · Git (human-readable procedures) · Neo4j (added in Phase 4) · MCP server (agent integration) · Next.js + shadcn/ui (management UI). **Start with Postgres + pgvector; add Neo4j only when graph traversal demonstrably improves retrieval.**

## 7. Management UI — five views
Overview · Knowledge Explorer · Session Intelligence · Memory Review · Evaluation Lab. (CI‑Metis runs the same UI inside its isolated environment.)

---

## 8. Decisions still needed
| # | Decision | Needed by | Recommendation |
|---|---|---|---|
| D1 | Deployment target after local Docker | Phase 2 | AWS (ECS/serverless); `offsec-eng:aws-platform-engineer` + `aws-dev-toolkit` already available |
| D2 | DPIA owner + timeline for G1/G2 | Before team expansion | Engage privacy@appliedcomputing.com during Phase 1 |
| D3 | Which Metis engagement is the sanitised M1 pilot | CI‑Metis M1 | A closed engagement with client deletion consent |
| D4 | Pilot eval task suite for `cyber-skill-extractor` | Phase 2 | 10–20 held-out real tasks from your own history |
| D5 | LLM provider(s) for extraction/consolidation | Phase 1 | Default to latest Claude (Opus/Sonnet 5.x) for extraction/critique |

## 9. Top risks
1. **Privacy breach / policy non-compliance** → governance gates G0–G3; redaction-before-storage; read-only.
2. **Memory poisoning via malicious transcript/README** → untrusted-until-validated; quarantine; human review before org promotion.
3. **Cross-client leak in CI‑Metis** → hard isolation + engagement-scoped tokens + security-reviewer worker.
4. **"More memory ≠ better agents"** → evaluation harness is a first-class deliverable, not an afterthought.
5. **Over-engineering (four databases before value)** → Postgres+pgvector first; graph and fleet features gated on proven gains.

## 10. Immediate next steps (first two weeks)
1. Confirm G0 self-pilot and D1/D2 owners.
2. Stand up the Phase 0 `docker compose` stack + Postgres schema + redaction library.
3. Build the read-only inventory collectors and run them over *your* `~/.claude` and `~/.codex` histories (counts only, no content exposure first).
4. Normalise one project's sessions (`cyber-skill-extractor`) to the event schema and correlate with its Git history.
5. Produce the first candidate memory pack for review.

> **North star:** the hundredth agent run benefits from the lessons of the previous ninety-nine, without inheriting their mistakes — and the Metis run does so without ever leaking one client's engagement into another.
