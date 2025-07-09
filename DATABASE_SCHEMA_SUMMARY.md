# Database Schema Summary

## Overview
This document provides a comprehensive overview of all database tables created by the migration system. The schema is designed for a production-ready insurance policy decision and management system.

## Migration Status
- **Latest Migration**: `009_add_missing_oauth2_tables.py`
- **Total Migrations**: 9 files
- **Database Engine**: PostgreSQL with asyncpg driver
- **Migration Tool**: Alembic

## Core Tables (Migration 001)

### `customers`
- **Primary Key**: `id` (String, 36 chars)
- **Key Fields**: `external_id`, `data` (JSONB)
- **Indexes**: GIN index on JSONB data, external_id index
- **Purpose**: Customer information storage with flexible JSON data

### `policies`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `policy_number`, `customer_id`, `data` (JSONB)
- **Status**: active, inactive, cancelled, expired, pending
- **Indexes**: Policy number, customer ID, status, date ranges
- **Purpose**: Policy management with flexible JSON data structure

### `claims`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `claim_number`, `policy_id`, `amount_claimed`, `amount_approved`
- **Status**: submitted, under_review, approved, denied, withdrawn, closed
- **Indexes**: Claim number, policy ID, status, submission date
- **Purpose**: Claims processing and tracking

## User Management (Migration 002)

### `users`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `email`, `password_hash`, `first_name`, `last_name`, `role`
- **Roles**: agent, underwriter, admin, system
- **Indexes**: Email, role, active status
- **Purpose**: User authentication and authorization

### `quotes`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `quote_number`, `customer_id`, `product_type`, `state`
- **Product Types**: auto, home, renters, life
- **Status**: draft, calculating, quoted, expired, bound, declined
- **Complex Fields**: `vehicle_info`, `property_info`, `drivers` (JSONB)
- **AI Fields**: `ai_risk_score`, `conversion_probability`
- **Purpose**: Comprehensive quote management with versioning

## Rating Engine (Migration 003)

### `rate_tables`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `state`, `product_type`, `coverage_type`, `base_rate`
- **Factor Fields**: `territory_factors`, `vehicle_factors`, `driver_factors`, `credit_factors` (JSONB)
- **Purpose**: Base rate storage with flexible factor multipliers

### `discount_rules`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `rule_name`, `discount_type`, `discount_value`
- **Purpose**: Discount calculation rules and eligibility

### `surcharge_rules`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `rule_name`, `surcharge_type`, `surcharge_value`
- **Purpose**: Surcharge calculation for risk factors

## Security & Compliance (Migration 004)

### `sso_providers`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `provider_name`, `provider_type`, `client_id`
- **Provider Types**: google, azure, okta, auth0, saml, oidc
- **Purpose**: SSO provider configuration management

### `oauth2_clients`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `client_id`, `client_secret_hash`, `client_name`
- **Settings**: `redirect_uris`, `allowed_grant_types`, `allowed_scopes` (JSONB)
- **Rate Limiting**: Per-minute and per-hour limits
- **Purpose**: OAuth2 client application management

### `user_mfa_settings`
- **Primary Key**: `user_id` (UUID)
- **MFA Types**: TOTP, WebAuthn, SMS, Recovery codes
- **Purpose**: Multi-factor authentication settings per user

### `user_sessions`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `user_id`, `session_token_hash`, `ip_address`
- **Purpose**: Session management and tracking

### `audit_logs` (Partitioned)
- **Primary Key**: `id` (UUID), `created_at` (Timestamp)
- **Partitioning**: Monthly partitions by creation date
- **Key Fields**: `user_id`, `action`, `resource_type`, `resource_id`
- **Security**: Risk scoring and security alerts
- **Purpose**: Comprehensive audit trail with SOC 2 compliance

## OAuth2 Tables (Migration 009) - NEW

### `oauth2_refresh_tokens`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `client_id`, `user_id`, `token_hash`, `access_token_hash`
- **Features**: Token rotation, revocation tracking, security metadata
- **Indexes**: Client ID, user ID, expiration, revocation status
- **Purpose**: Secure refresh token storage with rotation support

