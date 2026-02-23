# StaffHub — Database Design Document

> **Version:** 1.0  
> **Database:** MySQL 8.x (InnoDB, utf8mb4)  
> **Migrations:** Alembic + SQLAlchemy  
> **Date:** 2026-02-23

---

## Table of Contents

1. [Overview](#overview)  
2. [ER Diagram](#er-diagram)  
3. [Domain 1 — Identity & Access Management](#domain-1--identity--access-management)  
4. [Domain 2 — Accommodation](#domain-2--accommodation)  
5. [Domain 3 — Loans (Future)](#domain-3--loans-future)  
6. [Business Rules Reference](#business-rules-reference)  
7. [Index Strategy](#index-strategy)  
8. [Seed Data](#seed-data)  
9. [Running Migrations](#running-migrations)  
10. [Development Roadmap](#development-roadmap)

---

## Overview

StaffHub is a multi-organization personnel welfare system. The database is designed around three logical domains:

| Domain | Status | Description |
|--------|--------|-------------|
| **Identity & Access** | V1 (implemented) | Organizations, users, profiles, children, RBAC, OTP auth |
| **Accommodation** | V1 (implemented) | Places, rooms, pricing, reservations, discount tiers, special plans |
| **Loans** | Future (V2) | Bank integrations, loan caps, budgets, requests, letters, outcomes |

The schema is designed so that the loans domain can be added later without altering any existing tables.

---

## ER Diagram

```mermaid
erDiagram
    organizations ||--o{ users : "has"
    users ||--|| user_profiles : "has"
    users ||--o{ user_children : "has"
    users ||--o{ user_roles : "assigned"
    roles ||--o{ user_roles : "assigned"
    roles ||--o{ role_permissions : "grants"
    permissions ||--o{ role_permissions : "granted_by"
    users ||--o{ otp_tokens : "has"

    organizations ||--o{ org_place_access : "allowed"
    places ||--o{ org_place_access : "restricted_to"
    places ||--o{ place_rooms : "contains"
    room_types ||--o{ place_rooms : "typed_as"
    places ||--o{ place_availability : "blocked"
    places ||--o{ pricing_rules : "priced"
    room_types ||--o{ pricing_rules : "priced"

    users ||--o{ special_plans : "eligible"
    users ||--o{ discount_usage : "tracks"
    users ||--o{ reservations : "creates"
    organizations ||--o{ reservations : "belongs"
    places ||--o{ reservations : "at"
    room_types ||--o{ reservations : "for"
    special_plans ||--o| reservations : "used_in"
    reservations ||--o{ reservation_guests : "includes"

    organizations {
        bigint id PK
        varchar code UK
        varchar name
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    users {
        bigint id PK
        bigint org_id FK
        varchar username UK
        varchar password_hash
        varchar phone_number
        enum auth_method
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    user_profiles {
        bigint user_id PK_FK
        varchar first_name
        varchar last_name
        varchar national_id UK
        date birth_date
        enum marital_status
        date marriage_date
        varchar grade
        smallint number_of_children
    }
    user_children {
        bigint id PK
        bigint user_id FK
        varchar first_name
        date birth_date
        datetime created_at
    }
    roles {
        bigint id PK
        varchar key UK
        varchar name
        enum scope
        text description
    }
    permissions {
        bigint id PK
        varchar key UK
        text description
    }
    role_permissions {
        bigint role_id PK_FK
        bigint permission_id PK_FK
    }
    user_roles {
        bigint user_id PK_FK
        bigint role_id PK_FK
        datetime assigned_at
    }
    otp_tokens {
        bigint id PK
        bigint user_id FK
        varchar code
        datetime expires_at
        boolean is_used
        datetime created_at
    }
    places {
        bigint id PK
        varchar city
        varchar name
        boolean is_active
        datetime created_at
    }
    room_types {
        bigint id PK
        varchar key UK
        varchar label
        smallint max_capacity
    }
    place_rooms {
        bigint id PK
        bigint place_id FK
        bigint room_type_id FK
        int total_rooms
    }
    org_place_access {
        bigint id PK
        bigint org_id FK
        bigint place_id FK
        boolean is_allowed
    }
    place_availability {
        bigint id PK
        bigint place_id FK
        bigint room_type_id FK
        date date
        int blocked_count
        bigint blocked_by_user_id FK
    }
    pricing_rules {
        bigint id PK
        bigint place_id FK
        bigint room_type_id FK
        enum person_group
        decimal price_per_night
        date effective_from
        date effective_to
    }
    special_plans {
        bigint id PK
        bigint user_id FK
        enum plan_type
        date eligible_from
        date eligible_until
        boolean is_used
        datetime created_at
    }
    discount_usage {
        bigint id PK
        bigint user_id FK
        smallint year
        smallint usage_count
    }
    reservations {
        bigint id PK
        bigint user_id FK
        bigint org_id FK
        bigint place_id FK
        bigint room_type_id FK
        date check_in_date
        date check_out_date
        smallint nights
        enum status
        datetime admin_deadline_at
        decimal total_price
        smallint discount_percent
        decimal final_price
        bigint special_plan_id FK
        bigint reviewed_by_user_id FK
        datetime reviewed_at
        datetime created_at
        datetime updated_at
    }
    reservation_guests {
        bigint id PK
        bigint reservation_id FK
        enum person_type
        varchar name
        boolean is_extra
        decimal extra_charge
    }
```

---

## Domain 1 — Identity & Access Management

### `organizations`

Each client organization in the system.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| code | VARCHAR(32) | UNIQUE, NOT NULL | Short identifier (e.g. "ORG01") |
| name | VARCHAR(255) | NOT NULL | Display name |
| is_active | BOOLEAN | DEFAULT TRUE | Soft-delete flag |
| created_at | DATETIME | NOT NULL | Auto-set |
| updated_at | DATETIME | NOT NULL | Auto-updated |

### `users`

Login accounts. One user per person per organization.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| org_id | BIGINT | FK → organizations, NOT NULL | |
| username | VARCHAR(128) | UNIQUE, NOT NULL | |
| password_hash | VARCHAR(255) | NULLABLE | NULL for OTP-only users |
| phone_number | VARCHAR(20) | NULLABLE | For SMS/OTP login |
| auth_method | ENUM | NOT NULL, DEFAULT 'PASSWORD' | PASSWORD, OTP, or BOTH |
| is_active | BOOLEAN | DEFAULT TRUE | |
| created_at | DATETIME | NOT NULL | |
| updated_at | DATETIME | NOT NULL | |

### `user_profiles`

One-to-one personal data extension. Separated from `users` to keep authentication and personal data decoupled.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| user_id | BIGINT | PK, FK → users (CASCADE) | |
| first_name | VARCHAR(128) | NOT NULL | |
| last_name | VARCHAR(128) | NOT NULL | |
| national_id | VARCHAR(20) | UNIQUE, NULLABLE | National ID / code melli |
| birth_date | DATE | NULLABLE | |
| marital_status | ENUM | NOT NULL, DEFAULT 'SINGLE' | SINGLE or MARRIED |
| marriage_date | DATE | NULLABLE | Required if marital_status = MARRIED |
| grade | VARCHAR(64) | NULLABLE | Employment level (L1, L2, ...) — used by future loan system |
| number_of_children | SMALLINT | DEFAULT 0 | Denormalized count for quick access |

### `user_children`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| user_id | BIGINT | FK → users (CASCADE), NOT NULL | |
| first_name | VARCHAR(128) | NULLABLE | |
| birth_date | DATE | NOT NULL | Used to determine newborn-plan eligibility |
| created_at | DATETIME | NOT NULL | |

### `roles`

Named role definitions. Seeded with SUPER_ADMIN, ORG_ADMIN, EMPLOYEE.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| key | VARCHAR(64) | UNIQUE, NOT NULL | Machine-readable identifier |
| name | VARCHAR(128) | NOT NULL | Human-readable label |
| scope | ENUM | NOT NULL | SYSTEM (global) or ORGANIZATION (org-scoped) |
| description | TEXT | NULLABLE | |

### `permissions`

Granular permission keys using dot-notation (e.g. `reservation.approve`).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| key | VARCHAR(128) | UNIQUE, NOT NULL | e.g. "user.edit", "reservation.approve" |
| description | TEXT | NULLABLE | |

### `role_permissions`

Many-to-many join between roles and permissions.

| Column | Type | Constraints |
|--------|------|-------------|
| role_id | BIGINT | PK, FK → roles (CASCADE) |
| permission_id | BIGINT | PK, FK → permissions (CASCADE) |

### `user_roles`

Assigns roles to users. The **max 2 roles per user** rule is enforced at the application layer.

| Column | Type | Constraints |
|--------|------|-------------|
| user_id | BIGINT | PK, FK → users (CASCADE) |
| role_id | BIGINT | PK, FK → roles (CASCADE) |
| assigned_at | DATETIME | NOT NULL, AUTO-SET |

### `otp_tokens`

Short-lived one-time-password codes for SMS-based authentication.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| user_id | BIGINT | FK → users (CASCADE), NOT NULL | |
| code | VARCHAR(10) | NOT NULL | The OTP code |
| expires_at | DATETIME | NOT NULL | Typically created_at + 2-5 min |
| is_used | BOOLEAN | DEFAULT FALSE | Marked TRUE after successful verification |
| created_at | DATETIME | NOT NULL | |

---

## Domain 2 — Accommodation

### `places`

Accommodation locations (hotels, guest houses, etc.) in various cities.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| city | VARCHAR(128) | NOT NULL | |
| name | VARCHAR(255) | NOT NULL | |
| is_active | BOOLEAN | DEFAULT TRUE | |
| created_at | DATETIME | NOT NULL | |

### `room_types`

Enum-like reference table. Seeded with ONE_BED and TWO_BED.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| key | VARCHAR(32) | UNIQUE, NOT NULL | ONE_BED, TWO_BED |
| label | VARCHAR(64) | NOT NULL | Display name |
| max_capacity | SMALLINT | NOT NULL | ONE_BED=5, TWO_BED=8 |

### `place_rooms`

Room stock inventory per place per room type.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| place_id | BIGINT | FK → places (CASCADE), NOT NULL | |
| room_type_id | BIGINT | FK → room_types (RESTRICT), NOT NULL | |
| total_rooms | INT | DEFAULT 0 | |

Unique constraint: `(place_id, room_type_id)`

### `org_place_access`

Controls which organizations are permitted to book which places. Managed by the main admin.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| org_id | BIGINT | FK → organizations (CASCADE), NOT NULL | |
| place_id | BIGINT | FK → places (CASCADE), NOT NULL | |
| is_allowed | BOOLEAN | DEFAULT TRUE | |

Unique constraint: `(org_id, place_id)`

### `place_availability`

Per-date room blocking. Main admin can block specific room types on specific dates or block an entire place.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| place_id | BIGINT | FK → places (CASCADE), NOT NULL | |
| room_type_id | BIGINT | FK → room_types (RESTRICT), NULLABLE | NULL = entire place blocked |
| date | DATE | NOT NULL | |
| blocked_count | INT | DEFAULT 0 | Number of rooms blocked |
| blocked_by_user_id | BIGINT | FK → users (SET NULL), NULLABLE | Admin who created the block |

Unique constraint: `(place_id, room_type_id, date)`

### `pricing_rules`

Price matrix with temporal validity. Supports different prices for employee families vs. guests.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| place_id | BIGINT | FK → places (CASCADE), NOT NULL | |
| room_type_id | BIGINT | FK → room_types (RESTRICT), NOT NULL | |
| person_group | ENUM | NOT NULL | EMPLOYEE_FAMILY or GUEST |
| price_per_night | DECIMAL(15,0) | NOT NULL | Price in Toman |
| effective_from | DATE | NOT NULL | Start of validity period |
| effective_to | DATE | NULLABLE | NULL = open-ended |

Unique constraint: `(place_id, room_type_id, person_group, effective_from)`

### `special_plans`

Time-limited eligibility plans assigned to users by the admin when they report a life event (marriage or new child).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| user_id | BIGINT | FK → users (CASCADE), NOT NULL | |
| plan_type | ENUM | NOT NULL | NEW_MARRIAGE or NEW_CHILD |
| eligible_from | DATE | NOT NULL | |
| eligible_until | DATE | NOT NULL | Fixed window set by admin |
| is_used | BOOLEAN | DEFAULT FALSE | |
| created_at | DATETIME | NOT NULL | |

### `discount_usage`

Tracks the number of approved reservations per user per Shamsi year for tiered discounts.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| user_id | BIGINT | FK → users (CASCADE), NOT NULL | |
| year | SMALLINT | NOT NULL | Shamsi year (converted at app layer) |
| usage_count | SMALLINT | DEFAULT 0 | 1st → 50%, 2nd → 30%, 3rd+ → 0% |

Unique constraint: `(user_id, year)`

### `reservations`

Booking requests created by employees and reviewed by the main admin.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| user_id | BIGINT | FK → users (RESTRICT), NOT NULL | The requesting employee |
| org_id | BIGINT | FK → organizations (RESTRICT), NOT NULL | Denormalized from user for query speed |
| place_id | BIGINT | FK → places (RESTRICT), NOT NULL | |
| room_type_id | BIGINT | FK → room_types (RESTRICT), NOT NULL | |
| check_in_date | DATE | NOT NULL | |
| check_out_date | DATE | NOT NULL | |
| nights | SMALLINT | NOT NULL | |
| status | ENUM | NOT NULL, DEFAULT 'PENDING' | PENDING, APPROVED, REJECTED, EXPIRED, CANCELLED |
| admin_deadline_at | DATETIME | NOT NULL | created_at + 72h |
| total_price | DECIMAL(15,0) | DEFAULT 0 | Pre-discount total |
| discount_percent | SMALLINT | DEFAULT 0 | 0, 30, or 50 |
| final_price | DECIMAL(15,0) | DEFAULT 0 | After discount + extra charges |
| special_plan_id | BIGINT | FK → special_plans (SET NULL), NULLABLE | If booked under a special plan |
| reviewed_by_user_id | BIGINT | FK → users (SET NULL), NULLABLE | Admin who reviewed |
| reviewed_at | DATETIME | NULLABLE | |
| created_at | DATETIME | NOT NULL | |
| updated_at | DATETIME | NOT NULL | |

### `reservation_guests`

Individual people included in a reservation.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGINT | PK, AUTO_INCREMENT | |
| reservation_id | BIGINT | FK → reservations (CASCADE), NOT NULL | |
| person_type | ENUM | NOT NULL | EMPLOYEE, SPOUSE, CHILD, GUEST |
| name | VARCHAR(255) | NULLABLE | Nullable for known family members |
| is_extra | BOOLEAN | DEFAULT FALSE | TRUE for non-family guests (max 2) |
| extra_charge | DECIMAL(15,0) | DEFAULT 0 | Per-person extra charge |

---

## Domain 3 — Loans (Future)

The loans module is planned for V2. The current schema already accommodates it:

- `user_profiles.grade` stores the employment level (L1/L2) used for loan caps
- `organizations` serves as the anchor for `manager_budgets`
- No structural changes to existing tables will be needed

Planned tables (from reference ERD):

- `loan_banks` — Bank definitions (SEPAH, RESALAT, ...)
- `loan_caps` — Per-bank, per-level maximum amounts
- `manager_budgets` — Per-org-manager, per-bank budget tracking
- `loan_requests` — Employee loan applications
- `loan_approvals` — Approval/rejection audit trail
- `loan_letters` — Issued bank letters with 30-day expiry
- `loan_outcomes` — Final received/not-received status

---

## Business Rules Reference

### User Management

| # | Rule | Enforcement |
|---|------|-------------|
| U1 | Max 2 roles per user | Application layer (check on `user_roles` INSERT) |
| U2 | marriage_date required when marital_status = MARRIED | Application layer validation |
| U3 | User data updates done by main admin only | Permission check: `user.edit` on SUPER_ADMIN role |
| U4 | Users can authenticate via password, OTP, or both | `users.auth_method` field + `otp_tokens` table |

### Accommodation & Reservations

| # | Rule | Enforcement |
|---|------|-------------|
| A1 | Max 8 persons per reservation (including employee) | Application validation on `reservation_guests` count |
| A2 | Max 2 extra (non-family) guests | Application validation: count of `is_extra = TRUE` <= 2 |
| A3 | >= 5 persons requires TWO_BED room | Application logic checks `room_types.max_capacity` |
| A4 | < 5 persons shows single-bed rooms only | Application UI/API filter |
| A5 | Admin has 72 hours to approve/reject | `admin_deadline_at` = `created_at` + 72h; scheduled job expires |
| A6 | Conflict resolution: fewer past reservations wins | `ORDER BY usage_count ASC, created_at ASC` in resolution query |
| A7 | Discount tiers: 1st=50%, 2nd=30%, 3rd+=0% | `discount_usage` table; app calculates % before pricing |
| A8 | Special plans restrict available rooms | `special_plans` eligibility window; `reservations.special_plan_id` links |
| A9 | VIP rooms assigned only by main admin | Permission check: `reservation.assign_vip` |
| A10 | Some places not available for certain orgs | `org_place_access.is_allowed` filtering |
| A11 | Main admin sets available dates for places/rooms | `place_availability` table |
| A12 | Extra persons (beyond family) pay additional price | `reservation_guests.extra_charge` per guest |
| A13 | Newborn/newlywed plans have fixed eligibility window | `special_plans.eligible_from/until`; admin sets when creating |
| A14 | Booking window: next 20 days, max 3 nights | Application validation on check_in/check_out dates |

---

## Index Strategy

### Primary Indexes (automatic)

All primary keys are automatically indexed by InnoDB.

### Foreign Key Indexes

| Table | Column(s) | Index Name |
|-------|-----------|------------|
| users | org_id | ix_users_org_id |
| user_children | user_id | ix_user_children_user_id |
| otp_tokens | user_id | ix_otp_tokens_user_id |
| special_plans | user_id | ix_special_plans_user_id |
| reservations | user_id | ix_reservations_user_id |
| reservations | org_id | ix_reservations_org_id |
| reservations | place_id | ix_reservations_place_id |
| reservation_guests | reservation_id | ix_reservation_guests_reservation_id |

### Unique Constraints (also serve as indexes)

| Table | Column(s) | Constraint Name |
|-------|-----------|-----------------|
| place_rooms | (place_id, room_type_id) | uq_place_room |
| org_place_access | (org_id, place_id) | uq_org_place |
| place_availability | (place_id, room_type_id, date) | uq_place_avail_date |
| pricing_rules | (place_id, room_type_id, person_group, effective_from) | uq_pricing_rule |
| discount_usage | (user_id, year) | uq_discount_user_year |

### Composite Indexes

| Table | Column(s) | Index Name | Purpose |
|-------|-----------|------------|---------|
| reservations | (place_id, check_in_date, check_out_date) | ix_reservations_place_dates | Availability overlap queries |
| reservations | status | ix_reservations_status | Filter by pending/expired |

---

## Seed Data

Migration 003 seeds the following reference data:

### Roles

| ID | Key | Name | Scope |
|----|-----|------|-------|
| 1 | SUPER_ADMIN | Super Administrator | SYSTEM |
| 2 | ORG_ADMIN | Organization Administrator | ORGANIZATION |
| 3 | EMPLOYEE | Employee | ORGANIZATION |

### Permissions

| ID | Key | Description |
|----|-----|-------------|
| 1 | user.view | View user list and details |
| 2 | user.create | Create new users |
| 3 | user.edit | Edit user information |
| 4 | user.deactivate | Deactivate/reactivate users |
| 5 | user.assign_role | Assign or remove roles from users |
| 6 | place.manage | Create/edit/deactivate accommodation places |
| 7 | place.set_availability | Block or unblock dates for places |
| 8 | pricing.manage | Create and modify pricing rules |
| 9 | reservation.create | Create a reservation request |
| 10 | reservation.view_own | View own reservations |
| 11 | reservation.view_all | View all reservations (admin) |
| 12 | reservation.approve | Approve or reject reservation requests |
| 13 | reservation.assign_vip | Assign VIP rooms to users |
| 14 | org.manage | Manage organizations |
| 15 | org.set_place_access | Configure which orgs can access which places |
| 16 | special_plan.manage | Create/manage special plans for users |

### Role → Permission Mapping

| Role | Permissions |
|------|------------|
| SUPER_ADMIN | All 16 permissions |
| ORG_ADMIN | user.view, user.create, user.edit, reservation.create, reservation.view_own, reservation.view_all |
| EMPLOYEE | reservation.create, reservation.view_own |

### Room Types

| ID | Key | Label | Max Capacity |
|----|-----|-------|-------------|
| 1 | ONE_BED | Single Bed Room | 5 |
| 2 | TWO_BED | Double Bed Room | 8 |

---

## Running Migrations

### Prerequisites

```bash
pip install alembic sqlalchemy pymysql
```

### Configuration

Set the database URL in one of two ways:

1. **Environment variable** (recommended):
   ```bash
   export DATABASE_URL="mysql+pymysql://user:password@localhost:3306/staffhub?charset=utf8mb4"
   ```

2. **Edit `alembic.ini`**: Update the `sqlalchemy.url` line directly.

### Commands

```bash
cd db/

# Apply all migrations
alembic upgrade head

# Apply up to a specific revision
alembic upgrade 002

# Rollback one step
alembic downgrade -1

# Rollback to the beginning
alembic downgrade base

# Check current revision
alembic current

# View migration history
alembic history --verbose
```

---

## Development Roadmap

| Phase | Module | Tables Added | Migration |
|-------|--------|-------------|-----------|
| V1.0 (current) | Identity & Access | organizations, users, user_profiles, user_children, roles, permissions, role_permissions, user_roles, otp_tokens | 001, 003 |
| V1.0 (current) | Accommodation | places, room_types, place_rooms, org_place_access, place_availability, pricing_rules, special_plans, discount_usage, reservations, reservation_guests | 002, 003 |
| V2.0 (planned) | Loans | loan_banks, loan_caps, manager_budgets, loan_requests, loan_approvals, loan_letters, loan_outcomes | 004+ |
| V2.x (planned) | Audit Log | audit_logs (polymorphic event log) | TBD |
| V3.0 (planned) | Notifications | notification_templates, user_notifications | TBD |

### Design Decisions for Future Compatibility

1. **`user_profiles.grade`** — Already stores L1/L2 levels needed by the loan cap system
2. **`organizations.id`** — Serves as FK anchor for `manager_budgets`
3. **Separate `users` and `user_profiles`** — Auth data is decoupled from personal data, making it straightforward to add loan-related fields to profiles without touching auth
4. **Permission-based RBAC** — New modules only need new permission keys seeded; no schema changes to the access control tables
5. **All monetary values use `DECIMAL(15,0)`** — Toman (no decimals), large enough for any realistic amount
6. **Temporal pricing** — `effective_from` / `effective_to` on pricing rules allows historical price preservation without mutation
