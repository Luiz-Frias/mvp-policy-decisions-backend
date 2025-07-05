# Agent 01: Database Migration Specialist

## YOUR MISSION

Create all database tables and migrations needed for the full production system, including quotes, ratings, security, and compliance tables.

## NO SILENT FALLBACKS PRINCIPLE

### Database Schema Configuration Requirements

**NEVER use default values without explicit business justification:**

```sql
-- ❌ FORBIDDEN: Silent defaults without business rules
CREATE TABLE quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),  -- OK: Technical default
    premium DECIMAL DEFAULT 0,                       -- FORBIDDEN: No business rule
    status VARCHAR(20) DEFAULT 'draft',              -- OK: Explicit business rule
    customer_id UUID                                  -- FORBIDDEN: NULL allowed implicitly
);

-- ✅ REQUIRED: Explicit constraints and business rules
CREATE TABLE quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    premium DECIMAL CHECK (premium >= 0),            -- Explicit validation
    status VARCHAR(20) NOT NULL CHECK (status IN ('draft', 'quoted', 'bound')),
    customer_id UUID NOT NULL REFERENCES customers(id),  -- Explicit NOT NULL
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**NEVER create tables without explicit foreign key constraints:**

```sql
-- ❌ FORBIDDEN: Missing relationship validation
CREATE TABLE policies (
    customer_id UUID  -- No FK constraint
);

-- ✅ REQUIRED: Explicit foreign key relationships
CREATE TABLE policies (
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE RESTRICT
);
```

**NEVER create migrations without rollback procedures:**

```python
# ❌ FORBIDDEN: No rollback strategy
def upgrade() -> None:
    op.create_table('new_table', ...)
    # No downgrade function

# ✅ REQUIRED: Complete rollback procedures
def upgrade() -> None:
    op.create_table('new_table', ...)
    op.create_index('idx_new_table_field', 'new_table', ['field'])

def downgrade() -> None:
    op.drop_index('idx_new_table_field')
    op.drop_table('new_table')
```

### Fail Fast Validation

If ANY of these configurations are missing, you MUST:

1. **Stop immediately** and document the missing configuration
2. **Research the specific business requirement** (30-second timeout)
3. **Explicitly configure** the proper constraint or relationship
4. **Never proceed** with implicit defaults

### Explicit Error Remediation

**When schema validation fails:**

- Document the exact constraint that failed
- Provide the business rule that should apply
- Create explicit migration to fix the constraint
- Never use generic "fix later" TODOs

**Required verification for each table:**

- All foreign keys explicitly defined with CASCADE/RESTRICT behavior
- All NOT NULL constraints have business justification
- All CHECK constraints validate business rules
- All indexes support expected query patterns
- All migrations have complete rollback procedures

## MANDATORY PRE-WORK

1. Read ALL documents listed in AGENT_TEMPLATE.md FIRST
2. Specifically study:
   - `.sage/source_documents/DEMO_OVERALL_PRD.md` for business requirements
   - `.sage/source_documents/DEMO_OVERALL_ARCHITECTURE.md` for data architecture
   - `alembic/versions/001_initial_schema.py` to understand existing schema
   - `src/pd_prime_demo/models/` for existing model patterns (base.py, policy.py, customer.py, claim.py)

## SPECIFIC TASKS

### 1. Quote System Tables

```sql
-- quotes table with full production fields
CREATE TABLE quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_number VARCHAR(20) UNIQUE NOT NULL, -- Format: QUOT-YYYY-NNNNNN
    customer_id UUID REFERENCES customers(id),
    status VARCHAR(20) NOT NULL CHECK (status IN ('draft', 'calculating', 'quoted', 'expired', 'bound', 'declined')),

    -- Quote data
    product_type VARCHAR(20) NOT NULL,
    state VARCHAR(2) NOT NULL,
    zip_code VARCHAR(10) NOT NULL,
    effective_date DATE NOT NULL,

    -- Pricing
    base_premium DECIMAL(10,2),
    total_premium DECIMAL(10,2),
    monthly_premium DECIMAL(10,2),

    -- Complex data as JSONB
    vehicle_info JSONB, -- For auto quotes
    property_info JSONB, -- For home quotes
    drivers JSONB, -- Array of driver info
    coverage_selections JSONB,
    discounts_applied JSONB,
    surcharges_applied JSONB,
    rating_factors JSONB,

    -- AI and analytics
    ai_risk_score DECIMAL(3,2) CHECK (ai_risk_score >= 0 AND ai_risk_score <= 1),
    ai_risk_factors JSONB,
    conversion_probability DECIMAL(3,2),

    -- Metadata
    version INTEGER DEFAULT 1,
    parent_quote_id UUID REFERENCES quotes(id), -- For versioning
    expires_at TIMESTAMPTZ NOT NULL,
    converted_to_policy_id UUID REFERENCES policies(id),
    declined_reasons JSONB,

    -- Audit fields
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id)
);

