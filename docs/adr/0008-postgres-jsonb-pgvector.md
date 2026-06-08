# ADR-0008: PostgreSQL with JSONB for dynamic schemas and pgvector reserved for RAG

- **Status:** Accepted
- **Date:** 2026-06-08
- **Deciders:** Engineering

## Context

The data has three different shapes living together:

1. **Stable relational data** — users, orgs, rules, reports, audit. Strong
   constraints and joins matter.
2. **Genuinely dynamic data** — assessment definitions and responses vary per
   template and per question type; consultants author new question types.
3. **Future vector data** — RAG, semantic search over prior assessments, and memory
   are named extension points (the brief: design them, don't build them).

We want one boring, well-understood datastore, not a polyglot zoo we have to operate.

## Decision

**PostgreSQL as the single primary datastore**, using:

- **Relational columns** for everything with a stable shape and real constraints
  (the bulk of the schema). This keeps foreign keys, uniqueness, and joins doing the
  work they're good at.
- **JSONB** precisely where the schema is dynamic: `questions.config`,
  `responses.value`, `rules.condition`, `rules.recommendation_template`,
  `reports.content`, `evaluation_*` fixtures, and `*.metadata`. This avoids a
  migration per question type while keeping the stable identifiers (type, key,
  ordering, status) as real columns so rules and queries stay sane. We do **not**
  use JSONB as an excuse to avoid modeling — stable data is relational.
- **pgvector**: the extension is **enabled now** and a `knowledge_chunks(embedding
  vector(N))` table with an HNSW index is **designed but not created** (commented in
  the schema). The seam is reserved so RAG/semantic-search land without a datastore
  migration or a new piece of infrastructure.

## Alternatives considered

- **A dedicated vector database** (Pinecone, Weaviate, etc.) **now.** Another service
  to run and secure, for a feature we haven't built. pgvector keeps vectors next to
  the relational data (so they're tenant-scoped by the same `organization_id` and the
  same RLS) and is more than sufficient at this scale. Revisit only if vector volume
  outgrows Postgres. Adopting it now would violate "don't over-engineer."
- **A document database for the dynamic parts.** Splits the system of record, loses
  cross-entity constraints and transactions, and complicates tenant isolation.
  JSONB-in-Postgres gives the flexibility without the split. Rejected.
- **EAV tables for dynamic assessment data.** The classic "flexible schema" trap —
  unreadable queries, no typing, poor performance. JSONB is strictly better here.
  Rejected.

## Consequences

- **+** One datastore to run, back up, secure, and reason about. Vectors inherit the
  same tenant isolation as everything else.
- **+** Dynamic assessment schemas need no migrations; stable data keeps full
  relational integrity.
- **+** RAG/semantic-search are a future migration *within* Postgres, not a new
  system — the extension point is real and cheap.
- **−** JSONB columns trade some query ergonomics and schema-level validation for
  flexibility; we contain this by validating JSONB shapes with Pydantic at the
  service layer and indexing the JSONB paths that are queried.
- **−** pgvector at very large scale has known limits; acceptable now, and the cost of
  switching later is bounded because access goes through the repository layer.
