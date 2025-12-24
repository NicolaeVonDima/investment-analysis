# User System & Portfolio Versioning Implementation Plan

> **Version**: 1.0.0  
> **Created**: 2025-12-24  
> **Status**: Draft  

---

## Executive Summary

This plan outlines the implementation of a complete user management system with:
- Role-based access control (Freemium, Paid, Admin)
- User hierarchy with dependants (family invitations)
- Model portfolio versioning with user opt-in/opt-out
- Reset functionality for portfolios
- Admin panel for configuration

---

## 1. Core Concepts

### 1.1 Model Portfolio Versioning

**Problem**: Model portfolios (Aggressive Growth, Balanced Allocation, Income Focused) will change over time. Users who have customized these portfolios shouldn't be affected, but should have the option to adopt new versions.

**Solution**: Implement a versioned template system:

```
ModelPortfolioTemplate (Admin-defined, immutable once published)
├── version: "1.0.0" (semver)
├── name: "Aggressive Growth"
├── allocation: {...}
├── published_at: timestamp
├── is_current: boolean
└── changelog: "Initial release"

UserPortfolioInstance (User's copy, mutable)
├── user_id: FK
├── based_on_template_id: FK (nullable - custom portfolios have none)
├── based_on_version: "1.0.0"
├── current_values: {...} (user's customizations)
├── original_values: {...} (snapshot at adoption)
├── is_customized: boolean
└── created_at: timestamp
```

**Versioning Strategy**:
- **Major** (X.0.0): Fundamental strategy change, new assets, removed assets
- **Minor** (1.X.0): Allocation percentage changes, goal updates
- **Patch** (1.0.X): Typos, description improvements

### 1.2 Reset Functionality

Three types of reset:
1. **Reset to Original**: Restore to values when user first adopted the template
2. **Reset to Current Version**: Restore to the template's current published values
3. **Update to Latest Version**: Adopt the newest template version (with confirmation)

---

## 2. Database Schema Design

### 2.1 User Tables

```sql
-- Core user table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    password_hash VARCHAR(255) NOT NULL,
    
    -- Profile
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    avatar_url VARCHAR(500),
    
    -- Subscription
    role VARCHAR(20) NOT NULL DEFAULT 'freemium', -- 'freemium', 'paid', 'admin'
    subscription_tier VARCHAR(50), -- 'basic', 'premium', 'enterprise' (for paid users)
    subscription_expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Hierarchy
    parent_user_id UUID REFERENCES users(id), -- For dependants
    is_primary_account BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE
);

-- User sessions (for JWT refresh tokens)
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    device_info JSONB,
    ip_address INET,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Family/dependant invitations
CREATE TABLE user_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inviter_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    invitee_email VARCHAR(255) NOT NULL,
    family_member_id VARCHAR(100), -- Links to FamilyMember.id
    
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'accepted', 'declined', 'expired'
    invitation_token VARCHAR(255) UNIQUE NOT NULL,
    
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    accepted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 2.2 Portfolio Template Tables

```sql
-- Admin-defined model portfolio templates (immutable versions)
CREATE TABLE portfolio_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key VARCHAR(50) NOT NULL, -- 'aggressive_growth', 'balanced', 'income_focused'
    version VARCHAR(20) NOT NULL, -- Semver: "1.0.0"
    
    -- Template data
    name VARCHAR(100) NOT NULL,
    goal TEXT,
    risk_label VARCHAR(50),
    horizon VARCHAR(50),
    overperform_strategy JSONB,
    allocation JSONB NOT NULL,
    rules JSONB NOT NULL,
    strategy JSONB,
    
    -- Versioning metadata
    is_current BOOLEAN DEFAULT FALSE, -- Only one version per template_key is current
    changelog TEXT,
    published_at TIMESTAMP WITH TIME ZONE,
    
    -- Admin tracking
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(template_key, version)
);