-- Indexes for performance
CREATE INDEX idx_quotes_customer_id ON quotes(customer_id);
CREATE INDEX idx_quotes_status ON quotes(status);
CREATE INDEX idx_quotes_quote_number ON quotes(quote_number);
CREATE INDEX idx_quotes_expires_at ON quotes(expires_at);
CREATE INDEX idx_quotes_state_product ON quotes(state, product_type);
```

### 2. Rating Engine Tables

```sql
-- Base rates by state/product/coverage
CREATE TABLE rate_tables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state VARCHAR(2) NOT NULL,
    product_type VARCHAR(20) NOT NULL,
    coverage_type VARCHAR(50) NOT NULL,

    -- Rate info
    base_rate DECIMAL(8,6) NOT NULL,
    min_premium DECIMAL(10,2),
    max_premium DECIMAL(10,2),

    -- Factors as JSONB for flexibility
    territory_factors JSONB, -- ZIP-based multipliers
    vehicle_factors JSONB, -- Make/model/year multipliers
    driver_factors JSONB, -- Age/experience multipliers
    credit_factors JSONB, -- Credit score tiers

    -- Metadata
    effective_date DATE NOT NULL,
    expiration_date DATE,
    filing_id VARCHAR(50), -- State filing reference
    approved_by VARCHAR(100),

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(state, product_type, coverage_type, effective_date)
);

-- Discount rules
CREATE TABLE discount_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Applicability
    product_types JSONB NOT NULL, -- Array of applicable products
    states JSONB NOT NULL, -- Array of applicable states

    -- Discount calculation
    discount_type VARCHAR(20) NOT NULL CHECK (discount_type IN ('percentage', 'fixed')),
    discount_value DECIMAL(10,2) NOT NULL,
    max_discount_amount DECIMAL(10,2),

    -- Rules
    eligibility_rules JSONB NOT NULL,
    stackable BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 100,

    -- Validity
    effective_date DATE NOT NULL,
    expiration_date DATE,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### 3. Security & Compliance Tables

