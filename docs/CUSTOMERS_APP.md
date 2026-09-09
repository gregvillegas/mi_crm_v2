# Customers App — How It Works

This document explains the `customers` app, with a focus on the two areas that
generate the most questions: **managing duplicate customers** and **notifying
the AVP (and other approvers)** when a new customer needs review.

> Scope note: everything below reflects the code as it exists today. Where a
> feature is *designed but not yet built* (customer merge), it is called out
> explicitly so no one assumes it's live.

---

## 1. Quick overview

- **What it manages:** company records (`Customer`), their extra contacts,
  notes, full audit history, backups, delinquency records, and a
  **create-request approval workflow**.
- **Who sees what:** visibility is role-scoped (see §6). Executives see all
  customers; salespeople see only their own; supervisors/AVP/ASM/SM see their
  team's customers.
- **Key files:**
  | File | Responsibility |
  |------|----------------|
  | `customers/models.py` | `Customer`, `CustomerContact`, `CustomerNote`, `CustomerHistory`, `CustomerBackup`, `CustomerCreateRequest`, delinquency models |
  | `customers/views.py` | List/CRUD, duplicate detection, create-request approval flow, import/export |
  | `customers/permissions.py` | Role-based visibility and edit rules |
  | `customers/context_processors.py` | Builds the navbar notification bell data |
  | `customers/urls.py` | All routes |
  | `templates/customers/` + `templates/base.html` | UI, including the approval inbox and notification dropdown |

---

## 2. Core model: `Customer`

Central fields:

- **Identity:** `company_name`, `contact_person_name`, `contact_person_position`,
  `email` (required), `phone_number`, `address`.
- **Business classification:** `industry` (~24 sectors), `territory` (NCR cities
  + provinces).
- **Status flags:**
  - `is_vip` — manually flagged VIP/high-value account.
  - `is_active` — manual active/inactive.
  - `is_millionaire_account` — **system-managed**; set when cumulative won
    revenue exceeds ₱1,000,000.
  - `auto_inactive_flag` — **system-managed**; set when there's been no sales
    activity within the configured period.
  - `lifetime_won_revenue`, `last_sales_activity_at`, `status_last_synced_at` —
    system-managed metrics synced from the sales funnel/activities.
- **Assignment:** `salesperson` — FK to `User` (`on_delete=SET_NULL`), limited to
  roles `salesperson, supervisor, asm, sm, avp` who are active.

Helper properties: `is_effectively_active` (`is_active AND NOT auto_inactive_flag`),
`display_status` ("Millionaire Active/Inactive", "Active", "Inactive"),
`full_name`, and `create_backup()` which snapshots the record into a
`CustomerBackup` before risky changes.

**Related models:** `CustomerContact` (max 4 per customer, one primary — enforced
in `save()`), `CustomerNote`, `CustomerHistory` (audit trail with before/after
JSON and the AE-at-time-of-change for sales credit), `CustomerBackup`
(JSON snapshot + restore).

---

## 3. Managing duplicates

There is **no database-level unique constraint** on `company_name` or `email`.
Duplicate control is handled in two complementary ways: **prevention at creation
time** and **detection after the fact**.

### 3a. Company-name normalization — the shared foundation

Both prevention and detection rely on `_normalize_company_name()`
(`customers/views.py`). It reduces a raw company name to a comparable "core":

1. Lowercase the name.
2. Replace every non-alphanumeric character with a space (strips punctuation).
3. Split into word tokens.
4. Drop trailing legal suffixes: `corp, corporation, inc, incorporated, co,
   company, ltd, limited, llc, gmbh, sa, plc`.
5. Rejoin the remaining tokens with single spaces.

So `FOLARES PHARMACEUTICALS, INC` and `Folares Pharmaceuticals, Inc.` both
normalize to `folares pharmaceuticals` and are treated as the same company.

### 3b. Prevention at creation time (the approval gate)

Handled in `create_customer()` (`customers/views.py`). Behavior depends on the
creator's role:

- **Managers** (`admin, gm, vp, marketing, avp, supervisor, asm, sm, teamlead`)
  create customers **directly** — no duplicate check is applied. They are
  trusted to have already checked.
- **Salespeople** submit the `SalespersonCustomerForm`. On a valid submit, the
  system runs `_find_similar_customers(company_name)`:
  - If **one or more similar customers are found**, the customer is **not
    created**. Instead a `CustomerCreateRequest` (status `pending`) is created,
    storing the proposed fields plus the list of `similar_matches`, and the
    salesperson sees: *"A similar customer exists. Your request has been sent to
    AVP for approval."* → this routes into the approval workflow in §4.
  - If **no similar customer is found**, the customer is created immediately.

#### Similarity scoring — `_find_similar_customers(company_name, threshold=0.75)`

For each existing customer, it compares the two normalized names using three
signals and takes the strongest:

- **Jaccard token overlap** — shared words ÷ total distinct words.
- **Sequence similarity** — Python's `SequenceMatcher(...).ratio()` on the
  normalized strings.
