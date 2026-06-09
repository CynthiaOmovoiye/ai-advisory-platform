# AI Advisory Platform — User Guide

A practical, step-by-step manual: what the app is, how it thinks, and exactly what every
page, field, and button does.

---

## 1. What it is

A tool for running a structured **"how ready is this organization for AI adoption?"**
review. You answer a questionnaire; the system grades the answers into **findings**; AI
writes the human-readable explanation for each; a person approves them; you publish a
**report**.

Think of it as the software a consultancy would use to deliver a defensible AI-readiness
assessment — not a chatbot that guesses.

---

## 2. The core idea (read this once — everything else follows from it)

There are three deliberate stages, in order:

1. **Deterministic rules decide the findings.**
   Your answers are run through a fixed, versioned set of rules. A rule is a plain
   condition over your answers. Example rule (one of six shipped in `baseline-v1`):

   > **SEC-MFA-001** — *if* `mfa_enabled = false` **and** `sensitive_data_present = true`
   > → finding: **"Enforce multi-factor authentication"** (severity: high).

   Same answers → same findings, every time. Nothing is left to a model's mood.

2. **AI explains the findings — it never creates them.**
   For each finding the rules produced, the language model writes the wording (the
   finding summary, rationale, remediation). A **grounding check** then verifies the AI's
   text is supported by the finding. If the AI is unavailable or its text fails the
   check, the app falls back to the rule's built-in deterministic wording. Either way,
   *the AI cannot add, remove, or change a finding.*

3. **A human signs off.**
   A consultant **approves or rejects every recommendation** before it can go into a
   report.

The payoff: every recommendation is **traceable** (back to a specific rule code),
**grounded** (AI text checked), and **reviewed** (human-approved). On each recommendation
card you'll see a small label — **"AI-enhanced · grounded"** or **"deterministic"** —
telling you which wording you're looking at.

---

## 3. Key terms

| Term | Plain meaning |
|---|---|
| **Organization (org)** | Your tenant. All your data lives inside it; nobody outside your org can see it. |
| **Template** | A reusable questionnaire (a set of questions). You publish it, then start assessments from it. |
| **Assessment** | One filled-in attempt at a template by your org. This is the thing you "do." |
| **Response** | Your answer to one question in an assessment. |
| **Ruleset** | The versioned collection of rules that turns answers into findings (`baseline-v1` ships with 6 rules). |
| **Finding / Recommendation** | A graded issue the rules detected, with a fix. "Recommendation" is the reviewable card you approve/reject. |
| **Severity** | How serious a finding is: **critical › high › medium › low › info**. |
| **Grounding** | The automatic check that the AI's wording is backed by the actual finding. |
| **Report** | The published deliverable — a PDF compiled from the approved recommendations. |

---

## 4. Who's who (roles & permissions)

When you **sign up, you create an org and become its Consultant.** The Admin role is
*not* self-granted — it's assigned deliberately to people who oversee the platform.

| Capability | Org user | Consultant | Admin |
|---|:---:|:---:|:---:|
| Take & read assessments | ✓ | ✓ | ✓ |
| Complete an assessment | ✓ | ✓ | ✓ |
| Edit / approve recommendations | | ✓ | ✓ |
| Publish reports | | ✓ | ✓ |
| Author & publish templates | | ✓ | ✓ |
| Invite / manage members | | ✓ | ✓ |
| Admin dashboard & Evaluation | | | ✓ |

The top navigation adapts to your role:
- **Logged out:** brand + *Sign in* / *Sign up* only.
- **Consultant:** Assessments, Templates, Members.
- **Admin:** the above **plus** Admin and Evaluation.

> If you signed up or used the demo account and don't see **Admin** / **Evaluation** in
> the nav — that's correct. Those need the admin role.

---

## 5. The flow at a glance

```
Sign up → Verify email → Sign in
   → Templates:  author a questionnaire → Publish
   → Templates:  Start an assessment from it
   → Assessment: answer the questions → Save & complete
        (rules generate findings → AI explains → grounding check)
   → Assessment: Approve / Reject each recommendation
   → Assessment: Publish report → download the PDF
Optional: Members (invite team) · Admin (usage/cost) · Evaluation (AI quality)
```

---

## 6. End-to-end walkthrough (using the built-in demo)

The fastest way to see the whole loop. The app ships with a seeded demo org that already
has an assessment waiting to be completed.

1. Open **http://localhost:3100** and **Sign in** with `demo@example.com` / `ChangeMe123!`.
2. Go to **Assessments** — you'll see one already in progress.
3. Open it. Its answers are pre-filled with realistic values (no MFA, sensitive data
   present, no governance owner, low data-quality score, no DPIA, RAG/agents planned).