### `oauth2_token_logs`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `client_id`, `user_id`, `token_type`, `action`
- **Actions**: issued, refreshed, revoked, expired, used, introspected
- **Security**: Risk scoring and security flags
- **Purpose**: Comprehensive OAuth2 token audit trail

### `oauth2_authorization_codes`
- **Primary Key**: `id` (UUID)
- **Key Fields**: `client_id`, `user_id`, `code_hash`, `redirect_uri`
- **PKCE Support**: `code_challenge`, `code_challenge_method`
- **OpenID Connect**: `nonce` support
- **Purpose**: Authorization code flow with PKCE security

## Database Functions

### Utility Functions
- `update_updated_at_column()`: Automatic timestamp updates
- `generate_quote_number()`: Sequential quote number generation
- `cleanup_expired_oauth2_tokens()`: Token cleanup automation
- `revoke_user_tokens()`: Bulk token revocation
- `create_monthly_audit_partition()`: Automatic partition creation

### Validation Functions
- `validate_grant_types()`: OAuth2 grant type validation

## Database Features

### Performance Optimizations
- **GIN Indexes**: For JSONB column searches
- **Composite Indexes**: For common query patterns
- **Partitioning**: Monthly partitions for audit logs
- **Connection Pooling**: asyncpg with connection pooling

### Security Features
- **Encrypted Fields**: Client secrets, MFA settings, phone numbers
- **Hash Storage**: Password hashes, token hashes
- **IP Tracking**: Session and token IP addresses
- **Risk Scoring**: Numeric risk scores (0.00-1.00)

### Compliance Features
- **Audit Trails**: Complete action logging
- **Data Retention**: Configurable retention policies
- **Foreign Key Constraints**: Data integrity enforcement
- **Check Constraints**: Business rule validation

## Deployment Instructions

### Prerequisites
1. PostgreSQL 13+ with UUID extension
2. Database user with CREATE/ALTER permissions
3. Environment variables configured (DATABASE_URL)

### Migration Application
```bash
# Ensure database is running
psql $DATABASE_URL -c "SELECT version();"

# Run migrations
uv run alembic upgrade head

# Verify migration status
uv run alembic current
uv run alembic history
```

### Post-Migration Verification
```sql
-- Check all tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Verify partitions for audit_logs
SELECT schemaname, tablename, partitiontype 
FROM pg_partitions 
WHERE tablename LIKE 'audit_logs%';

-- Check function creation
SELECT proname FROM pg_proc 
WHERE proname IN (
    'update_updated_at_column',
    'generate_quote_number',
    'cleanup_expired_oauth2_tokens',
    'revoke_user_tokens',
    'create_monthly_audit_partition'
);
```

## Table Dependencies

### Foreign Key Relationships
```
customers (root)
├── policies (customer_id)
│   ├── claims (policy_id)
│   └── quotes (converted_to_policy_id)
├── users (root)
│   ├── quotes (created_by, updated_by)
│   ├── user_mfa_settings (user_id)
│   ├── user_sessions (user_id)
│   ├── oauth2_refresh_tokens (user_id)
│   ├── oauth2_token_logs (user_id)
│   └── oauth2_authorization_codes (user_id)
├── oauth2_clients (root)
│   ├── oauth2_refresh_tokens (client_id)
│   ├── oauth2_token_logs (client_id)
│   └── oauth2_authorization_codes (client_id)
├── sso_providers (root)
│   └── user_sessions (sso_provider_id)
└── quotes (root)
    └── quotes (parent_quote_id - self-reference)
```

## Missing Tables Resolution

The migration `009_add_missing_oauth2_tables.py` resolves all critical missing tables that were referenced in the codebase:

✅ **Resolved Issues:**
1. `oauth2_refresh_tokens` - Now created with full token rotation support
2. `oauth2_token_logs` - Now created with comprehensive audit logging
3. `oauth2_authorization_codes` - Now created with PKCE support
4. All foreign key constraints properly established
5. Performance indexes added for all common queries
6. Security features (IP tracking, risk scoring) implemented

The database schema is now complete and ready for production deployment.