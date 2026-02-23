# StaffHub

A multi-organization personnel welfare management system. Organizations register their employees, and employees can reserve accommodation rooms across various cities with tiered discounts, special plans, and admin approval workflows.

## Features

**V1 (current)**

- **Multi-organization user management** -- organizations, users, profiles, children records
- **Role-based access control (RBAC)** -- granular permission system with SUPER_ADMIN, ORG_ADMIN, and EMPLOYEE roles
- **Authentication** -- password-based login with JWT (access + refresh tokens). OTP/SMS login planned.
- **Accommodation reservations** -- places, rooms, pricing rules, booking with 72-hour admin review window
- **Discount tiers** -- 50% first reservation of the year, 30% second, 0% after
- **Special plans** -- new marriage and new child plans with time-limited eligibility
- **VIP room assignment** -- admin-only room allocation
- **Conflict resolution** -- automatic priority when multiple users reserve the same room

**Planned**

- OTP/SMS authentication
- Loan management system (V2)
- Notifications module
- Audit logging

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Framework | FastAPI |
| ORM | SQLAlchemy 2.x |
| Database | MariaDB / MySQL 8.x |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt |
| Background jobs | Celery + Redis (planned) |
| API docs | Swagger UI + ReDoc (auto-generated) |

## Project Structure

```
staffhub/
├── architecture/              # Architecture & implementation docs
│   ├── SYSTEM_ARCHITECTURE.md
│   └── IMPLEMENTATION_PLAN.md
├── db/                        # Database layer
│   ├── alembic.ini
│   ├── alembic/               # Migration engine
│   │   ├── env.py
│   │   └── versions/          # Versioned migration files
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── base.py            # Declarative base + mixins
│   │   ├── identity.py        # Organization, User, UserProfile, UserChild
│   │   ├── access.py          # Role, Permission, UserRole, OtpToken
│   │   └── accommodation.py   # Place, RoomType, Reservation, PricingRule, ...
│   └── DATABASE_DESIGN.md     # Full schema reference
├── src/                       # Application source code
│   ├── main.py                # FastAPI app factory
│   ├── config.py              # Pydantic settings (reads .env)
│   ├── core/                  # Shared infrastructure
│   │   ├── database.py        # Engine, session, get_db dependency
│   │   ├── security.py        # JWT + password hashing
│   │   ├── permissions.py     # RBAC: get_current_user, require_permission
│   │   ├── exceptions.py      # Error classes + handler
│   │   └── pagination.py      # Paginated response helper
│   ├── modules/               # Feature modules (modular monolith)
│   │   ├── auth/              # Login, token refresh
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── router.py
│   │   ├── users/             # Org & user CRUD, children, role assignment
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── router.py
│   │   └── accommodation/     # Places, rooms, pricing, reservations
│   │       ├── schemas.py
│   │       ├── service.py
│   │       └── router.py
│   └── adapters/              # External service adapters (SMS, etc.)
├── scripts/
│   ├── seed_admin.py          # Create initial admin user
│   └── expire_reservations.py # Background job: expire overdue reservations
├── docker-files/
│   └── docker-compose.yml     # MariaDB + phpMyAdmin
├── requirements.txt
├── .env.example
└── .gitignore
```

## Prerequisites

- Python 3.10+
- MariaDB or MySQL running on port 3306
- (Optional) Docker for running MariaDB via docker-compose

## Getting Started

### 1. Start the database

If you don't already have MariaDB running, use the provided docker-compose:

```bash
cd docker-files
docker-compose up -d
```

This starts:
- MariaDB on `localhost:3306` (user: `root`, password: `root`, database: `staffhub_db`)
- phpMyAdmin on `http://localhost:8080`

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy the example and edit if needed:

```bash
cp .env.example .env
```

Default `.env` values work with the docker-compose database:

```
DATABASE_URL=mysql+pymysql://root:root@127.0.0.1:3306/staffhub_db?charset=utf8mb4
SECRET_KEY=change-me-to-a-random-string
```

### 4. Run database migrations

```bash
cd db
DATABASE_URL="mysql+pymysql://root:root@127.0.0.1:3306/staffhub_db?charset=utf8mb4" \
  python -m alembic upgrade head
cd ..
```

This creates all 19 tables and seeds default roles, permissions, and room types.

### 5. Seed the admin user

```bash
python -m scripts.seed_admin
```

Creates:
- Organization: **HQ**
- User: `admin` / `admin` with **SUPER_ADMIN** role

### 6. Start the server

```bash
uvicorn src.main:app --reload --port 8000
```

