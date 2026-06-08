# Frontend

Next.js (App Router) frontend for the AI Advisory Platform: TypeScript, TailwindCSS,
React Query, Zod, and Auth.js — the stack from the design docs.

## The shape

```
app/
├── layout.tsx, providers.tsx     React Query + Auth.js session providers
├── page.tsx, login/, signup/, assessments/  pages (list + detail)
└── api/
    ├── auth/[...nextauth]/        Auth.js handler
    └── assessments/[id]/          BFF route handlers → FastAPI
components/                        SeverityBadge, RecommendationCard
lib/
├── schemas.ts        Zod schemas mirroring the backend DTOs (runtime-validated boundary)
├── session-token.ts  mints the BFF service token (the Next side of ADR-0009)
├── backend-auth.ts   server-only credential/signup calls to FastAPI
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

Auth.js owns the browser session. Its Credentials provider calls the FastAPI auth API
to verify persisted users with Argon2 password hashes, load active organization
memberships, and set session claims from real data. The old demo bypass no longer
exists: no hardcoded demo identity claims and no automatic global admin.

What **is** production-shaped (and implemented):

- Sign up, email verification, sign in, sign out, active-organization switching,
  **password reset** (`/forgot-password` → emailed link → `/reset-password`), and a
  `/verify-email` landing page for the emailed verification link.
- The **BFF trust boundary** ([ADR-0009](../docs/adr/0009-auth-bff-session-token.md)):
  the Next.js server mints a short-lived HS256 service token from the session and the
  FastAPI backend verifies it (signature, issuer, audience, expiry), then reloads
  active membership from the database. The browser never holds a backend token.
- **Default-deny RBAC** and **tenant isolation** on every backend route.

Local seed credentials are real persisted credentials: `demo@example.com` /
`ChangeMe123!`. Email is delivered by a configurable provider (`EMAIL_PROVIDER`:
console / SMTP / Resend — see the root `.env.example`). In local dev the default
console provider logs the verification/reset link and signup can also return the
verification token (`LOCAL_EMAIL_VERIFICATION_TOKENS`) for a no-SMTP loop. Password
reset bumps a per-user `session_version` that the BFF carries as the `sv` claim, so a
reset invalidates every previously minted session.
