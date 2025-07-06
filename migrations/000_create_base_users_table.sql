-- Base Users Table for SSO Integration
-- This creates the users table expected by the SSO system

-- Table: users
-- Core user accounts table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT, -- Can be NULL for SSO-only users
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'agent', -- 'agent', 'underwriter', 'admin', 'system'
    is_active BOOLEAN DEFAULT true,
    is_email_verified BOOLEAN DEFAULT false,
    phone_number VARCHAR(20),
    last_login_at TIMESTAMPTZ,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMPTZ,
    email_verification_token TEXT,
    password_reset_token TEXT,
    password_reset_expires TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_last_login_at ON users(last_login_at);
CREATE INDEX idx_users_created_at ON users(created_at);

-- Function to normalize email addresses
CREATE OR REPLACE FUNCTION normalize_user_email() RETURNS TRIGGER AS $$
BEGIN
    NEW.email = LOWER(TRIM(NEW.email));
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to normalize email on insert/update
CREATE TRIGGER normalize_user_email_trigger
    BEFORE INSERT OR UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION normalize_user_email();

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update timestamp
CREATE TRIGGER update_users_updated_at_trigger
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_users_updated_at();

-- Validate role values
ALTER TABLE users ADD CONSTRAINT check_valid_role 
    CHECK (role IN ('customer', 'agent', 'underwriter', 'adjuster', 'admin', 'system'));

-- Validate email format (additional check beyond unique constraint)
ALTER TABLE users ADD CONSTRAINT check_email_format 
    CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');

-- Add comments
COMMENT ON TABLE users IS 'Core user accounts for the application with SSO support';
COMMENT ON COLUMN users.password_hash IS 'Hashed password - can be NULL for SSO-only users';
COMMENT ON COLUMN users.role IS 'User role: customer, agent, underwriter, adjuster, admin, system';
COMMENT ON COLUMN users.is_active IS 'Whether the user account is active and can log in';
COMMENT ON COLUMN users.failed_login_attempts IS 'Number of consecutive failed login attempts';
COMMENT ON COLUMN users.locked_until IS 'Account locked until this timestamp';

-- Insert a default system admin user (disabled, needs manual activation)
INSERT INTO users (
    email,
    password_hash,
    first_name,
    last_name,
    role,
    is_active,
    is_email_verified
) VALUES (
    'admin@system.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewgktKCx3Dw.kHwu', -- 'admin123!' - change this!
    'System',
    'Administrator',
    'admin',
    false, -- Disabled by default for security
    true
) ON CONFLICT (email) DO NOTHING;

-- Table: admin_users (for admin interface SSO)
-- Separate admin users table for administrative access
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT, -- Can be NULL for SSO-only admins
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'admin', -- 'admin', 'super_admin'
    permissions TEXT[] DEFAULT ARRAY[]::TEXT[], -- Admin permissions
    is_active BOOLEAN DEFAULT true,
    is_email_verified BOOLEAN DEFAULT false,
    last_login_at TIMESTAMPTZ,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMPTZ,
    mfa_enabled BOOLEAN DEFAULT false,
    mfa_secret TEXT, -- TOTP secret for MFA
    backup_codes TEXT[], -- MFA backup codes
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for admin users
CREATE INDEX idx_admin_users_email ON admin_users(email);
CREATE INDEX idx_admin_users_role ON admin_users(role);
CREATE INDEX idx_admin_users_is_active ON admin_users(is_active);
CREATE INDEX idx_admin_users_last_login_at ON admin_users(last_login_at);

-- Normalize admin email trigger
CREATE TRIGGER normalize_admin_email_trigger
    BEFORE INSERT OR UPDATE ON admin_users
    FOR EACH ROW
    EXECUTE FUNCTION normalize_user_email();

-- Update admin timestamp trigger
CREATE TRIGGER update_admin_users_updated_at_trigger
    BEFORE UPDATE ON admin_users
    FOR EACH ROW
    EXECUTE FUNCTION update_users_updated_at();

-- Validate admin role
ALTER TABLE admin_users ADD CONSTRAINT check_valid_admin_role 
    CHECK (role IN ('admin', 'super_admin'));

-- Add comments for admin users
COMMENT ON TABLE admin_users IS 'Administrative users with access to admin interface';
COMMENT ON COLUMN admin_users.permissions IS 'Array of specific admin permissions';
COMMENT ON COLUMN admin_users.mfa_enabled IS 'Whether MFA is enabled for this admin';
COMMENT ON COLUMN admin_users.mfa_secret IS 'TOTP secret for MFA authentication';
COMMENT ON COLUMN admin_users.backup_codes IS 'MFA backup codes for account recovery';

-- Insert a default super admin (disabled, needs manual activation)  
INSERT INTO admin_users (
    email,
    password_hash,
    first_name,
    last_name,
    role,
    permissions,
    is_active,
    is_email_verified
) VALUES (
    'superadmin@system.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewgktKCx3Dw.kHwu', -- 'admin123!' - change this!
    'Super',
    'Administrator',
    'super_admin',
    ARRAY['admin:read', 'admin:write', 'system:manage', 'users:manage', 'sso:manage'],
    false, -- Disabled by default for security
    true
) ON CONFLICT (email) DO NOTHING;