4. Click **Save & complete**. The engine runs and you land in **review mode** with five
   findings:

   | Code | Severity | What it flags |
   |---|---|---|
   | COMP-PII-004 | **critical** | No Data Protection Impact Assessment despite sensitive data |
   | SEC-MFA-001 | **high** | MFA off while handling sensitive data |
   | GOV-OWN-002 | **medium** | No accountable AI governance owner |
   | DATA-QLT-003 | **medium** | Data quality too low for model adoption |
   | OPS-OBS-005 | **low** | No model monitoring/observability plan |

5. **Approve** (or reject) each recommendation. The **Publish report** button stays
   disabled until every card has been reviewed.
6. Click **Publish report**. The PDF renders in the background; when it's ready a
   **"view PDF"** link appears.

That's the entire product loop. Everything below is the detail.

---

## 6b. Scripted demo: the full template flow (≈3 minutes)

The seed also ships a **published, multi-section template** —
**"AI Readiness — Comprehensive (demo)"** — so you can show the *whole* journey, starting
from the template, not just a pre-filled assessment. Its question **keys** are wired to
the `baseline-v1` ruleset, so real answers produce real findings.

Its five sections:

| Section | Question (key) | Type |
|---|---|---|
| Security & Access | Is MFA enforced? (`mfa_enabled`) | Yes/No |
| | Process sensitive data? (`sensitive_data_present`) | Yes/No |
| Data Maturity | Data quality 1–5 (`data_quality_score`) | Number |
| Governance | Who owns AI governance? (`ai_governance_owner`) | Select (none / data_team / executive_sponsor) |
| Compliance & Privacy | DPIA completed? (`dpia_completed`) | Yes/No |
| AI Roadmap | Planned capabilities (`planned_capabilities`) | Multi-select (rag / agents / automation / analytics) |
| | Top AI use cases (`ai_use_cases`) | Long text |

**Run it (the talk track):**

1. Sign in as `demo@example.com` / `ChangeMe123!`.
2. **Templates** → open **"AI Readiness — Comprehensive (demo)"** to show the section/
   question structure (this is exactly what the *Author a new template* form builds — point
   that out). It's already **published**, so it shows **Start**.
3. Click **Start** → you're dropped into a fresh assessment with all five sections.
4. Answer to trigger findings (this is the realistic "unprepared org" profile):
   - MFA enforced → **No**
   - Process sensitive data → **Yes**
   - Data quality → **2**
   - AI governance owner → **none**
   - DPIA completed → **No**
   - Planned capabilities → tick **rag**
5. **Save & complete.** You'll get **six findings** spanning every severity:

   `COMP-PII-004` critical · `SEC-MFA-001` high · `GOV-OWN-002` medium ·
   `DATA-QLT-003` medium · `OPS-OBS-005` low · `INF-VEC-006` info

6. **Approve** them, then **Publish report**.

> Want to show authoring from scratch instead? On the **Templates** page, fill in *Author a
> new template* — note that each question's **key** is what links it to a rule. Use a key
> like `mfa_enabled` and the MFA rule will evaluate it; use an arbitrary key and the engine
> simply won't have a rule for it (no finding). That key↔rule contract is the whole trick.

---

## 7. Page-by-page reference

### Landing — `/`
Marketing page for logged-out visitors (hero, how-it-works, features). The moment you're
signed in, visiting `/` sends you to **Assessments**.

### Sign up — `/signup`
Creates your account **and** a new organization, with you as its consultant.
- **Name** — optional display name.
- **Email** — your login and where verification/reset emails go.
- **Organization name** — becomes your tenant (e.g. "Acme Advisory").
- **Password** — must be **12+ characters with an uppercase, a lowercase, a number, and a
  symbol.** Rejected otherwise.

After submitting, a verification email is sent. (In local dev the app may auto-verify and
sign you straight in.)

### Verify email — `/verify-email`
Opened by clicking the link in the verification email. It confirms your account and points
you to sign in. Links are single-use and expire after 24 hours.

### Sign in — `/login`
Email + password. Wrong credentials and unverified accounts both get the same generic
message (so the page can't be used to discover which emails exist). Has a **Forgot
password?** link.

### Forgot / reset password — `/forgot-password` → `/reset-password`
- **Forgot:** enter your email; you always see the same "if an account exists, we've sent
  a link" message (no account enumeration). If the account exists, a reset email is sent.
- **Reset:** opened from the emailed link; set a new password (same strength rules).
  Completing a reset **signs you out of every existing session** for safety. Reset links
  are single-use and expire after 60 minutes.

### Assessments — `/assessments`
Your org's list of assessments with their status badges. Click one to open it; **Start
from a template** jumps to Templates. Empty state guides you to start your first one.

### Assessment detail — `/assessments/[id]`  *(the core screen)*
This page has **two modes** depending on the assessment's status:

**A) In-progress → Answer mode.** Each section shows its questions. Field types:

| Question type | How you answer |
|---|---|
| `text` | single line |
| `long_text` | multi-line box |
| `number` | numeric input |
| `single_select` | dropdown (defaults to Yes/No if no options were defined) |
| `multi_select` | checkboxes |
| `file_upload` | attach a **PDF or DOCX**; it's virus-scanned and isn't downloadable until it passes |