-- User's portfolio instances (derived from templates or custom)
CREATE TABLE user_portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- Template relationship (null for custom portfolios)
    template_id UUID REFERENCES portfolio_templates(id),
    adopted_version VARCHAR(20), -- Version when user adopted/last updated
    
    -- Current user values (their customizations)
    name VARCHAR(100) NOT NULL,
    color VARCHAR(20) NOT NULL,
    capital DECIMAL(15,2) NOT NULL,
    goal TEXT,
    risk_label VARCHAR(50),
    horizon VARCHAR(50),
    selected_strategy VARCHAR(100),
    overperform_strategy JSONB,
    allocation JSONB NOT NULL,
    rules JSONB NOT NULL,
    strategy JSONB,
    
    -- Snapshot of original values when adopted (for reset)
    original_values JSONB,
    
    -- Flags
    is_customized BOOLEAN DEFAULT FALSE, -- Has user modified from template?
    is_member_portfolio BOOLEAN DEFAULT FALSE, -- Linked to a family member?
    family_member_id VARCHAR(100), -- Links to family_members.id
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Track available template updates for users
CREATE TABLE user_template_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    user_portfolio_id UUID REFERENCES user_portfolios(id) ON DELETE CASCADE,
    new_template_id UUID REFERENCES portfolio_templates(id),
    
    status VARCHAR(20) DEFAULT 'available', -- 'available', 'applied', 'dismissed'
    notified_at TIMESTAMP WITH TIME ZONE,
    applied_at TIMESTAMP WITH TIME ZONE,
    
    UNIQUE(user_portfolio_id, new_template_id)
);
```

### 2.3 Updated Family Member Table

```sql
-- Family members now linked to users
ALTER TABLE family_members ADD COLUMN user_id UUID REFERENCES users(id);
ALTER TABLE family_members ADD COLUMN linked_user_id UUID REFERENCES users(id); -- If invited & accepted
ALTER TABLE family_members ADD COLUMN email VARCHAR(255); -- For invitations
ALTER TABLE family_members ADD COLUMN color VARCHAR(20);
```

### 2.4 Admin Configuration Tables

```sql
-- System-wide configuration
CREATE TABLE system_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit log for admin actions
CREATE TABLE admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50), -- 'user', 'template', 'config'
    entity_id VARCHAR(100),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 3. Role-Based Access Control (RBAC)

### 3.1 Role Definitions

| Role | Description | Capabilities |
|------|-------------|--------------|
| **Freemium** | Free tier user | - 1 family member (self)<br>- Access to all 3 model portfolios<br>- Basic simulation (20 years)<br>- Can customize allocations<br>- Can reset to defaults |
| **Paid** | Subscription user | - All Freemium features<br>- Unlimited family members<br>- Extended simulation (50 years)<br>- Advanced analytics<br>- Custom scenarios<br>- Export features<br>- Invite dependants |
| **Admin** | Platform administrator | - All Paid features<br>- User management<br>- Template versioning<br>- System configuration<br>- Analytics dashboard |

### 3.2 Permission Matrix

```typescript
const PERMISSIONS = {
  // Portfolio
  'portfolio:create': ['freemium', 'paid', 'admin'],
  'portfolio:read': ['freemium', 'paid', 'admin'],
  'portfolio:update': ['freemium', 'paid', 'admin'],
  'portfolio:delete': ['paid', 'admin'],
  'portfolio:reset': ['freemium', 'paid', 'admin'],
  
  // Family Members
  'family:create': ['paid', 'admin'],
  'family:read': ['freemium', 'paid', 'admin'],
  'family:invite': ['paid', 'admin'],
  
  // Templates (Admin only)
  'template:create': ['admin'],
  'template:update': ['admin'],
  'template:publish': ['admin'],
  
  // Users (Admin only)
  'user:list': ['admin'],
  'user:update': ['admin'],
  'user:delete': ['admin'],
  
  // System (Admin only)
  'config:read': ['admin'],
  'config:update': ['admin'],
};
```

---

## 4. API Design

### 4.1 Authentication Endpoints

```
POST   /api/auth/register          # New user registration
POST   /api/auth/login             # Login (returns JWT)
POST   /api/auth/logout            # Invalidate session
POST   /api/auth/refresh           # Refresh access token
POST   /api/auth/forgot-password   # Request password reset
POST   /api/auth/reset-password    # Reset password with token
POST   /api/auth/verify-email      # Verify email address
GET    /api/auth/me                # Get current user
```

### 4.2 User Portfolio Endpoints

```
GET    /api/portfolios                     # List user's portfolios
POST   /api/portfolios                     # Create portfolio (from template or custom)
GET    /api/portfolios/:id                 # Get portfolio details
PUT    /api/portfolios/:id                 # Update portfolio
DELETE /api/portfolios/:id                 # Delete portfolio

# Reset functionality
POST   /api/portfolios/:id/reset           # Reset to original values
POST   /api/portfolios/:id/reset-to-current # Reset to current template version
POST   /api/portfolios/:id/update-version  # Update to latest template version

# Version info
GET    /api/portfolios/:id/version-info    # Check for available updates
```

### 4.3 Template Endpoints (Public + Admin)

```
# Public
GET    /api/templates                      # List current templates
GET    /api/templates/:key                 # Get current version of template
GET    /api/templates/:key/versions        # List all versions

# Admin only
POST   /api/admin/templates                # Create new template version
PUT    /api/admin/templates/:id/publish    # Publish a version
GET    /api/admin/templates/:id/adopters   # List users using this version
```

### 4.4 Family & Invitation Endpoints