- **Subset bonus** — `+0.1` if one name's word set is fully contained in the
  other (catches "ACME" vs "ACME Manufacturing").

`score = min(1.0, max(jaccard, ratio) + subset_bonus)`. Any customer scoring
**≥ 0.75** is considered a potential duplicate. The top 5 matches (with score,
assigned AE, and status) are stored on the request for the approver to review.

### 3c. Detection after the fact (the "Show Duplicates" filter)

On the customer list (`customer_list` view), managers can apply
`?duplicates=yes` (available to `admin, gm, vp, marketing, avp, asm, sm,
supervisor` — not salespeople). The view:

1. Takes the user's already permission-scoped customer set.
2. Normalizes every company name into a map of `normalized name → [customer IDs]`.
3. Keeps only groups with **2 or more** customers sharing the same normalized
   name.
4. Shows just those customers, ordered by company name so duplicates sit next to
   each other, and reports `duplicate_group_count`.

Because it starts from the scoped queryset, an AVP only sees duplicates **within
their own teams**; executives see all.

### 3d. Merging duplicates — DESIGNED, NOT YET IMPLEMENTED

There is **no merge feature in the code today** — no `merge_customers` view, URL,
template, or management command exists. The "Show Duplicates" filter only
*surfaces* duplicates; combining them is still a manual decision.

A complete implementation plan lives in
[`CUSTOMER_MERGE_ANALYSIS.md`](CUSTOMER_MERGE_ANALYSIS.md). Key points from that
analysis, important to understand before anyone attempts cleanup:

- Most models point to `Customer` with `on_delete=CASCADE` (proposals, funnel
  entries, sales activities, POCs, tickets, campaign recipients, notes, history,
  backups). **Deleting a duplicate directly would destroy all of that business
  data.**
- A safe merge must, inside a transaction, re-point every related record to the
  surviving customer *before* deleting the duplicate, migrate contacts (respecting
  the 4-contact limit), sum `lifetime_won_revenue`, preserve millionaire status,
  and log the merge in `CustomerHistory`.

Until that feature is built, treat duplicate cleanup as read-only: identify them
with the filter, then coordinate manually.

---

## 4. The customer create-request approval workflow

This is the mechanism that puts a proposed customer in front of the AVP.

### Model: `CustomerCreateRequest`

