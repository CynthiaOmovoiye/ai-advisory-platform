-- =============================================================================
-- AI Advisory Platform — canonical PostgreSQL schema
-- =============================================================================
-- This is the design-baseline DDL. In the running system these statements are
-- produced by Alembic migrations; this file is the human-readable source of truth
-- and matches docs/architecture/erd.md.
--
-- Conventions:
--   * UUID primary keys (gen_random_uuid via pgcrypto).
--   * created_at / updated_at on every table; deleted_at where soft-delete applies.
--   * organization_id on every tenant-owned table (isolation enforced in the
--     repository layer — see ADR-0006).
--   * JSONB only where the schema is genuinely dynamic; relational elsewhere.
--   * Enums via CHECK constraints + lookup where helpful (boring, portable).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid(), digest()
CREATE EXTENSION IF NOT EXISTS citext;       -- case-insensitive email
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector — reserved for RAG (ADR-0008)

-- Helper: updated_at trigger -------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- IDENTITY & ACCESS
-- =============================================================================

CREATE TABLE users (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email            citext NOT NULL UNIQUE,
    password_hash    text NOT NULL,
    name             text,
    status           text NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','disabled')),
    email_verified_at timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    deleted_at       timestamptz                       -- soft delete
);
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE email_verification_tokens (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  text NOT NULL UNIQUE,
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_email_verification_tokens_user ON email_verification_tokens(user_id);

CREATE TABLE roles (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE
                  CHECK (name IN ('admin','consultant','org_user')),
    description text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE permissions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code        text NOT NULL UNIQUE,        -- e.g. 'report:publish', 'rule:edit'
    description text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE role_permissions (
    role_id       uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id uuid NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- Role assignment, optionally scoped to an org (NULL org = global, e.g. admin /
-- consultant). See ERD note on why this is org-scoped.
CREATE TABLE user_roles (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    organization_id uuid,                    -- FK added after organizations exists
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, role_id, organization_id)
);

-- =============================================================================
-- ORGANIZATIONS (tenant boundary)
-- =============================================================================

CREATE TABLE organizations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL,
    slug        text NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    deleted_at  timestamptz
);
CREATE TRIGGER trg_orgs_updated BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE user_roles
    ADD CONSTRAINT fk_user_roles_org
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;

CREATE TABLE organization_members (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id           uuid REFERENCES users(id) ON DELETE SET NULL,  -- null until invite accepted
    status            text NOT NULL DEFAULT 'invited'
                        CHECK (status IN ('invited','active','removed')),
    invited_by        uuid REFERENCES users(id) ON DELETE SET NULL,
    invited_email     citext NOT NULL,
    invite_token_hash text,                  -- store hash, never the raw token
    invite_expires_at timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, invited_email)
);
CREATE INDEX idx_org_members_org ON organization_members(organization_id);
CREATE INDEX idx_org_members_user ON organization_members(user_id);
CREATE TRIGGER trg_org_members_updated BEFORE UPDATE ON organization_members
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- ASSESSMENT ENGINE
-- =============================================================================

CREATE TABLE assessment_templates (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category    text NOT NULL
                  CHECK (category IN ('ai_readiness','data_maturity','security',
                                      'governance','compliance','operations','infrastructure')),
    title       text NOT NULL,
    description text,
    version     integer NOT NULL DEFAULT 1,
    status      text NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','published','archived')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (category, version)
);
CREATE TRIGGER trg_templates_updated BEFORE UPDATE ON assessment_templates
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE assessment_sections (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id uuid NOT NULL REFERENCES assessment_templates(id) ON DELETE CASCADE,
    title       text NOT NULL,
    description text,
    order_index integer NOT NULL DEFAULT 0,
    UNIQUE (template_id, order_index)
);
CREATE INDEX idx_sections_template ON assessment_sections(template_id);

CREATE TABLE questions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id  uuid NOT NULL REFERENCES assessment_sections(id) ON DELETE CASCADE,
    key         text NOT NULL,               -- stable id referenced by rule conditions
    prompt      text NOT NULL,
    type        text NOT NULL
                  CHECK (type IN ('text','long_text','number',
                                  'single_select','multi_select','file_upload')),
    config      jsonb NOT NULL DEFAULT '{}'::jsonb,  -- options, min/max, required, validation
    order_index integer NOT NULL DEFAULT 0,
    UNIQUE (section_id, key)
);
CREATE INDEX idx_questions_section ON questions(section_id);

