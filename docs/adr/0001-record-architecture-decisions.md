# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-06-08
- **Deciders:** Engineering

## Context

This is a system where the *reasoning* behind decisions is as much a deliverable as
the code — a reviewer should be able to reconstruct why the system is shaped the way
it is. Decisions made implicitly in code review are lost; decisions made in a wiki
drift from the repo.

## Decision

We use **Architecture Decision Records** (Michael Nygard format) stored in
`docs/adr/`, versioned with the code. One ADR per significant, hard-to-reverse, or
contested decision. Each records context, the decision, and consequences (including
the bad ones).

A decision is "significant" if it constrains future work, costs meaningfully to
reverse, or a competent engineer might reasonably have chosen otherwise.

## Consequences

- **+** The "why" travels with the code and survives team turnover.
- **+** Reviewers evaluate decisions, not just diffs.
- **−** Small overhead per decision; we accept it and keep ADRs short.
- ADRs are immutable once Accepted. A reversal is a *new* ADR that supersedes the old
  one (with a link), never an edit.