### 7. Open the API docs

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health check**: [http://localhost:8000/health](http://localhost:8000/health)

## API Overview

All endpoints require a JWT Bearer token unless noted otherwise. Get a token via `/api/v1/auth/login`.

### Auth

| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| POST | `/api/v1/auth/login` | Public | Login with username + password |
| POST | `/api/v1/auth/refresh` | Public | Refresh access token |

### Users & Organizations

| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/v1/me` | Authenticated | Get current user profile |
| GET | `/api/v1/orgs` | `user.view` | List organizations (paginated) |
| POST | `/api/v1/orgs` | `org.manage` | Create organization |
| PATCH | `/api/v1/orgs/{org_id}` | `org.manage` | Update organization |
| GET | `/api/v1/users` | `user.view` | List users (paginated, filterable) |
| GET | `/api/v1/users/{user_id}` | `user.view` | Get user detail with profile, children, roles |
| POST | `/api/v1/users` | `user.create` | Create user with profile |
| PATCH | `/api/v1/users/{user_id}` | `user.edit` | Update user & profile |
| DELETE | `/api/v1/users/{user_id}` | `user.deactivate` | Soft-deactivate user |
| POST | `/api/v1/users/{user_id}/children` | `user.edit` | Add child record |
| PUT | `/api/v1/users/{user_id}/roles` | `user.assign_role` | Assign roles to user |

### Accommodation

| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/v1/places` | Authenticated | List places (org-scoped) |
| GET | `/api/v1/places/{place_id}` | Authenticated | Get place details with rooms |
| POST | `/api/v1/places` | `place.manage` | Create place |
| PATCH | `/api/v1/places/{place_id}` | `place.manage` | Update place |
| PUT | `/api/v1/places/{place_id}/rooms` | `place.manage` | Set room stock per type |
| PUT | `/api/v1/places/{place_id}/availability` | `place.set_availability` | Block/unblock dates |
| PUT | `/api/v1/places/{place_id}/org-access` | `org.set_place_access` | Set org access to place |
| POST | `/api/v1/pricing-rules` | `pricing.manage` | Create pricing rule |
| GET | `/api/v1/places/{place_id}/pricing-rules` | Authenticated | List pricing for a place |
| POST | `/api/v1/special-plans` | `special_plan.manage` | Create special plan for user |
| GET | `/api/v1/users/{user_id}/special-plans` | Authenticated | List user's special plans |
| POST | `/api/v1/reservations` | `reservation.create` | Create reservation request |
| GET | `/api/v1/reservations/mine` | `reservation.view_own` | List own reservations |
| GET | `/api/v1/reservations` | `reservation.view_all` | List all reservations (admin) |
| GET | `/api/v1/reservations/{id}` | Authenticated | Get reservation detail |
| POST | `/api/v1/reservations/{id}/review` | `reservation.approve` | Approve or reject |
| POST | `/api/v1/reservations/{id}/cancel` | Authenticated | Cancel own reservation |

### Quick test

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# Use the access_token from the response
curl http://localhost:8000/api/v1/me \
  -H "Authorization: Bearer <access_token>"
```

### Background Jobs

| Script | Description |
|--------|-------------|
| `python -m scripts.expire_reservations` | Expire PENDING reservations past 72-hour deadline. Auto-approves the winner based on priority rules. |

Run via cron (e.g., every hour) or a simple scheduler.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | -- | SQLAlchemy connection string |
| `SECRET_KEY` | Yes | -- | JWT signing key |
| `JWT_ACCESS_EXPIRE_MINUTES` | No | 30 | Access token lifetime |
| `JWT_REFRESH_EXPIRE_DAYS` | No | 7 | Refresh token lifetime |
| `OTP_EXPIRY_SECONDS` | No | 300 | OTP code validity |
| `SMS_PROVIDER` | No | console | SMS adapter (console, kavenegar) |
| `RESERVATION_ADMIN_DEADLINE_HOURS` | No | 72 | Hours before auto-expiry |
| `BOOKING_WINDOW_DAYS` | No | 20 | How far ahead users can book |
| `MAX_STAY_NIGHTS` | No | 3 | Max reservation length |
| `MAX_PERSONS_PER_RESERVATION` | No | 8 | Max people per booking |
| `MAX_EXTRA_GUESTS` | No | 2 | Max non-family guests |

## Database

- **19 tables** across 2 domains (Identity/Access + Accommodation)
- **3 migrations**: schema creation + seed data
- Full schema documentation in [`db/DATABASE_DESIGN.md`](db/DATABASE_DESIGN.md)

To manage migrations:

```bash
cd db

# Check current revision
DATABASE_URL="..." python -m alembic current

# Apply all pending migrations
DATABASE_URL="..." python -m alembic upgrade head

# Rollback one step
DATABASE_URL="..." python -m alembic downgrade -1
```

## Architecture

The system follows a **modular monolith** pattern:

- Single deployable, single process
- Modules (`auth`, `users`, `accommodation`) have clear boundaries
- Shared infrastructure lives in `src/core/`
- Modules communicate through service functions, not by importing each other's internals
- New features (loans, notifications) are added as new module folders with no changes to existing code

Full architecture analysis and decision log in [`architecture/SYSTEM_ARCHITECTURE.md`](architecture/SYSTEM_ARCHITECTURE.md).

Step-by-step implementation plan in [`architecture/IMPLEMENTATION_PLAN.md`](architecture/IMPLEMENTATION_PLAN.md).

## Roles & Permissions

| Role | Scope | Access |
|------|-------|--------|
| SUPER_ADMIN | System-wide | All 16 permissions |
| ORG_ADMIN | Own organization | View/create/edit users, create/view reservations |
| EMPLOYEE | Own organization | Create and view own reservations |

Permissions use dot-notation keys (e.g., `reservation.approve`, `user.edit`). Endpoints are protected using the `require_permission` dependency. See the full permission list in the [database docs](db/DATABASE_DESIGN.md#seed-data).

## License

Private / Internal use.