CREATE TABLE assessments (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    template_id        uuid NOT NULL REFERENCES assessment_templates(id),
    assignee_id        uuid REFERENCES users(id) ON DELETE SET NULL,
    status             text NOT NULL DEFAULT 'in_progress'
                         CHECK (status IN ('in_progress','completed','evaluating','reviewed','archived')),
    ruleset_version_id uuid,                  -- pinned at completion (FK below)
    completed_at       timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    deleted_at         timestamptz
);
CREATE INDEX idx_assessments_org ON assessments(organization_id);
CREATE INDEX idx_assessments_org_status ON assessments(organization_id, status);
CREATE TRIGGER trg_assessments_updated BEFORE UPDATE ON assessments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE responses (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id  uuid NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    question_id    uuid NOT NULL REFERENCES questions(id),
    value          jsonb NOT NULL,           -- typed per question.type
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (assessment_id, question_id)
);
CREATE INDEX idx_responses_assessment ON responses(assessment_id);
CREATE TRIGGER trg_responses_updated BEFORE UPDATE ON responses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE documents (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    response_id       uuid REFERENCES responses(id) ON DELETE SET NULL,
    original_filename text NOT NULL,
    storage_key       text NOT NULL,         -- object-store key, NEVER a public path
    mime_type         text NOT NULL,         -- validated server-side, not trusted from client
    byte_size         bigint NOT NULL,
    sha256            text NOT NULL,
    scan_status       text NOT NULL DEFAULT 'pending'
                        CHECK (scan_status IN ('pending','clean','infected','error')),
    created_at        timestamptz NOT NULL DEFAULT now(),
    deleted_at        timestamptz
);
CREATE INDEX idx_documents_org ON documents(organization_id);
CREATE INDEX idx_documents_sha ON documents(sha256);
CREATE INDEX idx_documents_scan ON documents(scan_status);

-- =============================================================================
-- RULE ENGINE
-- =============================================================================

CREATE TABLE rulesets (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name         text NOT NULL,
    version      integer NOT NULL DEFAULT 1,
    status       text NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft','published','archived')),
    published_at timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);
CREATE TRIGGER trg_rulesets_updated BEFORE UPDATE ON rulesets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE assessments
    ADD CONSTRAINT fk_assessments_ruleset
    FOREIGN KEY (ruleset_version_id) REFERENCES rulesets(id);

CREATE TABLE rules (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ruleset_id              uuid NOT NULL REFERENCES rulesets(id) ON DELETE CASCADE,
    code                    text NOT NULL,    -- human-readable id e.g. 'SEC-MFA-001'
    category                text NOT NULL
                              CHECK (category IN ('ai_readiness','data_maturity','security',
                                                  'governance','compliance','operations','infrastructure')),
    severity                text NOT NULL
                              CHECK (severity IN ('info','low','medium','high','critical')),
    -- Safe boolean expression tree over response keys & derived facts.
    -- NOT executable code — evaluated by a sandboxed interpreter (ADR-0003).
    condition               jsonb NOT NULL,
    recommendation_template jsonb NOT NULL,   -- {title, body, references[]}
    priority                integer NOT NULL DEFAULT 100,
    is_active               boolean NOT NULL DEFAULT true,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ruleset_id, code)
);
CREATE INDEX idx_rules_ruleset ON rules(ruleset_id);
CREATE INDEX idx_rules_active ON rules(ruleset_id, is_active);
CREATE TRIGGER trg_rules_updated BEFORE UPDATE ON rules
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- AI VERSIONING & TELEMETRY
-- =============================================================================

CREATE TABLE prompt_versions (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL,                -- e.g. 'exec_summary'
    version    integer NOT NULL DEFAULT 1,
    template   text NOT NULL,
    variables  jsonb NOT NULL DEFAULT '[]'::jsonb,
    is_active  boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

CREATE TABLE model_versions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider           text NOT NULL DEFAULT 'openrouter',
    model_id           text NOT NULL,        -- e.g. 'anthropic/claude-...' routed via OpenRouter
    params             jsonb NOT NULL DEFAULT '{}'::jsonb,  -- temperature, max_tokens, ...
    input_cost_per_1k  numeric(12,6) NOT NULL DEFAULT 0,    -- for cost accounting
    output_cost_per_1k numeric(12,6) NOT NULL DEFAULT 0,
    is_active          boolean NOT NULL DEFAULT false,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, model_id, created_at)
);

-- =============================================================================
-- RECOMMENDATIONS & REPORTS
-- =============================================================================