```sql
-- SSO providers configuration
CREATE TABLE sso_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name VARCHAR(50) UNIQUE NOT NULL,
    provider_type VARCHAR(20) NOT NULL, -- google, azure, okta, auth0

    -- Configuration
    client_id VARCHAR(255) NOT NULL,
    client_secret_encrypted TEXT NOT NULL, -- Encrypted with KMS
    issuer_url TEXT,
    authorize_url TEXT,
    token_url TEXT,
    userinfo_url TEXT,

    -- Settings
    enabled BOOLEAN DEFAULT false,
    auto_create_users BOOLEAN DEFAULT false,
    allowed_domains JSONB, -- Array of email domains

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- OAuth2 clients for API access
CREATE TABLE oauth2_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id VARCHAR(100) UNIQUE NOT NULL,
    client_secret_hash TEXT NOT NULL,
    client_name VARCHAR(100) NOT NULL,

    -- OAuth2 settings
    redirect_uris JSONB NOT NULL,
    allowed_grant_types JSONB NOT NULL,
    allowed_scopes JSONB NOT NULL,

    -- Rate limiting
    rate_limit_per_minute INTEGER DEFAULT 60,
    rate_limit_per_hour INTEGER DEFAULT 1000,

    -- Status
    active BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- MFA settings per user
CREATE TABLE user_mfa_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id),

    -- TOTP
    totp_secret_encrypted TEXT,
    totp_enabled BOOLEAN DEFAULT false,

    -- WebAuthn
    webauthn_credentials JSONB, -- Array of credential info
    webauthn_enabled BOOLEAN DEFAULT false,

    -- SMS (backup)
    sms_phone_encrypted TEXT,
    sms_enabled BOOLEAN DEFAULT false,

    -- Recovery codes
    recovery_codes_encrypted JSONB,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Audit log for SOC 2 compliance
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Who
    user_id UUID REFERENCES users(id),
    ip_address INET,
    user_agent TEXT,
    session_id UUID,

    -- What
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,

    -- Details
    request_method VARCHAR(10),
    request_path TEXT,
    request_body JSONB,
    response_status INTEGER,
    response_time_ms INTEGER,

    -- Security
    risk_score DECIMAL(3,2),
    security_alerts JSONB,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create partitioned table for high volume
CREATE TABLE audit_logs_2024 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

### 4. Real-time & Analytics Tables

```sql
-- WebSocket connections tracking
CREATE TABLE websocket_connections (
    connection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),

    -- Connection info
    connected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMPTZ,
    last_ping_at TIMESTAMPTZ,

    -- Subscriptions
    subscribed_channels JSONB, -- Array of channel names

    -- Metadata
    ip_address INET,
    user_agent TEXT
);

-- Analytics events for real-time dashboard
CREATE TABLE analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event info
    event_type VARCHAR(50) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,

    -- Context
    user_id UUID REFERENCES users(id),
    session_id UUID,
    quote_id UUID REFERENCES quotes(id),
    policy_id UUID REFERENCES policies(id),

    -- Metrics
    value DECIMAL(10,2),
    duration_ms INTEGER,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for real-time queries
CREATE INDEX idx_analytics_events_created_at ON analytics_events(created_at);
CREATE INDEX idx_analytics_events_type_category ON analytics_events(event_type, event_category);
```

### 5. Create Alembic Migrations

Create these files in `alembic/versions/`:

1. `002_add_quote_system_tables.py`
2. `003_add_rating_engine_tables.py`
3. `004_add_security_compliance_tables.py`
4. `005_add_realtime_analytics_tables.py`

Each migration should:

- Include proper upgrade() and downgrade() functions
- Add helpful comments
- Include index creation
- Set up proper foreign keys
- Add check constraints

## DELIVERABLES

1. **Migration Files**: All 4 Alembic migration files
2. **Seed Data Script**: `scripts/seed_rate_tables.py` with initial rates for CA, TX, NY
3. **Database Documentation**: `docs/database_schema.md` with full ERD
4. **Performance Test**: Script to verify indexes work properly

## SUCCESS CRITERIA

1. All migrations run without errors
2. Foreign keys properly enforced
3. Indexes improve query performance
4. Check constraints validate data
5. Partitioning works for audit logs

## CONFIDENCE CHECK

For each table design decision:

- If confidence < 95%, research best practices for that table type
- Example searches (30-second timeout):
  - "PostgreSQL audit log table best practices"
  - "Database schema for insurance quotes"
  - "OAuth2 client storage schema"

Remember: We're building for 10,000 concurrent users. Design for scale!

## ADDITIONAL REQUIREMENT: Admin Module Tables

**IMPORTANT**: You must ALSO read `.sage/wave_contexts/wave_2/AGENT_DEPLOYMENT_SUMMARY.md` to understand the full system context.

### 6. Admin System Tables

You must also create comprehensive admin module tables:

```sql
-- Admin users with enhanced permissions
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,

    -- Admin specific fields
    role_id UUID REFERENCES admin_roles(id),
    is_super_admin BOOLEAN DEFAULT false,

    -- Security
    two_factor_enabled BOOLEAN DEFAULT false,
    two_factor_secret TEXT,
    last_login_at TIMESTAMPTZ,
    last_login_ip INET,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMPTZ,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES admin_users(id),
    deactivated_at TIMESTAMPTZ
);

