-- SSO (Single Sign-On) Database Schema
-- This migration creates all tables required for SSO functionality

-- Table: sso_provider_configs
-- Stores SSO provider configuration and credentials
CREATE TABLE IF NOT EXISTS sso_provider_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name VARCHAR(100) UNIQUE NOT NULL,
    provider_type VARCHAR(20) NOT NULL, -- 'oidc', 'saml', 'oauth2'
    client_id VARCHAR(255) NOT NULL,
    client_secret_encrypted TEXT NOT NULL, -- Encrypted client secret
    configuration JSONB NOT NULL DEFAULT '{}', -- Provider-specific config
    auto_create_users BOOLEAN DEFAULT true,
    allowed_domains TEXT[], -- Allowed email domains
    default_role VARCHAR(50) DEFAULT 'agent',
    is_enabled BOOLEAN DEFAULT false,
    created_by UUID, -- References admin_users(id) when available
    updated_by UUID, -- References admin_users(id) when available
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Ensure provider names are lowercase for consistency
CREATE OR REPLACE FUNCTION normalize_provider_name() RETURNS TRIGGER AS $$
BEGIN
    NEW.provider_name = LOWER(NEW.provider_name);
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER normalize_provider_name_trigger
    BEFORE INSERT OR UPDATE ON sso_provider_configs
    FOR EACH ROW
    EXECUTE FUNCTION normalize_provider_name();

-- Index for fast provider lookups
CREATE INDEX idx_sso_provider_configs_name ON sso_provider_configs(provider_name);
CREATE INDEX idx_sso_provider_configs_enabled ON sso_provider_configs(is_enabled);

-- Table: user_sso_links
-- Links users to their SSO provider accounts
CREATE TABLE IF NOT EXISTS user_sso_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL, -- References users(id)
    provider VARCHAR(100) NOT NULL REFERENCES sso_provider_configs(provider_name),
    provider_user_id VARCHAR(255) NOT NULL, -- User ID from SSO provider
    profile_data JSONB DEFAULT '{}', -- Raw user data from provider
    last_login_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure one link per provider per user
    UNIQUE(user_id, provider),
    -- Ensure unique provider user ID per provider
    UNIQUE(provider, provider_user_id)
);

-- Indexes for fast lookups
CREATE INDEX idx_user_sso_links_user_id ON user_sso_links(user_id);
CREATE INDEX idx_user_sso_links_provider ON user_sso_links(provider);
CREATE INDEX idx_user_sso_links_provider_user_id ON user_sso_links(provider_user_id);
CREATE INDEX idx_user_sso_links_last_login ON user_sso_links(last_login_at);

-- Table: sso_group_mappings
-- Maps SSO groups to internal roles
CREATE TABLE IF NOT EXISTS sso_group_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES sso_provider_configs(id) ON DELETE CASCADE,
    sso_group_name VARCHAR(200) NOT NULL,
    internal_role VARCHAR(50) NOT NULL,
    auto_assign BOOLEAN DEFAULT true,
    created_by UUID, -- References admin_users(id) when available
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique group mapping per provider
    UNIQUE(provider_id, sso_group_name)
);

-- Index for fast group mapping lookups
CREATE INDEX idx_sso_group_mappings_provider_id ON sso_group_mappings(provider_id);
CREATE INDEX idx_sso_group_mappings_auto_assign ON sso_group_mappings(auto_assign);

-- Table: sso_group_sync_logs
-- Logs group synchronization activities
CREATE TABLE IF NOT EXISTS sso_group_sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES sso_provider_configs(id) ON DELETE CASCADE,
    user_id UUID, -- References users(id)
    sync_type VARCHAR(20) NOT NULL, -- 'full', 'incremental'
    groups_added TEXT[],
    groups_removed TEXT[],
    status VARCHAR(20) NOT NULL, -- 'success', 'failed', 'partial'
    error_message TEXT,
    last_sync TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Index for performance on sync logs
CREATE INDEX idx_sso_group_sync_logs_provider_id ON sso_group_sync_logs(provider_id);
CREATE INDEX idx_sso_group_sync_logs_user_id ON sso_group_sync_logs(user_id);
CREATE INDEX idx_sso_group_sync_logs_last_sync ON sso_group_sync_logs(last_sync);
CREATE INDEX idx_sso_group_sync_logs_status ON sso_group_sync_logs(status);

-- Table: auth_logs
-- Comprehensive authentication event logging
CREATE TABLE IF NOT EXISTS auth_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID, -- References users(id), NULL if auth failed
    auth_method VARCHAR(20) NOT NULL, -- 'password', 'sso', 'api_key', 'mfa'
    provider VARCHAR(100), -- SSO provider name if applicable
    status VARCHAR(20) NOT NULL, -- 'success', 'failed', 'blocked', 'expired'
    error_message TEXT,
    ip_address INET,
    user_agent TEXT,
    session_id UUID,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for auth log analysis
CREATE INDEX idx_auth_logs_user_id ON auth_logs(user_id);
CREATE INDEX idx_auth_logs_auth_method ON auth_logs(auth_method);
CREATE INDEX idx_auth_logs_provider ON auth_logs(provider);
CREATE INDEX idx_auth_logs_status ON auth_logs(status);
CREATE INDEX idx_auth_logs_created_at ON auth_logs(created_at);
CREATE INDEX idx_auth_logs_ip_address ON auth_logs(ip_address);