```
GET    /api/family                         # List family members
POST   /api/family                         # Add family member
PUT    /api/family/:id                     # Update family member
DELETE /api/family/:id                     # Remove family member

POST   /api/family/:id/invite              # Send invitation email
GET    /api/invitations/accept/:token      # Accept invitation
POST   /api/invitations/decline/:token     # Decline invitation
```

### 4.5 Admin Endpoints

```
# User Management
GET    /api/admin/users                    # List all users (paginated)
GET    /api/admin/users/:id                # Get user details
PUT    /api/admin/users/:id                # Update user (role, subscription)
DELETE /api/admin/users/:id                # Delete user
POST   /api/admin/users/:id/impersonate    # Impersonate user

# Dashboard
GET    /api/admin/stats                    # Platform statistics
GET    /api/admin/audit-log                # Admin action log

# System Config
GET    /api/admin/config                   # Get all config
PUT    /api/admin/config/:key              # Update config
```

---

## 5. Frontend Components

### 5.1 New Pages

```
/login                 # Login page
/register              # Registration page
/forgot-password       # Password reset request
/reset-password/:token # Password reset form
/verify-email/:token   # Email verification

/settings              # User settings
/settings/profile      # Profile settings
/settings/subscription # Subscription management
/settings/security     # Password, sessions

/admin                 # Admin dashboard
/admin/users           # User management
/admin/templates       # Template versioning
/admin/config          # System configuration
```

### 5.2 Portfolio Reset UI

```tsx
// ResetButton component for each portfolio
interface ResetOptions {
  type: 'original' | 'current_version' | 'latest_version';
  templateVersion?: string;
}

// Modal showing:
// - "Reset to Original" (your starting values)
// - "Reset to v1.2.0" (current template version)
// - "Update to v2.0.0" (if newer available, with changelog)
```

### 5.3 Version Update Banner

```tsx
// Shown when template has newer version available
<VersionUpdateBanner
  portfolioName="Aggressive Growth"
  currentVersion="1.0.0"
  latestVersion="1.2.0"
  changelog="Updated TVBETETF allocation from 55% to 50%..."
  onUpdate={() => {...}}
  onDismiss={() => {...}}
/>
```

### 5.4 Admin Components

```
AdminLayout
├── Sidebar (navigation)
├── UserTable (searchable, sortable, paginated)
├── TemplateEditor (create/edit template versions)
├── TemplateVersionHistory (version timeline)
├── ConfigPanel (key-value editor)
└── AuditLogViewer (filterable log)
```

---

## 6. Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal**: Basic auth and user system

- [ ] Database migrations for user tables
- [ ] JWT authentication (access + refresh tokens)
- [ ] Password hashing (bcrypt/argon2)
- [ ] Login/Register/Logout endpoints
- [ ] Basic auth middleware
- [ ] Frontend auth pages (login, register)
- [ ] Auth context/state management
- [ ] Protected route wrapper

### Phase 2: Portfolio Ownership (Week 3)
**Goal**: Link portfolios to users

- [ ] Migrate existing portfolios to user_portfolios
- [ ] Add user_id to all portfolio queries
- [ ] Update save/load endpoints for user context
- [ ] Handle anonymous/demo mode
- [ ] Frontend: Auth-aware data fetching

### Phase 3: Template Versioning (Week 4-5)
**Goal**: Versioned model portfolios with reset

- [ ] Create portfolio_templates table
- [ ] Seed initial template versions (1.0.0)
- [ ] Implement template adoption logic
- [ ] Reset to original endpoint
- [ ] Reset to current version endpoint
- [ ] Update to latest version endpoint
- [ ] Frontend: Reset button UI
- [ ] Frontend: Version update banner

### Phase 4: Role-Based Access (Week 6)
**Goal**: Freemium/Paid/Admin roles

- [ ] Permission middleware
- [ ] Role-based feature gates
- [ ] Subscription management (manual for now)
- [ ] Frontend: Feature gates based on role
- [ ] Frontend: Upgrade prompts for freemium

### Phase 5: Family Invitations (Week 7)
**Goal**: Invite dependants via email

- [ ] Email service integration (SendGrid/SES)
- [ ] Invitation flow endpoints
- [ ] Linked user accounts
- [ ] Invitation email templates
- [ ] Frontend: Invite modal
- [ ] Frontend: Invitation acceptance page

### Phase 6: Admin Panel (Week 8-9)
**Goal**: Full admin functionality

- [ ] Admin-only route protection
- [ ] User management CRUD
- [ ] Template version management
- [ ] Template publishing workflow
- [ ] System config management
- [ ] Audit logging
- [ ] Admin dashboard with stats
- [ ] Frontend: Admin pages