-- Admin roles and permissions
CREATE TABLE admin_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,

    -- Permissions as JSONB for flexibility
    permissions JSONB NOT NULL DEFAULT '[]',

    -- Hierarchy
    parent_role_id UUID REFERENCES admin_roles(id),

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Admin permissions registry
CREATE TABLE admin_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource VARCHAR(50) NOT NULL, -- 'quotes', 'policies', 'users', etc.
    action VARCHAR(50) NOT NULL,   -- 'read', 'write', 'delete', 'approve'
    description TEXT,

    UNIQUE(resource, action)
);

-- System configuration
CREATE TABLE system_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(50) NOT NULL,
    key VARCHAR(100) NOT NULL,
    value JSONB NOT NULL,

    -- Type information
    data_type VARCHAR(20) NOT NULL, -- 'string', 'number', 'boolean', 'json'
    validation_rules JSONB,

    -- Security
    is_sensitive BOOLEAN DEFAULT false,
    encrypted BOOLEAN DEFAULT false,

    -- Audit
    last_modified_by UUID REFERENCES admin_users(id),
    last_modified_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(category, key)
);

-- Admin activity logs
CREATE TABLE admin_activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES admin_users(id),

    -- Activity details
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,

    -- Changes made
    old_values JSONB,
    new_values JSONB,

    -- Context
    ip_address INET,
    user_agent TEXT,
    request_id UUID,

    -- Result
    status VARCHAR(20) NOT NULL, -- 'success', 'failed', 'unauthorized'
    error_message TEXT,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create index for fast lookups
CREATE INDEX idx_admin_activity_logs_admin_user ON admin_activity_logs(admin_user_id);
CREATE INDEX idx_admin_activity_logs_created_at ON admin_activity_logs(created_at);
CREATE INDEX idx_admin_activity_logs_resource ON admin_activity_logs(resource_type, resource_id);

-- Admin dashboard configurations
CREATE TABLE admin_dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,

    -- Dashboard configuration
    layout JSONB NOT NULL,
    widgets JSONB NOT NULL,
    refresh_interval INTEGER DEFAULT 60, -- seconds

    -- Access control
    required_permission VARCHAR(100),

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Rate table administration
CREATE TABLE admin_rate_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rate_table_id UUID REFERENCES rate_tables(id),

    -- Approval workflow
    submitted_by UUID REFERENCES admin_users(id),
    submitted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    approved_by UUID REFERENCES admin_users(id),
    approved_at TIMESTAMPTZ,

    rejected_by UUID REFERENCES admin_users(id),
    rejected_at TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Changes
    changes_summary JSONB NOT NULL,
    effective_date DATE NOT NULL,

    status VARCHAR(20) DEFAULT 'pending' -- 'pending', 'approved', 'rejected'
);
```

### 7. Create Admin-Specific Indexes and Constraints

```sql
-- Performance indexes for admin queries
CREATE INDEX idx_system_settings_category ON system_settings(category);
CREATE INDEX idx_admin_users_role ON admin_users(role_id);
CREATE INDEX idx_admin_rate_approvals_status ON admin_rate_approvals(status);

-- Add RLS (Row Level Security) for admin tables
ALTER TABLE admin_activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;
```

### 8. Update Alembic Migrations

Add a new migration file:

- `006_add_admin_system_tables.py`

This should create all admin tables with proper relationships and indexes.

Make sure all admin tables follow the same patterns as other tables and include proper audit trails!