-- Table: sso_activity_logs
-- Admin SSO configuration activity logs
CREATE TABLE IF NOT EXISTS sso_activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID, -- References admin_users(id) when available
    action VARCHAR(50) NOT NULL, -- 'create_provider', 'update_provider', 'test_connection', etc.
    provider_id UUID, -- References sso_provider_configs(id)
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for admin activity tracking
CREATE INDEX idx_sso_activity_logs_admin_user_id ON sso_activity_logs(admin_user_id);
CREATE INDEX idx_sso_activity_logs_action ON sso_activity_logs(action);
CREATE INDEX idx_sso_activity_logs_provider_id ON sso_activity_logs(provider_id);
CREATE INDEX idx_sso_activity_logs_created_at ON sso_activity_logs(created_at);

-- Table: user_provisioning_rules
-- Rules for automatic user provisioning from SSO
CREATE TABLE IF NOT EXISTS user_provisioning_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES sso_provider_configs(id) ON DELETE CASCADE,
    rule_name VARCHAR(100) NOT NULL,
    conditions JSONB NOT NULL, -- Conditions for rule execution
    actions JSONB NOT NULL, -- Actions to perform (assign role, set attributes, etc.)
    is_enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 100, -- Lower number = higher priority
    created_by UUID, -- References admin_users(id) when available
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Index for rule processing
CREATE INDEX idx_user_provisioning_rules_provider_id ON user_provisioning_rules(provider_id);
CREATE INDEX idx_user_provisioning_rules_enabled ON user_provisioning_rules(is_enabled);
CREATE INDEX idx_user_provisioning_rules_priority ON user_provisioning_rules(priority);

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add update triggers for timestamp management
CREATE TRIGGER update_sso_provider_configs_updated_at
    BEFORE UPDATE ON sso_provider_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_provisioning_rules_updated_at
    BEFORE UPDATE ON user_provisioning_rules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE sso_provider_configs IS 'Configuration for SSO providers (Google, Azure AD, Okta, Auth0, etc.)';
COMMENT ON TABLE user_sso_links IS 'Links between internal users and their SSO provider accounts';
COMMENT ON TABLE sso_group_mappings IS 'Maps SSO provider groups to internal application roles';
COMMENT ON TABLE sso_group_sync_logs IS 'Audit log for group synchronization activities';
COMMENT ON TABLE auth_logs IS 'Comprehensive authentication event logging';
COMMENT ON TABLE sso_activity_logs IS 'Admin activity logs for SSO configuration changes';
COMMENT ON TABLE user_provisioning_rules IS 'Rules for automatic user provisioning from SSO providers';

-- Insert sample SSO provider configurations (disabled by default)
INSERT INTO sso_provider_configs (
    provider_name,
    provider_type,
    client_id,
    client_secret_encrypted,
    configuration,
    auto_create_users,
    allowed_domains,
    default_role,
    is_enabled
) VALUES 
(
    'google',
    'oidc',
    'your-google-client-id',
    'encrypted-client-secret',
    '{
        "redirect_uri": "https://your-app.com/auth/sso/callback",
        "hosted_domain": "your-company.com"
    }',
    true,
    ARRAY['your-company.com'],
    'agent',
    false
),
(
    'azure',
    'oidc',
    'your-azure-client-id',
    'encrypted-client-secret',
    '{
        "redirect_uri": "https://your-app.com/auth/sso/callback",
        "tenant_id": "your-tenant-id"
    }',
    true,
    ARRAY['your-company.com'],
    'agent',
    false
),
(
    'okta',
    'oidc',
    'your-okta-client-id',
    'encrypted-client-secret',
    '{
        "redirect_uri": "https://your-app.com/auth/sso/callback",
        "okta_domain": "your-org.okta.com",
        "authorization_server_id": "default"
    }',
    true,
    ARRAY['your-company.com'],
    'agent',
    false
),
(
    'auth0',
    'oidc',
    'your-auth0-client-id',
    'encrypted-client-secret',
    '{
        "redirect_uri": "https://your-app.com/auth/sso/callback",
        "auth0_domain": "your-org.auth0.com"
    }',
    true,
    ARRAY['your-company.com'],
    'agent',
    false
) ON CONFLICT (provider_name) DO NOTHING;

-- Insert default group mappings
INSERT INTO sso_group_mappings (
    provider_id,
    sso_group_name,
    internal_role,
    auto_assign
) 
SELECT 
    id,
    'Administrators',
    'admin',
    true
FROM sso_provider_configs
WHERE provider_name IN ('google', 'azure', 'okta', 'auth0')
ON CONFLICT (provider_id, sso_group_name) DO NOTHING;

INSERT INTO sso_group_mappings (
    provider_id,
    sso_group_name,
    internal_role,
    auto_assign
) 
SELECT 
    id,
    'Underwriters',
    'underwriter',
    true
FROM sso_provider_configs
WHERE provider_name IN ('google', 'azure', 'okta', 'auth0')
ON CONFLICT (provider_id, sso_group_name) DO NOTHING;

-- Insert default provisioning rules
INSERT INTO user_provisioning_rules (
    provider_id,
    rule_name,
    conditions,
    actions,
    is_enabled,
    priority
)
SELECT 
    id,
    'Default User Provisioning',
    '{
        "email_verified": true,
        "domain_allowed": true
    }',
    '{
        "assign_role": "agent",
        "mark_active": true,
        "send_welcome_email": false
    }',
    true,
    100
FROM sso_provider_configs
WHERE provider_name IN ('google', 'azure', 'okta', 'auth0')
ON CONFLICT DO NOTHING;