Buttons:
- **Save responses** — saves your progress so you can return later. Required questions are
  marked with a red `*`.
- **Save & complete** — validates that all required questions are answered, then locks the
  assessment and runs the rules → AI → grounding pipeline. (You can't complete twice.)

**B) Completed → Review mode.** A workspace of recommendation cards, each showing severity,
rule code, the finding's rationale and remediation, a status badge, and the
**AI-enhanced/deterministic** provenance label. For each card:
- **Approve** — accept it into the report.
- **Reject** — exclude it.

A progress line shows "X of N reviewed." **Publish report** unlocks only when all are
reviewed; clicking it renders the PDF in the background (status goes *queued* →
*published*, then a download link appears).

### Templates — `/templates`
Where you build and manage questionnaires.
- **The list** shows each template's category, question count, and status (**draft** or
  **published**). Drafts show a **Publish** button; published ones show **Start** (which
  creates a new assessment and opens it).
- **Author a new template:** give it a **Title** and **Category** (ai_readiness,
  data_maturity, security, governance, compliance, operations, infrastructure), then add
  **Questions** — each needs a **key** (a stable id like `mfa_enabled`, used by rules), a
  **prompt** (the text the user sees), and a **type**. **Create** saves it as a draft;
  **Publish** makes it usable.

> The **key** matters: rules match on keys. A question keyed `mfa_enabled` is what rule
> SEC-MFA-001 reads. Authoring a template that lines up with the ruleset is how you make
> the engine produce findings.

### Members — `/members`
- **Invite a member** by email with a role of **Org user** or **Consultant**.
- The table lists everyone with their role and status (**invited / active / removed**) and
  a **Remove** action. People only ever see your org's data; their access comes from this
  membership, never from anything they can type into a request.

### Admin — `/admin`  *(admin only)*
A read-only dashboard: counts (organizations, assessments, reports), **AI usage &
quality** (LLM-enhanced vs deterministic, grounding pass-rate), the **latest evaluation**
scores, and **LLM telemetry** (call count, estimated cost, average latency, token totals).

### Evaluation — `/eval`  *(admin only)*
Run and review **evaluation runs** that test AI output against a gold dataset
(`baseline-readiness`). Each run reports accuracy, hallucination rate, and consistency —
the regression gate that tells you whether an AI/prompt change made quality worse.

---

## 8. What happens behind the scenes

**When you click "Save & complete":**
1. The server checks you're allowed to complete this assessment (in your org).
2. It loads your answers (scoped to your org only).
3. The **rule engine** evaluates every rule against your answers → a list of findings.
4. The **AI enhancement** step writes wording for each finding and runs the **grounding
   check**; anything that fails falls back to the rule's deterministic text.
5. Recommendations are saved and the action is written to an append-only **audit log**.

**When you click "Publish report":**
- A background worker renders the approved recommendations into a **PDF** (HTML → PDF).
  The report row goes *queued* → *published*; the download link appears when it's done.

**Why you only ever see your org's data:** the active organization is taken from your
verified session — never from anything the browser sends — and the database enforces it a
second time with row-level security. Two independent layers, so a cross-tenant leak would
have to defeat both.

---

## 9. Accounts, email & multiple orgs

- **Email delivery:** verification and password-reset emails are sent through the
  configured provider. In this environment that's **Mailtrap** — check your Mailtrap inbox
  for the messages.
- **Switching organizations:** if you belong to more than one org, an organization
  switcher appears in the header; the rest of the app re-scopes to whichever you pick.
- **Sessions:** signing out clears your session; resetting your password invalidates all
  existing sessions.

---

## 10. Troubleshooting / FAQ

- **"I don't see Admin or Evaluation in the nav."** Expected — those require the admin
  role. Signup and the demo account are consultants.
- **"The site isn't on localhost:3000."** This app runs on **http://localhost:3100**
  (3000 is taken by another app on this machine).
- **"Publish report is greyed out."** You must approve or reject *every* recommendation
  first.
- **"My uploaded file won't download."** Files are scanned first and are only downloadable
  once they pass.
- **"Signup says it can't complete."** Check the password rules (12+ chars, mixed case,
  number, symbol) and that the email isn't already registered.
- **"No findings appeared after completing."** Findings only fire when answers meet a
  rule's condition and the question **keys** match the ruleset. The demo assessment is
  pre-wired to fire five.

---

## 11. Quick reference card

| I want to… | Go to |
|---|---|
| Create an account / org | `/signup` |
| Build a questionnaire | `/templates` → author → Publish |
| Run an assessment | `/templates` → Start, then `/assessments/[id]` |
| See findings & approve them | open the completed assessment |
| Get the PDF | review all → Publish report |
| Add a teammate | `/members` |
| See usage / cost (admin) | `/admin` |
| Check AI quality (admin) | `/eval` |
