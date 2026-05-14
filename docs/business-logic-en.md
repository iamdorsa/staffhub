# StaffHub — Complete Business Logic Documentation

> This document covers all business rules, operational scenarios, discount calculation edge cases, and frontend implementation status.

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Roles & Permissions](#2-roles--permissions)
3. [Accommodation Management](#3-accommodation-management)
4. [Room Management](#4-room-management)
5. [Availability Calendar (Date Blocking)](#5-availability-calendar)
6. [Organization Place Access](#6-organization-place-access)
7. [Pricing](#7-pricing)
8. [Special Plans](#8-special-plans)
9. [Reservation Creation](#9-reservation-creation)
10. [Reservation Review & Lifecycle](#10-reservation-review--lifecycle)
11. [Automatic Reservation Expiry](#11-automatic-reservation-expiry)
12. [Rating System](#12-rating-system)
13. [Analytics Dashboard](#13-analytics-dashboard)
14. [Discount Calculation — Scenarios & Edge Cases](#14-discount-calculation--scenarios--edge-cases)
15. [Frontend Coverage](#15-frontend-coverage)

---

## 1. Authentication

### 1.1 Auth Methods

Each user has one of three auth methods:

| Method | Description |
|--------|-------------|
| `PASSWORD` | Username + password login |
| `OTP` | One-time code sent to mobile |
| `BOTH` | User can choose either method |

### 1.2 Password Login Flow

1. User submits username and password
2. System checks:
   - User exists? → If not: "Invalid username or password"
   - User active (`is_active`)? → If not: "Account is deactivated"
   - Auth method includes `PASSWORD` or `BOTH`? → If not: "Invalid auth method"
   - Password correct? → If not: "Invalid username or password"
3. On success: access token (30 min) and refresh token (7 days) are issued

### 1.3 OTP Login Flow

**Step 1 — Send code:**
1. User submits username
2. System checks user exists, is active, and auth method includes `OTP` or `BOTH`
3. A 6-digit code is generated and stored in-memory
4. Code is valid for **300 seconds** (5 minutes)

**Step 2 — Verify code:**
1. User submits the received code
2. System checks code exists, is not expired, and matches
3. On success: tokens are issued

### 1.4 Token Refresh

- Access token expires every 30 minutes
- Send `refresh_token` to `/refresh` to get a new access token
- Refresh token is valid for 7 days
- Frontend uses an Axios interceptor for automatic token renewal

### 1.5 JWT Structure

```json
{
  "sub": "user_id",
  "org_id": "organization_id",
  "roles": ["SUPER_ADMIN", "ORG_ADMIN", "EMPLOYEE"],
  "type": "access | refresh",
  "exp": "expiration_timestamp"
}
```

---

## 2. Roles & Permissions

### 2.1 Roles

| Role | Description |
|------|-------------|
| `SUPER_ADMIN` | System administrator — full access to all resources |
| `ORG_ADMIN` | Organization admin — manages users and reservations within their org |
| `EMPLOYEE` | Employee — can create reservations and view their own |

### 2.2 Permissions

| Permission | Description | Allowed Roles |
|------------|-------------|---------------|
| `place.manage` | Create/edit accommodations | SUPER_ADMIN |
| `place.set_availability` | Block dates | SUPER_ADMIN |
| `org.set_place_access` | Set organization access | SUPER_ADMIN |
| `pricing.manage` | Create pricing rules | SUPER_ADMIN |
| `special_plan.manage` | Manage special plans | SUPER_ADMIN |
| `reservation.create` | Create reservations | EMPLOYEE, ORG_ADMIN |
| `reservation.view_own` | View own reservations | EMPLOYEE, ORG_ADMIN |
| `reservation.view_all` | View all reservations | ORG_ADMIN, SUPER_ADMIN |
| `reservation.approve` | Approve/reject reservations | ORG_ADMIN, SUPER_ADMIN |

### 2.3 Key Access Rules

- **Super Admin** bypasses all access checks
- **Regular users** only see accommodations their organization has access to
- **VIP rooms** are only visible to and bookable by Super Admin
- **Reservations** are only visible to the creator or members of the same organization

---

## 3. Accommodation Management

### 3.1 Create Accommodation

- **Permission:** `place.manage`
- **Input:** city + name
- **Output:** accommodation with `is_active = true`

### 3.2 Edit Accommodation

- **Permission:** `place.manage`
- Editable fields: city, name, active/inactive
- Inactive accommodations are hidden from regular user listings

### 3.3 Viewing Accommodations

**Super Admin view:**
- All active accommodations with all rooms (including VIP)

**Regular user view:**
- Only accommodations their organization has access to
- VIP rooms are filtered out
- City filter available

---

## 4. Room Management

### 4.1 Room Types

| Key | Name | Max Capacity |
|-----|------|--------------|
| `ONE_BED` | One-bedroom | Per configuration |
| `TWO_BED` | Two-bedroom | Per configuration |

### 4.2 Room Configuration

- **Permission:** `place.manage`
- Each accommodation can have a mix of room types
- Each room type can have a standard and VIP variant
- `total_rooms`: total count of that type
- Upsert operation: if (place_id + room_type_id + is_vip) exists, it is updated

### 4.3 Automatic Room Type Selection

| Guest Count | Room Type |
|-------------|-----------|
| 1–4 persons | `ONE_BED` |
| 5+ persons | `TWO_BED` |

> Room type is selected **automatically** — users do not choose it directly.

---

## 5. Availability Calendar

### 5.1 Date Blocking

- **Permission:** `place.set_availability`
- Admin can block a number of rooms for specific dates
- `blocked_count`: number of rooms unavailable on that date
- If `room_type_id` is null, the block applies to the entire accommodation

### 5.2 Available Capacity Calculation

For each night of stay:

```
available = total_rooms - blocked_count - active_reservations
```

- Active reservations = reservations with status `PENDING` or `APPROVED` that overlap that night
- If available ≤ 0 → error: "No available room on date X"

---

## 6. Organization Place Access

### 6.1 Configuration

- **Permission:** `org.set_place_access`
- Each organization can be granted access to specific accommodations
- Upsert on (org_id + place_id)

### 6.2 Effect on Users

- Users only see accommodations where `is_allowed = true` for their org
- If org lacks access and user tries to book → error: "Your organization does not have access"
- Super Admin is exempt from this restriction

---

## 7. Pricing

### 7.1 Pricing Rule Structure

| Field | Description |
|-------|-------------|
| `place_id` | Accommodation |
| `room_type_id` | Room type (ONE_BED / TWO_BED) |
| `person_group` | Group: `EMPLOYEE_FAMILY` or `GUEST` |
| `price_per_night` | Price per night (Toman) |
| `effective_from` | Start date |
| `effective_to` | End date (optional — null = indefinite) |

### 7.2 Price Lookup

1. Find a pricing rule where `effective_from ≤ check_in_date` and `effective_to ≥ check_in_date` (or no end date)
2. If multiple rules match, the **most recent** (by `effective_from` descending) is used
3. If no rule found, price defaults to **zero**

### 7.3 Reservation Price Calculation

```
family_total = family_price × family_count × nights
guest_total  = guest_price  × guest_count  × nights
total_price  = family_total + guest_total
```

**Family members:** employee + spouse + children
**Guests:** persons with type `GUEST`

---

## 8. Special Plans

### 8.1 Plan Types

| Type | Description |
|------|-------------|
| `NEW_MARRIAGE` | New marriage plan |
| `NEW_CHILD` | New child plan |

### 8.2 Structure

- Each plan belongs to an **organization**
- Each org can have **one plan per type**
- Plans have a validity window (`eligible_from` to `eligible_until`) and active/inactive status

### 8.3 Automatic Eligibility

When a user's marital status or child count changes:
1. System checks if the user's org has an active special plan of that type
2. Today's date must be within the plan's validity window
3. If yes: a `UserPlanEligibility` record is created with `is_used = false`

### 8.4 Usage in Reservations

When `use_special_plan = true`:
- System finds the user's first unused eligibility record
- Plan must be active and today must be within its window
- **Tiered discount is NOT applied** (discount_percent = 0)
- After reservation is created, `is_used = true`

---

## 9. Reservation Creation

### 9.1 Constraints

| Parameter | Value | Description |
|-----------|-------|-------------|
| `MAX_STAY_NIGHTS` | **3** | Maximum stay: 3 nights |
| `BOOKING_WINDOW_DAYS` | **20** | Bookings only up to 20 days ahead |
| `MAX_PERSONS_PER_RESERVATION` | **8** | Max 8 persons per reservation |
| `MAX_EXTRA_GUESTS` | **2** | Max 2 extra guests |

### 9.2 Full Reservation Flow

#### Step 1 — Basic Validation

1. **Check-in date:** must not be in the past
2. **Booking window:** check-in must be within 20 days from today
3. **Stay duration:** minimum 1 night, maximum 3 nights
4. **Person count:** employee + companions ≤ 8
5. **Extra guests:** maximum 2 guests

#### Step 2 — Organization Access Check

- If user is NOT Super Admin: org must have `is_allowed = true` for the accommodation
- Otherwise: error "Your organization does not have access to this accommodation"

#### Step 3 — Guest Validation

**Spouse (`SPOUSE`):**
- User must have marital status `MARRIED`
- Maximum 1 spouse allowed

**Child (`CHILD`):**
- Number of declared children must not exceed children registered in profile
- Example: if 2 children are registered, cannot add 3

**Guest (`GUEST`):**
- Maximum 2 guests
- Charged at a separate rate (guest pricing)

#### Step 4 — VIP Check

- VIP rooms can **only** be booked by Super Admin (`SUPER_ADMIN`)
- Other users: error "Only Super Admin can book VIP rooms"

#### Step 5 — Room Type Selection

- Total person count is calculated (employee + companions)
- ≥ 5 persons → `TWO_BED`
- < 5 persons → `ONE_BED`
- If no room of that type (matching VIP status) exists → error

#### Step 6 — Capacity Check (Per Night)

For **each night** of stay (check-in to one day before check-out):

```
blocked  = SUM(blocked_count) for that date and room type
reserved = COUNT of PENDING or APPROVED reservations overlapping that night
available = total_rooms - blocked - reserved
```

If available ≤ 0 on **any night** → error: "No available room on date X"

#### Step 7 — Price Calculation

1. Family price (`EMPLOYEE_FAMILY`) and guest price (`GUEST`) are looked up from pricing rules
2. Total price:

```
total_price = (family_price × family_count × nights) + (guest_price × guest_count × nights)
```

#### Step 8 — Discount Calculation (Preview)

**If special plan is used:**
- discount = 0% (special plan replaces tiered discount)

**If no special plan — tiered discount based on yearly reservation count:**

| Reservation # (Shamsi year) | Discount |
|------------------------------|----------|
| 1st reservation | **50%** |
| 2nd reservation | **30%** |
| 3rd and beyond | **0%** |

```
final_price = total_price × (100 - discount_percent) / 100
```

> Note: Shamsi year is approximated as `gregorian_year - 621`. Usage count resets per Shamsi year.

> **Important:** The discount stored at creation time is a **preview**. The actual discount is **recalculated at approval time** based on the user's current usage count. See [Section 10.1](#101-approve-reservation) and [Section 14](#14-discount-calculation--scenarios--edge-cases) for details.

#### Step 9 — Reservation Record

- Status: `PENDING`
- Admin deadline: `admin_deadline_at = now + 72 hours`
- Employee is automatically added as the first guest
- If special plan used: eligibility record set to `is_used = true`

---

## 10. Reservation Review & Lifecycle

### 10.1 Approve Reservation

- **Permission:** `reservation.approve`
- Only `PENDING` reservations can be approved
- On approval:
  - Status → `APPROVED`
  - **Discount recalculation:** The discount percentage is recalculated based on the user's **current** usage count at the time of approval (not the value from reservation creation). This prevents the scenario where two concurrent PENDING reservations both receive 50% discount.
  - Usage counter is incremented by **+1**
  - Reviewer ID and timestamp are recorded

> **Example:** A user creates 2 reservations simultaneously (both usage_count=0 → both show 50%). When reservation 1 is approved: recalculation (count=0 → 50%, correct), usage +1. When reservation 2 is approved: recalculation (count=1 → 30%), usage +1. Result: reservation 1 gets 50%, reservation 2 gets 30% — correct.
>
> **Exception:** Reservations using a special plan are not recalculated (discount is always 0%).

### 10.2 Reject Reservation

- **Permission:** `reservation.approve`
- Only `PENDING` reservations
- Status → `REJECTED`
- Reviewer ID and timestamp are recorded
- Usage counter does **not** change

### 10.3 Cancel Reservation

- **Only the reservation owner** can cancel their own reservation
- Only `PENDING` reservations can be cancelled
- Status → `CANCELLED`
- Usage counter does **not** change (it was never incremented before approval)
- Cancel button is available both on the reservation detail page and in the "My Reservations" list

### 10.4 Reservation Statuses

| Status | Description |
|--------|-------------|
| `PENDING` | Awaiting admin review |
| `APPROVED` | Approved |
| `REJECTED` | Rejected |
| `CANCELLED` | Cancelled by user |
| `EXPIRED` | Auto-expired after 72 hours |

---

## 11. Automatic Reservation Expiry

### 11.1 Process

A background job processes `PENDING` reservations whose `admin_deadline_at` has passed:

1. Expired reservations are grouped by **(place_id + room_type_id + check_in_date + check_out_date)**
2. Within each group, reservations are ranked by **priority**:
   - **Primary:** lowest yearly usage count (usage_count)
   - **Tiebreaker:** earliest creation time (created_at)
3. **Winner** (first in ranking): status → `APPROVED` + discount recalculated based on current usage + usage counter +1
4. **Losers**: status → `EXPIRED`

### 11.2 Purpose

This mechanism ensures that if an admin does not act within 72 hours, the system resolves fairly. Users who have booked less this year get higher priority.

### 11.3 Frontend

The reservation detail page shows an explanation banner when status is `EXPIRED`, describing the 72-hour auto-expiry mechanism and how the system selects the winner.

---

## 12. Rating System

### 12.1 Submitting a Rating

- Each user can give **one rating** (1–5) per accommodation
- If a rating already exists: it is **updated** (upsert)
- No special permission required (all authenticated users)

### 12.2 Rating Summary

- Average score (rounded to 1 decimal)
- Total number of raters
- Displayed on accommodation cards and detail page

---

## 13. Analytics Dashboard

### 13.1 Overview Stats (Admins Only)

- Pending reservations count
- Total users count
- Total accommodations count
- Total organizations count

### 13.2 Accommodation Analytics

- Ranking by reservation count (PENDING + APPROVED)
- Average rating per accommodation
- Total voter count per accommodation

---

## 14. Discount Calculation — Scenarios & Edge Cases

This section documents every discount-related scenario, how the system handles it, and why.

### 14.1 Core Discount Rules

| Usage Count (Shamsi Year) | Discount | Explanation |
|----------------------------|----------|-------------|
| 0 (first reservation) | 50% | First reservation of the year |
| 1 (second reservation) | 30% | Second reservation of the year |
| 2+ (third onwards) | 0% | No discount |

- Usage count is incremented **only on APPROVE**, not on creation
- Discount is **recalculated at approval time**, not locked at creation time
- Special plan reservations always have 0% discount and bypass tiered discounts

### 14.2 Scenario: Normal Single Reservation

1. User has 0 approved reservations this year
2. Creates a reservation → preview shows 50% discount
3. Admin approves → recalculates (count=0 → 50%), increments usage to 1
4. Final price reflects 50% discount ✓

### 14.3 Scenario: Two Concurrent Pending Reservations

1. User has 0 approved reservations this year
2. Creates reservation A → preview shows 50%
3. Creates reservation B → preview also shows 50% (usage still 0)
4. Admin approves reservation A → recalculate (count=0 → 50%), usage becomes 1
5. Admin approves reservation B → recalculate (count=1 → **30%**), usage becomes 2
6. Result: A gets 50%, B gets 30% — correct tiered pricing ✓

### 14.4 Scenario: Cancel a Pending Reservation

1. User has 0 approved reservations, creates reservation A (preview 50%)
2. User cancels reservation A → status becomes `CANCELLED`
3. Usage counter is unchanged (was never incremented) → still 0
4. User creates reservation B → preview shows 50% (correct, count still 0)
5. Admin approves B → recalculate (count=0 → 50%), usage becomes 1 ✓

### 14.5 Scenario: Rejected Reservation

1. User creates reservation A (preview 50%)
2. Admin rejects A → status `REJECTED`, usage NOT incremented → still 0
3. User creates reservation B → preview shows 50%
4. Admin approves B → recalculate (count=0 → 50%), usage becomes 1 ✓

### 14.6 Scenario: Special Plan Reservation

1. User has an unused eligibility (e.g., NEW_MARRIAGE)
2. Creates reservation with `use_special_plan = true` → discount = 0% (no tiered discount)
3. Eligibility marked `is_used = true`
4. On approval: no recalculation (special plan reservations are excluded), usage +1
5. Next reservation (without special plan, count=1) → 30% discount ✓

### 14.7 Scenario: Special Plan + Normal Reservation Concurrent

1. User (count=0) creates reservation A with special plan → discount = 0%
2. Creates reservation B without special plan → preview shows 50%
3. Admin approves A → no recalculation (special plan), usage becomes 1
4. Admin approves B → recalculate (count=1 → **30%**), usage becomes 2
5. Result: A at full price (special plan), B at 30% ✓

### 14.8 Scenario: Auto-Expiry with Discount

1. Two users each create a reservation for the same room/dates
2. Admin does not act within 72 hours
3. Expiry job runs:
   - Groups by (place + room_type + check_in + check_out)
   - Ranks by usage count (lowest first), then created_at (earliest first)
   - Winner: APPROVED + discount recalculated based on current usage + usage +1
   - Loser: EXPIRED
4. Winner's discount is accurate at time of approval ✓

### 14.9 Scenario: Year Boundary

1. User has 2 approved reservations in Shamsi year 1404
2. Shamsi year changes to 1405
3. Usage count resets to 0 for the new year
4. First reservation of 1405 gets 50% discount ✓

### 14.10 Why Discount Is Not Locked at Creation

If discount were locked at creation time:
- Two concurrent PENDING reservations would both get 50% (total 100% discount value)
- After both are approved, the system would have given 50% + 50% instead of 50% + 30%
- The recalculation-at-approval approach ensures the correct tiered discount regardless of how many reservations are pending simultaneously

---

## 15. Frontend Coverage

### 15.1 Implemented Features ✅

| Backend Logic | Frontend Status | Details |
|---------------|----------------|---------|
| Password login | ✅ | Login page with password tab |
| OTP login | ✅ | Login page with OTP tab + resend |
| Create reservation | ✅ | 3-step form (place → dates → guests) |
| Max 3 nights | ✅ | ShamsiDatePicker constrains check-out |
| Price estimation | ✅ | Price calculated from pricing rules with discount preview |
| Add companions | ✅ | Guest form with type selection (spouse/child/guest) |
| My reservations | ✅ | Paginated table with status + cancel action |
| All reservations | ✅ | Admin table with status filter + approve/reject actions |
| Approve/reject | ✅ | Buttons on detail page and all-reservations list (admin only) |
| Cancel reservation | ✅ | Cancel on detail page and my-reservations list (owner + PENDING) |
| Discount recalculation | ✅ | Discount recalculated on approval based on current usage |
| Yearly usage display | ✅ | Reservation creation page shows "reservation #N of year Y" |
| Discount tier preview | ✅ | Estimated price includes discount + `GET /reservations/discount-info` |
| Expired explanation | ✅ | Detail page shows explanation banner for EXPIRED status |
| Accommodation management | ✅ | List + create + edit |
| Room management | ✅ | Room config in accommodation detail |
| Pricing | ✅ | Create form + pricing list |
| Ratings | ✅ | Interactive stars on accommodation detail |
| Analytics dashboard | ✅ | Stat cards + ranking table |
| VIP badge | ✅ | VIP indicator on accommodation cards |
| VIP room filter | ✅ | Backend filters VIP rooms for non-admin |
| Special plans | ✅ | Management page + usage option in reservation |
| Organization access | ✅ | Access config in accommodation detail |
| Availability calendar | ✅ | Date blocking in accommodation detail |

### 15.2 Client-Side Validations (Aligned with Backend) ✅

| Validation | Status | Details |
|------------|--------|---------|
| 20-day booking window | ✅ | ShamsiDatePicker with `maxDate` |
| Max 3 nights | ✅ | Check-out limited to 3 days after check-in |
| Max 8 persons | ✅ | Add button disabled after 7 companions |
| Max 2 extra guests | ✅ | Guest option hidden after 2 |
| Marriage check for spouse | ✅ | Spouse option only for married users |
| Children count check | ✅ | Child option limited by registered count |
| VIP for Super Admin only | ✅ | VIP toggle only shown to Super Admin |
| 1 spouse limit | ✅ | Spouse option hidden after adding 1 |
| Route guard by role | ✅ | RequireAdmin protects admin routes |
| Permission check | ✅ | `hasPermission()` based on actual roles/permissions |
| Hidden menus | ✅ | Admin menus only for authorized roles |
| Active/inactive place | ✅ | Toggle in edit modal + warning banner |
| Refresh token | ✅ | Axios interceptor auto-refreshes token |

---

## System Constants

| Constant | Value |
|----------|-------|
| Max stay nights | 3 |
| Booking window | 20 days |
| Max persons per reservation | 8 |
| Max extra guests | 2 |
| Admin review deadline | 72 hours |
| Access token lifetime | 30 minutes |
| Refresh token lifetime | 7 days |
| OTP validity | 300 seconds |
| OTP length | 6 digits |
| 1st reservation discount | 50% |
| 2nd reservation discount | 30% |
| 3rd+ reservation discount | 0% |
| Max rating | 5 |
| Min rating | 1 |

---

## API Endpoints Summary

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST | `/login` | Password login |
| POST | `/otp/send` | Send OTP code |
| POST | `/otp/verify` | Verify OTP code |
| POST | `/refresh` | Refresh access token |
| GET | `/me` | Get current user info |

### Accommodations
| Method | Path | Description |
|--------|------|-------------|
| GET | `/room-types` | List room types |
| GET | `/places` | List places (paginated, city filter) |
| GET | `/places/{id}` | Get place details |
| POST | `/places` | Create place |
| PATCH | `/places/{id}` | Update place |
| GET | `/places/{id}/rooms` | List rooms |
| PUT | `/places/{id}/rooms` | Set rooms (upsert) |
| GET | `/places/{id}/availability` | List availability |
| PUT | `/places/{id}/availability` | Set availability (block dates) |
| GET | `/places/{id}/org-access` | List org access |
| PUT | `/places/{id}/org-access` | Set org access |
| GET | `/places/{id}/pricing-rules` | List pricing rules |
| GET | `/places/{id}/rating` | Get place rating summary |

### Pricing
| Method | Path | Description |
|--------|------|-------------|
| POST | `/pricing-rules` | Create pricing rule |

### Special Plans
| Method | Path | Description |
|--------|------|-------------|
| POST | `/org-special-plans` | Create org special plan |
| PATCH | `/org-special-plans/{id}` | Update org special plan |
| GET | `/orgs/{id}/special-plans` | List org special plans |
| GET | `/users/{id}/plan-eligibility` | List user plan eligibility |

### Reservations
| Method | Path | Description |
|--------|------|-------------|
| POST | `/reservations` | Create reservation |
| GET | `/reservations/mine` | List my reservations |
| GET | `/reservations` | List all reservations (admin) |
| GET | `/reservations/discount-info` | Get current user discount info |
| GET | `/reservations/{id}` | Get reservation details |
| POST | `/reservations/{id}/review` | Approve or reject reservation |
| POST | `/reservations/{id}/cancel` | Cancel reservation |

### Ratings & Analytics
| Method | Path | Description |
|--------|------|-------------|
| POST | `/place-ratings` | Rate a place |
| GET | `/place-ratings/summary` | List all place rating summaries |
| GET | `/analytics/places` | Place analytics (admin) |
