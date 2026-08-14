# Sales Proposals App — Technical Documentation

**Module:** `sales_proposals`  
**URL Prefix:** `/proposals/`  
**Date:** August 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [Proposal Lifecycle](#2-proposal-lifecycle)
3. [Proposal Number Generation](#3-proposal-number-generation)
4. [Data Models](#4-data-models)
5. [Item Types](#5-item-types)
6. [Multi-Option Proposals](#6-multi-option-proposals)
7. [Financial Calculations](#7-financial-calculations)
8. [Approval Workflow](#8-approval-workflow)
9. [PDF Generation](#9-pdf-generation)
10. [Email Sending](#10-email-sending)
11. [Sales Funnel Integration](#11-sales-funnel-integration)
12. [Change Log Tracking](#12-change-log-tracking)
13. [Role-Based Access](#13-role-based-access)
14. [URL Reference](#14-url-reference)
15. [Notification System](#15-notification-system)

---

## 1. Overview

The Sales Proposals module handles the complete lifecycle of formal sales quotations — from drafting through PDF generation, customer delivery via email, internal approval workflow, and integration with the Sales Funnel pipeline.

**Key capabilities:**
- Standard single-format proposals with optional and bundled items
- Multi-option proposals presenting multiple pricing configurations
- Auto-generated proposal and reference numbers
- Professional branded PDF generation with ReportLab
- Direct email sending with PDF attachment and HTML signature
- Multi-level approval workflow based on configurable amount tiers
- Full change history audit trail
- Automatic Sales Funnel entry creation and sync

---

## 2. Proposal Lifecycle

### Status Flow

```
                 ┌────────────┐
                 │   DRAFT    │  ← Created by salesperson
                 └─────┬──────┘
                       │ (Email sent to customer)
                       ▼
                 ┌────────────┐
                 │    SENT    │  ← PDF emailed to customer
                 └─────┬──────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ ACCEPTED │ │ DECLINED │ │ EXPIRED  │
    └──────────┘ └──────────┘ └──────────┘
```

### Approval Status (Independent from Proposal Status)

```
    ┌──────────────┐
    │ NOT REQUIRED │  ← Total < ₱500,000
    └──────────────┘

    ┌──────────┐     ┌─────────────┐     ┌──────────┐
    │ PENDING  │ ──▶ │ IN PROGRESS │ ──▶ │ APPROVED │
    └──────────┘     └──────┬──────┘     └──────────┘
                            │
                            ▼
                     ┌──────────┐
                     │ REJECTED │
                     └──────────┘
```

**Important:** Approval status is separate from proposal status. A proposal can be in `draft` status while `in_progress` for approval. The system blocks email sending until approval is complete for proposals that require it.

---

## 3. Proposal Number Generation

### Proposal Number Format

```
{INITIALS}-{YEAR}-{SEQUENCE:04d}
```

**Example:** `MCB-2026-0001`

**Logic:**
1. Takes the salesperson's `initials` field (max 3 characters)
2. If no initials: uses first letter of first name + first letter of last name
3. If still empty: uses first 3 characters of username
4. Pads to exactly 3 characters with 'X'
5. Finds the maximum sequence number across ALL proposals for that year (global, not per-user)
6. Increments by 1, checks uniqueness in a loop

### Reference Number Format

```
{INITIALS}{YYYYMMDD}{SEQUENCE:03d}
```

**Example:** `MCB20260808001`

**Logic:**
- Uses the proposal's date (not today's date)
- Sequence is per-salesperson (count of their total proposals + 1)
- Uniqueness loop ensures no conflicts

---

## 4. Data Models

### Proposal (Main Entity)

| Field Group | Key Fields |
|---|---|
| Identity | `proposal_number` (auto), `reference_number` (auto) |
| Relationships | `customer` FK, `created_by` FK |
| Dates | `date`, `valid_until` |
| Contact | `contact_name`, `contact_email`, `contact_phone` |
| Currency | `currency` (PHP/USD), `exchange_rate` |
| Terms | `payment_terms`, `delivery_lead_time`, `warranty`, `stock_availability` |
| Content | `subject`, `introduction`, `closing`, `special_note` |
| Options | `include_bank_details`, `show_discount`, `use_total_price_label`, `discount_amount` |
| Bank (PHP) | `php_bank_name`, `php_account_name`, `php_account_number`, `php_account_type`, `php_branch` |
| Bank (USD) | `usd_beneficiary_name`, `usd_beneficiary_address`, `usd_account_number`, `usd_bank_address`, `usd_swift_code` |
| Financials | `subtotal`, `total_amount`, `total_cost`, `gross_profit`, `tax_type`, `tax_rate`, `tax_amount` |
| Format | `is_multi_option` |
| Status | `status`, `approval_status`, `approval_required`, `approval_total_php`, `approval_version` |
| Timestamps | `created_at`, `updated_at`, `approval_submitted_at`, `approved_at` |

### ProposalItem (Line Items)

| Field | Description |
|---|---|
| `proposal` | FK to Proposal |
| `option_group` | FK to ProposalOptionGroup (nullable, multi-option only) |
| `part_number` | Product SKU / part number |
| `description` | Full item description |
| `quantity` | Decimal (supports fractional) |
| `unit_price` | Selling price per unit |
| `unit_cost` | Internal cost per unit |
| `warranty` | Per-item warranty text |
| `is_optional` | Excluded from totals, labeled "Option N" |
| `is_bundle` | Has sub-components listed in `bundled_items` |
| `bundled_items` | Text: one component per line (`PART | Description | Qty`) |
| `amount` | Computed: `quantity × unit_price` (auto-saved) |
| `total_cost` | Computed: `quantity × unit_cost` (auto-saved) |

### ProposalOptionGroup (Multi-Option)

| Field | Description |
|---|---|
| `proposal` | FK to Proposal |
| `name` | Display name (e.g., "OPTION 1") |
| `sort_order` | Ordering |
| `notes` | Optional group notes |

Properties: `subtotal`, `total_cost`, `profit`

### ProposalAttachment

| Field | Description |
|---|---|
| `proposal` | FK to Proposal |
| `file` | Uploaded file |
| `include_in_email` | Toggle (auto-disabled for costing matrix files) |
| `uploaded_by` | FK to User |

Auto-detection: Files with "costing" or "matrix" in their name are flagged as confidential and cannot be included in customer emails.

### ProposalApprovalTier (Configuration)

| Field | Description |
|---|---|
| `name` | Tier display name (e.g., "₱500K – ₱1M") |
| `min_amount_php` | Minimum PHP amount for this tier |
| `max_amount_php` | Maximum (null = unlimited) |
| `chain` | Comma-separated roles: `supervisor,asm,avp_or_gm` |
| `order` | Priority when multiple tiers match |
| `active` | Tier is currently active |

### ProposalApprovalStep (Workflow Instance)

| Field | Description |
|---|---|
| `proposal` | FK to Proposal |
| `level` | Step number (1, 2, 3...) |
| `approver` | FK to User (the person who must approve) |
| `status` | pending / approved / rejected |
| `decided_at` | Timestamp of decision |
| `comment` | Approver's note |

### ProposalChangeLog (Audit)

| Field | Description |
|---|---|
| `proposal` | FK to Proposal |
| `changed_by` | FK to User |
| `changed_at` | Timestamp |
| `summary` | Brief description (e.g., "Proposal updated") |
| `details` | JSON diff of before/after values |

---

## 5. Item Types

### Regular Items
- `is_optional = False`, `is_bundle = False`
- Included in all total calculations
- Shown normally in PDF table

### Optional Items
- `is_optional = True`
- **Excluded** from subtotal and grand total
- Labeled "Option 1", "Option 2", etc. sequentially in PDF
- When ANY optional item exists, the Grand Total row is hidden in the PDF
- Highlighted in yellow in the detail view

### Bundled Items
- `is_bundle = True`
- A single priced parent row with sub-components
- Sub-components listed in `bundled_items` text field
- Format: `PART NUMBER | Description | Qty` (one per line)
- Supports tab-separated paste from Excel (3, 4, or 5 columns)
- **5-column paste** (Part Number, Description, Qty, Unit Price, Total Price): pricing columns 4 & 5 are automatically ignored — only the first 3 are kept
- In the PDF: parent row shows price; sub-component rows are indented without prices

---

## 6. Multi-Option Proposals

When `is_multi_option = True`, the proposal uses a different format:

### Structure

```
Proposal Header
├── OPTION 1 (ProposalOptionGroup)
│   ├── Item A (ProposalItem with option_group FK)
│   ├── Item B
│   └── Total Investment: ₱X,XXX,XXX
├── OPTION 2 (ProposalOptionGroup)
│   ├── Item C
│   ├── Item D
│   └── Total Investment: ₱Y,YYY,YYY
└── Terms & Conditions (shared)
```

### Key Differences from Standard Format

| Aspect | Standard | Multi-Option |
|---|---|---|
| Items structure | Flat list | Grouped by ProposalOptionGroup |
| Totals | Single subtotal/grand total | Per-group subtotal ("Total Investment") |
| Optional items | Supported (`is_optional`) | Not used (entire groups serve as options) |
| Discount | Supported (`show_discount`) | Not available |
| Grand Total | Shown (or hidden if optionals exist) | Not shown (each option stands alone) |
| Approval threshold | Based on `total_amount` | Based on **highest** group subtotal |
| PDF rendering | Single table | Separate table per group with section header |

### Creation Flow (UI)

1. User clicks "Multi-Option Proposal" button on proposal list
2. Form shows header fields (same as standard minus discount)
3. Option Groups section: collapsible cards, each with editable name + item table
4. Items managed via JavaScript: add/remove rows per group, live subtotal calculation
5. On submit: items serialized as JSON (`option_items_json`), groups parsed from formset

---

## 7. Financial Calculations

### `Proposal.calculate_totals()` — Standard Format

```python
subtotal = sum(item.amount for non-optional items)
total_cost = sum(item.total_cost for non-optional items)

# Tax removed (hardcoded to 0%)
tax_type = 'ZERO'
tax_rate = 0
tax_amount = 0

# Discount (only if enabled and > 0)
effective_discount = discount_amount if show_discount else 0

total_amount = max(subtotal - effective_discount, 0)
gross_profit = total_amount - (total_cost × 1.05)  # 5% internal cost uplift

# PHP equivalent for approval
approval_total_php = total_amount × exchange_rate  (if USD)

# Trigger approval if ≥ ₱500,000
approval_required = (approval_total_php >= 500000)
```

### Multi-Option Totals (`_calculate_multi_option_totals`)

```python
# Use the HIGHEST option group subtotal
max_subtotal = max(group.subtotal for group in option_groups)
max_cost = corresponding group's total_cost

subtotal = max_subtotal
total_amount = max_subtotal  (no discount in multi-option)
gross_profit = max_subtotal - (max_cost × 1.05)
approval_total_php = max_subtotal × exchange_rate
```

### Display Properties

| Property | Includes Optional Items? | Use Case |
|---|---|---|
| `subtotal` | No | Official total for invoicing/approval |
| `total_amount` | No | After discount, the binding total |
| `quoted_subtotal` | Yes (all items) | Display: what customer sees |
| `quoted_total_amount` | Yes (all items) | Display total including optionals |
| `quoted_amount_php` | Yes | PHP equivalent for display |

---

## 8. Approval Workflow

### When Is Approval Required?

Approval is triggered automatically when `approval_total_php >= ₱500,000`.

For multi-option proposals, this uses the **highest** option group subtotal.

### Who Can Create Proposals?

Any role that can view the customer can create proposals for them:

| Creator Role | Typical Scenario |
|---|---|
| Salesperson | Creates proposals for their own assigned customers |
| Supervisor | Creates for their group members' customers |
| SM (Sales Manager) | Creates for subordinates' customers (e.g., team members) |
| ASM | Creates for any customer in their managed teams |
| Executives | Creates for any customer in the system |

**Business rule:** The approval chain adjusts based on the creator's role — approvers must always outrank the creator. A Sales Manager creating a proposal will never have a Supervisor as approver.

### How the Approval Chain Is Built

#### Step 1: Resolve the Creator's Team/Group

The system determines which Group (and therefore which Team hierarchy) applies to this proposal. The lookup adapts to the creator's role:

| Creator Role | Group Resolution Method |
|---|---|
| Salesperson | `creator.team_membership.group` (OneToOne via TeamMembership) |
| SM | `creator.sm_groups.first()` (M2M: Group.sm_managers) |
| ASM | `Team.objects.filter(asm=creator).first()` → team.groups.first() |
| Supervisor | `creator.managed_groups.first()` (FK: Group.supervisor) |

Once the Group is resolved, the hierarchy is:
```
Group → get_manager()      → Supervisor
Group → team.asm           → ASM
Group → team.avp           → AVP / GM
```

#### Step 2: Apply Role Hierarchy Filter

Not all discovered approvers are eligible. The system enforces a strict role authority hierarchy:

```
Level 1: Salesperson
Level 2: Teamlead
Level 3: Supervisor
Level 4: ASM / SM
Level 5: AVP
Level 6: VP / GM
Level 7: President / Admin
```

**Rule:** An approver is only included in the chain if their role level is **strictly higher** than the creator's role level. This means:
- A **Salesperson** (level 1) creating a ₱2.7M proposal → chain may include Supervisor (3), ASM (4), AVP (5)
- A **Sales Manager** (level 4) creating the same proposal → Supervisor (3) skipped, ASM (4) skipped → only AVP (5) qualifies
- An **AVP** (level 5) creating a proposal → only VP/GM (6) or President (7) can approve

#### Step 3: Find Matching Approval Tier

```python
ProposalApprovalTier.objects.filter(
    active=True,
    min_amount_php <= approval_total_php,
    (max_amount_php is NULL OR max_amount_php >= approval_total_php)
).order_by('order', 'min_amount_php').first()
```

#### Step 4: Build the Chain

If a tier is found (e.g., `chain = "supervisor,asm,avp_or_gm"`):
- Maps each role to the actual user from the hierarchy
- Skips the proposal creator (identity check: can't approve own proposal)
- Skips any approver whose role level ≤ creator's level (hierarchy check)
- Deduplicates

**Fallback if no tier matches:**

| Amount Threshold | Potential Approver | Added only if... |
|---|---|---|
| ≥ ₱500,000 | Supervisor | ...outranks creator |
| ≥ ₱1,000,000 | ASM | ...outranks creator |
| ≥ ₱3,000,000 | AVP/GM | ...outranks creator |

#### Step 5: Escalation (Empty Chain Safety Net)

If approval is required (`approval_total_php >= ₱500K`) but the chain is empty after filtering (all lower-tier approvers were outranked by the creator), the system **automatically escalates** to the AVP/GM — the highest available authority in the team hierarchy.

This prevents proposals from being stuck in "Pending — Awaiting chain generation."

### Example Scenarios

| Creator | Amount | Approvers in Chain | Reason |
|---|---|---|---|
| Salesperson (L1) | ₱600K | Supervisor | Standard: ≥₱500K tier |
| Salesperson (L1) | ₱2.7M | Supervisor, ASM | ≥₱500K + ≥₱1M tiers |
| Salesperson (L1) | ₱5M | Supervisor, ASM, AVP | All three tiers |
| **SM (L4)** | **₱2.7M** | **AVP only** | Supervisor (L3) skipped, ASM (L4) skipped → escalation to AVP (L5) |
| SM (L4) | ₱600K | AVP only | Supervisor skipped → escalation |
| Supervisor (L3) | ₱2.7M | ASM, AVP | Supervisor can't approve own, ASM outranks (L4) |
| AVP (L5) | ₱5M | VP/GM | Only higher authority qualifies |

### Approval Step Execution

**Sequential enforcement:** Each level must be approved before the next can act.

```
Level 1 (Supervisor) → pending
Level 2 (ASM)        → pending (can't act until Level 1 is approved)
Level 3 (AVP)        → pending (can't act until Level 2 is approved)
```

**Approver actions:**
- **Approve**: Step marked `approved`, moves to next level. If last level → proposal `fully approved`.
- **Reject**: Step marked `rejected`, entire proposal → `rejected`. Stops chain immediately.

**Chain restart on edit:**
If a proposal is edited AFTER approval steps have been created:
- If the chain composition changed OR any step already has a decision → ALL steps deleted, chain rebuilt from scratch, version incremented.
- This ensures stale approvals don't persist on modified content.

### Approval Configuration (Admin)

Executives can manage tiers via:
- `/proposals/approvals/tiers/` — list all tiers
- Create, edit, delete individual tiers
- Import tiers from CSV
- Export tiers to CSV
- Seed default tiers (predefined amounts/chains)

### Default Tier Configuration

| Tier Name | Range | Chain |
|---|---|---|
| Standard (₱500K–₱1M) | ₱500,000 – ₱999,999 | supervisor |
| Large (₱1M–₱3M) | ₱1,000,000 – ₱2,999,999 | supervisor, asm |
| Enterprise (₱3M+) | ₱3,000,000 – unlimited | supervisor, asm, avp_or_gm |

> **Note:** Even with a tier that lists `supervisor, asm`, if the creator outranks those roles, they are automatically skipped and the system escalates to the next higher authority.

---

## 9. PDF Generation

The PDF is generated using **ReportLab** with `SimpleDocTemplate` (US Letter size).

### PDF Sections

| Section | Content |
|---|---|
| **Header** | Full-width branded image (`Proposal_Header.png`) or fallback logo |
| **Reference** | Reference number + date |
| **Customer** | Contact name, company, phone, email |
| **Salutation** | "Dear {name}," |
| **Introduction** | Custom text or default boilerplate |
| **Items Table** | See below for standard vs. multi-option |
| **Special Note** | Bold highlighted text (if set) |
| **Terms Table** | Price Validity, Stock, Payment, Cancellation, Bank Details, Delivery, Other |
| **Closing** | Trust statement, conforme request |
| **Signatures** | Salesperson signature image + dynamic job title + Conforme block |
| **Footer** | Footer image on every page (via canvas callback) |

### Items Table — Standard Format

| Column | Width |
|---|---|
| ITEM # | 0.45" |
| PART NUMBER | 1.1" |
| PRODUCT DESCRIPTION | 2.4" |
| QTY | 0.5" |
| UNIT PRICE | 1.0" |
| EXTENDED PRICE (or TOTAL PRICE) | 1.1" |
| WARRANTY | 0.95" |

- Red header row with white text
- Optional items: "Option N" italic label in description
- Bundle components: indented sub-rows without prices
- Subtotal + optional Discount + Grand Total rows at bottom (red background)
- Grand Total hidden when optional items exist

### Items Table — Multi-Option Format

For each `ProposalOptionGroup`:
- Bold red section header: "OPTION 1", "OPTION 2", etc.
- Same column structure as standard
- Yellow "Total Investment" row at bottom of each group's table
- No combined grand total across options

### Font Handling

Priority order:
1. Bundled fonts: `DejaVuSans.ttf`, `LiberationSans-Regular.ttf`
2. System fonts: macOS Arial, Ubuntu Liberation/DejaVu
3. Fallback: Helvetica (built into PDF standard)

Bold variant loaded separately (`LiberationSans-Bold.ttf` or `Arial_Bold.ttf`).

---

## 10. Email Sending

### Pre-conditions

- If `approval_required = True` and `approval_status != 'approved'` → sending blocked with warning
- The proposal must have at least one valid recipient email

### Email Composition

| Component | Details |
|---|---|
| Subject | `Proposal: {subject} - {proposal_number}` |
| From | Current user's email (or DEFAULT_FROM_EMAIL) |
| To | Customer contact email(s) — supports multiple (comma/semicolon separated) |
| CC | Optional: supervisor email, additional customer contacts, free-form CC field |
| Reply-To | Current user's email |
| Body (HTML) | Cover message + company signature with social icons (inline CID images) |
| Body (Text) | Plain-text alternative |
| Attachments | Proposal PDF + selected non-costing-matrix file attachments |

### Post-Send Actions

1. Proposal status → `'sent'`
2. `SalesActivity` logged (type: "Proposals", status: completed)
3. `update_sales_funnel()` called (syncs retail/cost values)

### Costing Matrix Protection

Attachments with filenames containing "costing" or "matrix" (case-insensitive):
- `include_in_email` auto-disabled in the form
- Cannot be sent to customers even if checkbox is somehow checked
- Marked with "Confidential" warning label in the UI

---

## 11. Sales Funnel Integration

### How It Works

Every proposal automatically creates or updates a Sales Funnel entry.

**On first save / email send:**
```python
SalesFunnel.objects.create(
    date_created = proposal.date,
    company_name = customer.company_name,
    requirement_description = proposal.subject,
    cost = quoted_cost_php × 1.05,   # internal cost with uplift
    retail = quoted_amount_php,       # full quoted amount (including optionals)
    stage = 'quoted',                 # Newly Quoted (Pink Funnel)
    salesperson = proposal.created_by,
    customer = proposal.customer,
    deal_outcome = 'active',
    proposal = proposal               # FK link for syncing
)
```

**On subsequent edits:**
```python
# Finds existing entry linked to this proposal
funnel.retail = updated quoted_amount_php
funnel.cost = updated quoted_cost_php × 1.05
funnel.requirement_description = proposal.subject
funnel.save()
```

---

## 12. Change Log Tracking

Every time a proposal is edited (via `proposal_update` view):

1. **Before save**: Snapshot all header fields + all items (with field values)
2. **After save**: Compare each field
3. **Header changes**: Recorded as `{field: {from: old_value, to: new_value}}`
4. **Item changes**: Recorded as `{items: {item_pk: {status: 'added'|'updated'|'deleted', before: {...}, after: {...}}}}`
5. **If any changes detected**: `ProposalChangeLog.objects.create(...)` with JSON details

### Tracked Header Fields

`customer_id`, `date`, `valid_until`, `stock_availability`, `subject`, `payment_terms`, `delivery_lead_time`, `warranty`, `special_note`, `introduction`, `closing`, `include_bank_details`, `show_discount`, `discount_amount`, `currency`, `exchange_rate`

### Tracked Item Fields

`part_number`, `description`, `quantity`, `unit_cost`, `unit_price`, `warranty`, `is_optional`, `is_bundle`, `bundled_items`

---

## 13. Role-Based Access

### Proposal List Visibility

| Role | Sees |
|---|---|
| Salesperson | Own proposals only |
| Supervisor | Own + all group members' proposals |
| Teamlead | Own + led group members' proposals |
| ASM | Own + all team members' proposals (via `asm_teams`) |
| SM | Own + assigned group members' proposals (via `sm_groups`) |
| AVP | Own + all managed team members' proposals |
| Admin / VP / GM / President | All proposals |

### Executive View (Team Grouping)

For roles `admin, president, asm, vp, avp, gm`:
- Proposals are grouped by team in the list view
- Each group shows team name + total investment + proposal rows

### Approval Tier Management

Restricted to executives only (`admin, president, vp, avp, gm`):
- Create, edit, delete approval tiers
- Import/export tiers as CSV
- Seed default tier configuration

---

## 14. URL Reference

| URL | View | Purpose |
|---|---|---|
| `/proposals/` | `proposal_list` | List all proposals (role-scoped) |
| `/proposals/create/` | `proposal_create` | Create standard proposal |
| `/proposals/create/multi-option/` | `multi_option_proposal_create` | Create multi-option proposal |
| `/proposals/<pk>/` | `proposal_detail` | View proposal details |
| `/proposals/<pk>/edit/` | `proposal_update` | Edit standard proposal |
| `/proposals/<pk>/edit/multi-option/` | `multi_option_proposal_update` | Edit multi-option proposal |
| `/proposals/<pk>/delete/` | `proposal_delete` | Delete proposal |
| `/proposals/<pk>/pdf/` | `proposal_pdf` | Generate and view PDF |
| `/proposals/<pk>/email/` | `proposal_email` | Send proposal via email |
| `/proposals/<pk>/approve/` | `approve_proposal` | Approve current step |
| `/proposals/<pk>/reject/` | `reject_proposal` | Reject proposal |
| `/proposals/approvals/inbox/` | `approvals_inbox` | View pending approvals |
| `/proposals/approvals/tiers/` | `approval_tier_list` | Manage approval tiers |
| `/proposals/approvals/tiers/create/` | `approval_tier_create` | Create tier |
| `/proposals/approvals/tiers/<pk>/edit/` | `approval_tier_edit` | Edit tier |
| `/proposals/approvals/tiers/<pk>/delete/` | `approval_tier_delete` | Delete tier |
| `/proposals/approvals/tiers/export/` | `approval_tier_export` | Export tiers CSV |
| `/proposals/approvals/tiers/import/` | `approval_tier_import` | Import tiers CSV |
| `/proposals/approvals/tiers/template/` | `approval_tier_template` | Download import template |
| `/proposals/approvals/tiers/seed-defaults/` | `approval_tier_seed_defaults` | Reset to defaults |

---

## 15. Notification System

### Context Processor (`proposal_approval_notifications`)

Injected into every page via Django template context processor:

**Logic:**
1. Query `ProposalApprovalStep` where:
   - `approver = current_user`
   - `status = 'pending'`
   - `level` = minimum pending level for that proposal (ensures only current-turn approver sees it)
2. Returns:
   - `proposal_approval_notifications`: List of up to 5 notification dicts (type, title, message, url, timestamp)
   - `proposal_approval_notification_count`: Total count for badge display

**Used in:** Navbar notification bell icon — shows badge with pending approval count and dropdown with recent pending approvals.

---

*Document prepared by the Development Team — Micro Image International Corp. — August 2026*