### Phase 7: Polish & Security (Week 10)
**Goal**: Production-ready

- [ ] Rate limiting
- [ ] Security audit
- [ ] Email verification flow
- [ ] Password reset flow
- [ ] Session management (logout all devices)
- [ ] GDPR: Data export, account deletion
- [ ] Documentation

---

## 7. Data Migration Strategy

### 7.1 Existing Data Handling

Current state: All data is shared (no user concept)

Migration approach:
1. Create a "default" admin user
2. Assign all existing portfolios to this user as templates
3. Create initial template versions from current portfolios
4. New users get fresh copies from templates

```python
def migrate_existing_data():
    # 1. Create admin user
    admin = create_user(email="admin@system", role="admin")
    
    # 2. Convert existing portfolios to templates
    for portfolio in get_all_portfolios():
        if portfolio.name in ['Aggressive Growth', 'Balanced Allocation', 'Income Focused']:
            create_template(
                template_key=slugify(portfolio.name),
                version="1.0.0",
                data=portfolio_to_template_data(portfolio),
                created_by=admin.id,
                is_current=True
            )
    
    # 3. Keep "Current Allocation" as user-specific (not a template)
```

### 7.2 Backward Compatibility

- Keep existing `/api/data/save` and `/api/data/load` endpoints
- Add optional `?user_id=` parameter (for admin impersonation)
- Anonymous usage saves to localStorage (demo mode)
- Prompt to register to persist data

---

## 8. Security Considerations

### 8.1 Authentication

- **Passwords**: Argon2id hashing (bcrypt fallback)
- **Tokens**: 
  - Access token: 15 min expiry, in memory
  - Refresh token: 7 day expiry, HttpOnly cookie
- **Rate limiting**: 5 login attempts per 15 min per IP

### 8.2 Authorization

- All endpoints verify user ownership of resources
- Admin actions require explicit admin role check
- Template publishing requires approval workflow (optional)

### 8.3 Data Protection

- Encrypt PII at rest (email, names)
- Audit logging for all admin actions
- GDPR compliance: Export, deletion rights

---

## 9. Technical Stack Additions

### Backend
```
# requirements.txt additions
python-jose[cryptography]  # JWT
passlib[bcrypt,argon2]     # Password hashing
python-multipart           # Form data
emails                     # Email sending
redis                      # Session storage (optional)
```

### Frontend
```json
// package.json additions
{
  "dependencies": {
    "@tanstack/react-query": "^5.x",  // Data fetching
    "zustand": "^4.x",                 // Auth state
    "react-hook-form": "^7.x",         // Forms
    "zod": "^3.x"                      // Validation
  }
}
```

---

## 10. Open Questions

1. **Payment Integration**: Stripe? Manual subscription management initially?
2. **Email Provider**: SendGrid, AWS SES, or self-hosted?
3. **Demo Mode**: Allow anonymous usage with localStorage persistence?
4. **Template Approval**: Should new template versions require approval before publish?
5. **Notification System**: In-app notifications for version updates?

---

## 11. Success Metrics

- User registration/conversion rate
- Portfolio reset usage frequency
- Template update adoption rate
- Admin workflow efficiency
- User retention (30/60/90 day)

---

## Appendix A: Template Version Schema

```json
{
  "template_key": "aggressive_growth",
  "version": "1.2.0",
  "name": "Aggressive Growth",
  "goal": "Maximum growth potential...",
  "risk_label": "Risk: High",
  "horizon": "2026 - 2029",
  "overperform_strategy": {
    "title": "Harvest & Rotate",
    "content": ["..."]
  },
  "allocation": {
    "vwce": 35,
    "tvbetetf": 50,
    "ernx": 5,
    "ayeg": 10,
    "fidelis": 0
  },
  "rules": {
    "tvbetetfConditional": false
  },
  "changelog": "Reduced TVBETETF from 55% to 50%, added 5% ERNX for stability",
  "is_current": true,
  "published_at": "2025-01-15T10:00:00Z"
}
```

---

## Appendix B: Reset Flow Diagram

```
User clicks "Reset" on Portfolio
            │
            ▼
    ┌───────────────────┐
    │   Reset Options   │
    │     Modal         │
    └───────┬───────────┘
            │
    ┌───────┼───────┬────────────────┐
    ▼       ▼       ▼                ▼
 Cancel  Original  Current      Latest
            │     Version      Version
            │       │              │
            ▼       ▼              ▼
        Restore  Restore       Show
        saved    template      changelog
        snapshot v1.0.0        & confirm
            │       │              │
            └───────┴──────┬───────┘
                           ▼
                    Update portfolio
                    in database
                           │
                           ▼
                    Refresh UI
```

---

*Document maintained by: System*  
*Last updated: 2025-12-24*