CREATE TABLE recommendations (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    assessment_id     uuid NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    rule_id           uuid REFERENCES rules(id),         -- traceability to the deterministic source
    category          text NOT NULL,
    severity          text NOT NULL
                        CHECK (severity IN ('info','low','medium','high','critical')),
    -- Deterministic fields (rule engine output — source of truth):
    title             text NOT NULL,
    finding           text NOT NULL,
    -- LLM-enhanced narrative fields (nullable; fallback to deterministic render):
    rationale         text,
    remediation       text,
    -- Provenance & governance:
    prompt_version_id uuid REFERENCES prompt_versions(id),
    model_version_id  uuid REFERENCES model_versions(id),
    grounding_passed  boolean,               -- did the enhancement pass the grounding check?
    status            text NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','edited','approved','rejected')),
    edited_by         uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_recs_assessment ON recommendations(assessment_id);
CREATE INDEX idx_recs_org ON recommendations(organization_id);
CREATE INDEX idx_recs_assessment_cat ON recommendations(assessment_id, category);
CREATE TRIGGER trg_recs_updated BEFORE UPDATE ON recommendations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE llm_calls (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   uuid REFERENCES organizations(id) ON DELETE SET NULL,
    recommendation_id uuid REFERENCES recommendations(id) ON DELETE SET NULL,
    prompt_version_id uuid REFERENCES prompt_versions(id),
    model_version_id  uuid REFERENCES model_versions(id),
    correlation_id    text,                  -- ties web→api→worker→llm
    status            text NOT NULL CHECK (status IN ('success','timeout','error','rejected')),
    latency_ms        integer,
    input_tokens      integer,
    output_tokens     integer,
    cost_estimate     numeric(12,6),         -- tokens × model rates
    created_at        timestamptz NOT NULL DEFAULT now()  -- append-only telemetry
);
CREATE INDEX idx_llm_calls_created ON llm_calls(created_at);
CREATE INDEX idx_llm_calls_model_created ON llm_calls(model_version_id, created_at);
CREATE INDEX idx_llm_calls_org ON llm_calls(organization_id);

CREATE TABLE reports (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    assessment_id   uuid NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    title           text NOT NULL,
    status          text NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','published')),
    content         jsonb,                   -- immutable snapshot of what was published
    pdf_storage_key text,                    -- object-store key (outside public paths)
    published_by    uuid REFERENCES users(id) ON DELETE SET NULL,
    published_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_reports_org ON reports(organization_id);
CREATE INDEX idx_reports_assessment ON reports(assessment_id);
CREATE TRIGGER trg_reports_updated BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- EVALUATION FRAMEWORK
-- =============================================================================

CREATE TABLE evaluation_datasets (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL,
    version     integer NOT NULL DEFAULT 1,
    description text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

CREATE TABLE evaluation_dataset_items (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id uuid NOT NULL REFERENCES evaluation_datasets(id) ON DELETE CASCADE,
    input      jsonb NOT NULL,               -- gold assessment responses fixture
    expected   jsonb NOT NULL,               -- expected deterministic findings + narrative constraints
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_eval_items_dataset ON evaluation_dataset_items(dataset_id);

CREATE TABLE evaluation_runs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id        uuid NOT NULL REFERENCES evaluation_datasets(id),
    prompt_version_id uuid REFERENCES prompt_versions(id),
    model_version_id  uuid REFERENCES model_versions(id),
    status            text NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running','completed','failed')),
    -- aggregate scores for fast regression comparison:
    accuracy          numeric(5,4),
    consistency       numeric(5,4),
    completeness      numeric(5,4),
    hallucination_rate numeric(5,4),
    triggered_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    completed_at      timestamptz
);
CREATE INDEX idx_eval_runs_dataset ON evaluation_runs(dataset_id, created_at);

CREATE TABLE evaluations (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id    uuid NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    item_id   uuid NOT NULL REFERENCES evaluation_dataset_items(id),
    metrics   jsonb NOT NULL,                -- {accuracy, consistency, completeness, hallucination, grounding}
    passed    boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_evaluations_run ON evaluations(run_id);

-- =============================================================================
-- CROSS-CUTTING: AUDIT LOG (append-only)
-- =============================================================================

CREATE TABLE audit_logs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id   uuid REFERENCES users(id) ON DELETE SET NULL,
    organization_id uuid REFERENCES organizations(id) ON DELETE SET NULL,
    action          text NOT NULL,           -- e.g. 'report.published', 'rule.updated'
    entity_type     text,
    entity_id       uuid,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    ip              inet,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_org_created ON audit_logs(organization_id, created_at);
CREATE INDEX idx_audit_actor_created ON audit_logs(actor_user_id, created_at);
-- audit_logs is append-only: no UPDATE/DELETE grants in production roles.

-- =============================================================================
-- RESERVED FOR FUTURE AI FEATURES (designed, not created — ADR-0008)
-- =============================================================================
-- CREATE TABLE knowledge_chunks (
--     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--     organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
--     source_type text NOT NULL,
--     content text NOT NULL,
--     embedding vector(1536) NOT NULL,
--     created_at timestamptz NOT NULL DEFAULT now()
-- );
-- CREATE INDEX ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
-- =============================================================================
