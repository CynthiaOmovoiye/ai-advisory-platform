# Frontend

Next.js (App Router) frontend for the AI Advisory Platform: TypeScript, TailwindCSS,
React Query, Zod, and Auth.js — the stack from the design docs.

## The shape

```
app/
├── layout.tsx, providers.tsx     React Query + Auth.js session providers
├── page.tsx, login/, assessments/  pages (list + detail)
└── api/
    ├── auth/[...nextauth]/        Auth.js handler
    └── assessments/[id]/          BFF route handlers → FastAPI
components/                        SeverityBadge, RecommendationCard
lib/
├── schemas.ts        Zod schemas mirroring the backend DTOs (runtime-validated boundary)
├── session-token.ts  mints the BFF service token (the Next side of ADR-0009)
├── api.ts            server-only typed client to FastAPI
├── auth.ts           Auth.js config + getSessionIdentity()
└── queries.ts        React Query hooks (client → same-origin BFF routes)
```

## How auth flows (ADR-0009)

```
Browser ──(Auth.js session cookie)──► Next.js BFF route handler
                                         │  getSessionIdentity()
                                         │  mintServiceToken()  ── HS256 over AUTH_SECRET
                                         ▼
                                       FastAPI  ── decode_session() verifies sig/iss/aud/exp
```

The browser **never** holds a backend token. The same `AUTH_SECRET` signs both the
Auth.js session and the short-lived service token; the backend trusts only the latter.
`lib/session-token.ts` here and `app/infra/auth.py` in the backend are two halves of
one contract — the claim names match exactly.

## Why this layering

- **Server Components / route handlers** do the privileged work (token, backend calls);
  client components never see secrets.
- **Zod at the boundary**: every backend payload is parsed (`lib/schemas.ts`) on both
  the server (`api.ts`) and the client (`queries.ts`) — typed *and* validated.
- **React Query** owns client cache/refetch; completing an assessment seeds the
  recommendations cache so the UI updates without a round-trip.

## Run

```bash
cp .env.example .env.local      # set AUTH_SECRET == backend AUTH_SECRET
npm install
npm run dev                     # http://localhost:3000  (backend must be on :8000)
npm run typecheck               # tsc --noEmit
```

> The framework-agnostic core (`lib/schemas.ts`, `lib/session-token.ts`, `lib/api.ts`)
> is typechecked in isolation and passes; the full app typechecks/builds after
> `npm install` brings in the Next/React toolchain.

## Authentication

**The login is demo-only.** The Auth.js Credentials provider accepts any
email/password and issues a **global-admin** session so the entire UI is exercisable
end-to-end. It is **opt-in**: enabled only when `AUTH_DEMO_MODE` is exactly `"true"`.
Any other value — including missing or misspelled — leaves it **off** (fail-closed), so
no provider is registered and login fails until a real one is wired. The bundled Docker
demo sets `AUTH_DEMO_MODE=true` deliberately; a real deployment must not.

What **is** production-shaped (and implemented):

- The **BFF trust boundary** ([ADR-0009](../docs/adr/0009-auth-bff-session-token.md)):
  the Next.js server mints a short-lived HS256 service token from the session and the
  FastAPI backend verifies it (signature, issuer, audience, expiry) and maps claims to
  a `Principal`. The browser never holds a backend token.
- **Default-deny RBAC** and **tenant isolation** on every backend route.

**Extension point (not built):** a real identity source — a DB-backed Auth.js user
store with password hashing, or an external IdP (OIDC/SAML) — plugged in as the
provider in `lib/auth.ts`. Registration, password reset, and email verification are
part of that work and are intentionally out of scope here. No part of the docs claims
production auth is implemented.
