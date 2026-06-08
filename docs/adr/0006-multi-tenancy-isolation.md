# ADR-0006: Shared-database multi-tenancy with isolation enforced at the repository layer

- **Status:** Accepted
- **Date:** 2026-06-08
- **Deciders:** Engineering

## Context

Organizations are tenants and **must never access each other's data** — assessments,
documents, reports, recommendations are all confidential. A cross-tenant leak is the
single worst failure this product can have. We need an isolation model that is
strong, simple to operate at this scale, and hard to get wrong in day-to-day code.

## Decision

**Shared database, shared schema, `organization_id` on every tenant-owned table,
with isolation enforced centrally in the repository layer** — backed by Postgres
Row-Level Security as defense-in-depth.

- The tenant id is **derived from the authenticated principal**, never read from the
  request body, path, or query in a way the client controls. A `TenantContext` is
  established by an auth dependency and injected (ADR-0002).
- **Every repository query is scoped to the tenant context.** Tenant filtering lives
  in a base repository, not sprinkled across services — a developer cannot "forget"
  the `WHERE organization_id = ...` because they never write it by hand.
- **Defense-in-depth: PostgreSQL Row-Level Security** policies on tenant-owned tables
  keyed off a session variable set per request/transaction. Even a bug in a repository
  cannot return another tenant's rows, because the database itself refuses.
- Consultants and admins are the deliberate cross-tenant principals; their access is
  an *explicit, audited* widening of the tenant scope, granted by RBAC (ADR-0007),
  not an absence of scoping.

## Alternatives considered

- **Database-per-tenant.** Strongest isolation, but heavy to operate (migrations,
  connection sprawl, cross-tenant consultant queries become hard) and unjustified at
  this scale. Violates "don't over-engineer." Rejected; revisitable if a tenant
  demands physical isolation.
- **Schema-per-tenant.** Middle ground, still operationally noisy and awkward for the
  consultant/admin cross-tenant views that are core to the product. Rejected.
- **App-layer filtering only, no RLS.** One forgotten filter = a breach. Too fragile
  for the highest-severity risk in the system. Rejected in favor of belt-and-braces.

## Consequences

- **+** Simple to operate; one schema, one migration path.
- **+** Two independent layers must both fail to leak data (repository scoping *and*
  RLS). The most dangerous failure is the most defended.
- **+** Cross-tenant consultant/admin access is a clean, audited widening, not a hole.
- **−** RLS adds query-planning considerations and a small operational learning curve.
  Accepted given the stakes.
- **−** Shared infrastructure means noisy-neighbor and shared-blast-radius concerns;
  mitigated operationally (quotas, monitoring) and revisited only if a tenant's
  contract requires physical separation.
- This decision is reflected in the schema (ubiquitous `organization_id`) and is a
  primary line item in the threat model (tenant isolation tests are mandatory).