Stores the proposed customer fields, `requested_by`, `status`
(`pending / approved / rejected`), `similar_matches` (JSON), review metadata
(`reviewed_by`, `reviewed_at`, `decision_notes`), and `requester_seen_at`
(a read-receipt so the requester's "decision" notification clears once seen).

- `approve(reviewer)` — only if still `pending`; creates the real `Customer`
  (assigns the salesperson only if the requester's role is `salesperson`), then
  marks the request `approved`.
- `reject(reviewer, notes)` — marks `rejected` and stores the reason.

### Views (`customers/views.py`)

| View | URL name | Who | Purpose |
|------|----------|-----|---------|
| `customer_create_requests` | `customer_create_requests` | admin, avp, gm, vp, marketing | Pending inbox; shows each request with its similar-match list |
| `approve_customer_request` | `approve_customer_request` | admin, avp, gm, vp, marketing | POST; creates the customer (guards against double-processing) |
| `reject_customer_request` | `reject_customer_request` | admin, avp, gm, vp, marketing | POST; rejects with an optional reason |
| `customer_create_request_history` | `customer_create_request_history` | approvers + salesperson | History of processed requests; salespeople see only their own and it marks them "seen" |

**Double-approval safety:** `approve_customer_request` checks the request is
still `pending` and, if another approver already handled it, reports who did —
so two AVPs clicking at once won't create two customers.

---

## 5. Notifying the AVP (and other approvers)

AVP notification is **in-app only** (the navbar bell) and is driven by a context
processor. **There are no email notifications** for customer requests.

### The context processor — `customer_request_notifications`

Located in `customers/context_processors.py` and registered globally in
`settings.py`, so it runs on every authenticated page load and feeds the navbar.

- **Approver roles** = `admin, avp, gm, vp, marketing`. For these users it loads:
  - up to 5 pending `CustomerCreateRequest`s as notifications
    (type `pending_request`, linking to the approval inbox), and
  - `pending_count` = total pending requests.
- **Requester side** (role `salesperson`): loads their own requests that were
  approved/rejected but not yet seen (type `request_decision`, linking to their
  history), plus an unread count. Opening the history view marks them seen and
  clears the badge.
- The navbar badge number = `pending_count + requester_unread_count`.

### The navbar dropdown

Rendered in `templates/base.html`. The bell shows for approver roles (and for
salespeople with decision updates), lists the notification items, color-codes by
status (pending = yellow, approved = green, rejected = red), and provides a
footer link: salespeople → "View My Request History", everyone else → "View
Pending Requests" (the approval inbox).

### Notification scoping (who sees which requests)

There are **three tiers**, all centralized in `customers/permissions.py`:

| Tier | Roles | Sees | Can approve/reject? |
|------|-------|------|---------------------|
| **Global reviewers** | `admin, gm, vp, marketing` | **All** pending requests | ✅ Yes (any) |
| **Approvers (scoped)** | `avp` | Requests from **their own team(s)** | ✅ Yes (their scope) |
| **Watchers (scoped)** | `supervisor, asm, sm` | Requests from **the people they manage** | ❌ No — view only |

Role sets in code: `GLOBAL_REVIEWER_ROLES`, `APPROVER_ROLES`
(= global + `avp`), `WATCHER_ROLES` (= `supervisor, asm, sm`), and
`REQUEST_REVIEWER_ROLES` (= everyone who can see the queue).

**How each manager's scope is resolved** — `_managed_requester_ids(user)` mirrors
that role's customer visibility so notifications match the data they already see:
- **avp / asm** → assignable users within their team(s) (`get_team_scoped_users`).
- **supervisor / teamlead** → members of the groups they manage/lead (+ self).
- **sm** → members of their assigned `sm_groups` (+ those groups' supervisors + self).

A manager with no resolvable scope sees nothing.

**Watchers are view-only by design.** Supervisors/SM/ASM get situational
awareness (they can see a customer their salesperson is trying to create, and its
duplicate matches), but the *decision* stays with the AVP or an executive. In the
inbox, watchers see a "View only" badge instead of Approve/Reject buttons.

> To promote a watcher role to a full approver later, move it from
> `WATCHER_ROLES` into `APPROVER_ROLES` — no other code changes needed.

This scoping is enforced consistently everywhere, using shared helpers:

| Where | Helper used |
|-------|-------------|
| Navbar bell (`context_processors.py`) | `pending_requests_for_reviewer(user)` |
| Approval inbox (`customer_create_requests` view) | `pending_requests_for_reviewer(user)` + `can_approve_customer_requests(user)` |
| Customer-list pending badge | `pending_requests_for_reviewer(user)` |
| Approve / reject actions | `can_approve_customer_requests(user)` + `can_approve_request(user, req)` (per-request guard) |

**Cross-scope protection:** even if a user guesses the URL of a request outside
their scope, `approve_customer_request` / `reject_customer_request` call
`can_approve_request()` and reject the action with a clear message. Watchers are
blocked from approving entirely (they lack `can_approve_customer_requests`).
Executives can act on any request.

> Note on the salesperson-facing message: it says the request was "sent to AVP,"
> which is accurate — the requesting salesperson's own AVP receives it — but their
> supervisor/SM/ASM also see it (view-only), and executives can act on it too.

---

## 6. Permissions & visibility (reference)

Defined in `customers/permissions.py`.

- `EXEC_ROLES = {admin, president, gm, vp, marketing}` → see **all** customers.
- `visible_customers_queryset(user)`:
  - **salesperson** → only customers assigned to them.
  - **supervisor / teamlead** → their groups' members' customers + their own.
  - **avp / asm** → all customers of assignable users within their teams.
  - **sm** → customers of salespeople in their explicitly assigned groups
    (+ those groups' supervisors + self).
- `can_edit_customer(user, customer)` → allowed for execs, the assigned AE, or a
  manager whose scope includes that AE (subject to `can_manage_role`).
- `assignment_targets_queryset(user)` → who a user may assign/transfer customers
  to (used by the transfer view and list filters).

---

## 7. Routes cheat sheet (`customers/urls.py`)

- **List / CRUD:** `customer_list` (`''`), `create_customer` (`add/`),
  `customer_detail`, `edit_customer`, `transfer_customer`, `toggle_customer_vip`,
  `toggle_customer_active`, `customer_history`, `add_customer_note`,
  `customer_contacts`.
- **Approval flow:** `create-requests/` (inbox),
  `create-requests/<pk>/approve/`, `create-requests/<pk>/reject/`,
  `create-requests/history/`.
- **Backups:** `customer_backups`, `create_manual_backup`, `restore_customer`,
  `backups-overview/`.
- **Import/export:** customer + contacts CSV import/export and sample templates.
- **Delinquency:** `delinquent_list`, `create_delinquency`,
  `import_delinquencies`, `clear_delinquencies`, `export_delinquencies`.
- **No merge route exists.**

---

## 8. Summary of current gaps / gotchas

1. **Merge is documented but not implemented** — the duplicates filter finds
   them; there is no in-app way to combine them yet. See
   `CUSTOMER_MERGE_ANALYSIS.md`.
2. **No DB uniqueness on customers** — duplicate prevention is behavioral (the
   salesperson approval gate), and only triggers when similarity ≥ 0.75.
3. **Reviewer notifications are three-tier and in-app only** — executives
   (admin/gm/vp/marketing) see all and can approve; AVP sees + approves their own
   team's requests; supervisor/SM/ASM see their managed people's requests
   **view-only** (no approve/reject). No email is sent.
4. **`CustomerContact.save()` caps contacts at 4** — relevant to any future merge
   or bulk import.
5. **Delinquency (`DelinquentCustomer` / `DelinquencyRecord`) is a separate
   subsystem** and is not part of the `Customer` foreign-key graph.
