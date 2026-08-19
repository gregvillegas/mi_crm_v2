# Sales Order App — Feature Plan

**Status:** Pending Management Approval  
**Author:** Development Team  
**Date:** August 2026  
**Priority:** New Module — Critical Business Process  
**Estimated Effort:** Phase 1: 8–10 days | Phase 2: 5–7 days | Phase 3: 3–5 days

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Context](#2-business-context)
3. [Current System Integration Points](#3-current-system-integration-points)
4. [Approval Workflow Design](#4-approval-workflow-design)
5. [Data Model Design](#5-data-model-design)
6. [Workflow State Machine](#6-workflow-state-machine)
7. [User Interface Plan](#7-user-interface-plan)
8. [Email Notifications](#8-email-notifications)
9. [Role-Based Access Matrix](#9-role-based-access-matrix)
10. [PDF Generation](#10-pdf-generation)
11. [Integration with Existing Modules](#11-integration-with-existing-modules)
12. [New User Roles Required](#12-new-user-roles-required)
13. [Implementation Phases](#13-implementation-phases)
14. [Files to Create / Modify](#14-files-to-create--modify)
15. [Risks and Mitigations](#15-risks-and-mitigations)
16. [Acceptance Criteria](#16-acceptance-criteria)
17. [Decisions Required from Management](#17-decisions-required-from-management)

---

## 1. Executive Summary

Build a **Sales Order** module that transforms accepted Sales Proposals into formal internal purchase/delivery orders. The Sales Order follows a **6-level sequential approval chain** spanning Sales, Accounting, Executive, Warehouse, and Purchasing departments — ensuring proper financial checks, management sign-off, and supply chain execution before goods are committed.

**Key principle:** A Sales Order is created FROM a Sales Proposal. It inherits customer, items, pricing, and terms — but lives independently with its own status lifecycle and multi-department approval flow.

---

## 2. Business Context

### Current Flow (Before Sales Order)

```
Salesperson creates Proposal
  → Proposal sent to Customer
  → Customer accepts (verbal/email)
  → ??? (manual process, no system tracking)
  → Goods delivered somehow
```

### Proposed Flow (With Sales Order)

```
Salesperson creates Proposal
  → Proposal sent to Customer
  → Customer accepts
  → Salesperson creates Sales Order FROM the accepted Proposal
  → Sales Order enters 6-level approval pipeline:
      1. Sales Supervisor — verifies items, pricing, margin
      2. Sales Manager / AVP — strategic approval
      3. Accounting Supervisor — checks balance, credit terms, AR
      4. GM — executive sign-off (for high-value orders)
      5. Warehouse Supervisor — confirms stock availability
      6. Purchasing Supervisor — issues PO to supplier
  → Order fulfilled
  → Delivery to customer
```

---

## 3. Current System Integration Points

| Existing Module | How Sales Order Connects |
|---|---|
| **Sales Proposals** | SO is created from a Proposal. Inherits: customer, items, pricing, terms, currency |
| **Sales Funnel** | When SO is fully approved → funnel deal_outcome can be marked 'won' automatically |
| **Customers** | SO links to Customer (same FK as Proposal) |
| **Teams** | Approval chain resolves approvers from the salesperson's Team → Group → Supervisor hierarchy |
| **Users** | New roles needed: `accounting_supervisor`, `warehouse_supervisor`, `purchasing_supervisor` (already exist in JOB_TITLE_CHOICES but not in ROLE_CHOICES) |
| **Sales Monitoring** | SO creation logged as a sales activity |
| **Gamification** | Points awarded for SO creation and full approval |

### Data Inherited from Proposal

| From Proposal | To Sales Order |
|---|---|
| `proposal_number` | `source_proposal` (FK reference) |
| `customer` | `customer` (copied FK) |
| `created_by` | `salesperson` (the AE who owns the deal) |
| `currency`, `exchange_rate` | Copied directly |
| `payment_terms`, `delivery_lead_time` | Copied directly |
| `items` (all ProposalItems) | Copied as `SalesOrderItem` records |
| `total_amount`, `total_cost` | Recalculated from SO items |
| `contact_name/email/phone` | Copied as delivery contact |

---

## 4. Approval Workflow Design

### 6-Level Sequential Approval Chain

| Level | Approver Role | Department | Responsibility |
|---|---|---|---|
| 1 | **Sales Supervisor** | Sales | Verify items, pricing, margin, customer relationship |
| 2 | **Sales Manager (SM) / AVP** | Sales Management | Strategic approval, deal alignment with targets |
| 3 | **Accounting Supervisor** | Finance | Credit check, AR balance, payment terms compliance |
| 4 | **General Manager (GM)** | Executive | Final business approval (may be skipped for low-value orders) |
| 5 | **Warehouse Supervisor** | Operations | Stock availability verification, allocation |
| 6 | **Purchasing Supervisor** | Supply Chain | Issue Purchase Order to supplier, confirm lead time |

### Approval Actions Per Level

Each approver at each level can take one of three actions:

| Action | Effect | Next State |
|---|---|---|
| **Approve** | Moves to next level in chain | `level_N_approved` → advances to level N+1 |
| **Reject** | Stops the entire workflow | `rejected` — SO goes back to salesperson for revision or cancellation |
| **Return for Correction** | Sends back to salesperson WITHOUT rejecting | `returned` — salesperson edits and resubmits (restarts from level 1) |

### Conditional Levels

| Condition | Rule |
|---|---|
| GM approval (Level 4) | **Required** only when total ≥ ₱500,000 (configurable threshold) |
| SM/AVP (Level 2) | Uses team hierarchy: SM if assigned to group, else AVP of team |
| Accounting (Level 3) | Always required — financial verification is mandatory |
| Warehouse (Level 5) | Always required — stock must be confirmed before PO |
| Purchasing (Level 6) | Always required — PO to supplier is the final step |

### Approver Resolution Logic

```python
Level 1: salesperson.team_membership.group.supervisor
Level 2: salesperson.team_membership.group.sm_managers.first() OR team.avp
Level 3: User.objects.filter(role='accounting_supervisor').first()  # dedicated role
Level 4: User.objects.filter(role='gm').first()  # or team.avp if role=gm not found
Level 5: User.objects.filter(role='warehouse_supervisor').first()
Level 6: User.objects.filter(role='purchasing_supervisor').first()
```

---

## 5. Data Model Design

### Model: `SalesOrder`

```python
class SalesOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Approval'),
        ('in_progress', 'Approval In Progress'),
        ('approved', 'Fully Approved'),
        ('rejected', 'Rejected'),
        ('returned', 'Returned for Correction'),
        ('po_issued', 'PO Issued to Supplier'),
        ('fulfilled', 'Fulfilled / Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    # Auto-generated: SO-{INITIALS}-{YEAR}-{SEQ}
    order_number = models.CharField(max_length=50, unique=True, editable=False)

    # Source
    source_proposal = models.ForeignKey('sales_proposals.Proposal', on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='sales_orders')

    # Core relationships
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='sales_orders')
    salesperson = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_sales_orders')

    # Customer PO reference (from client)
    customer_po_number = models.CharField(max_length=100, blank=True,
                                          help_text="Customer's Purchase Order reference number")
    customer_po_date = models.DateField(null=True, blank=True)

    # Contact snapshot
    contact_name = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    delivery_address = models.TextField(blank=True)

    # Financial
    currency = models.CharField(max_length=3, choices=[('PHP','PHP'),('USD','USD')], default='PHP')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Terms (inherited from proposal, editable)
    payment_terms = models.TextField(default="30 days")
    delivery_lead_time = models.CharField(max_length=200, blank=True)
    warranty = models.CharField(max_length=200, blank=True)
    special_instructions = models.TextField(blank=True)

    # Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    current_approval_level = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    fully_approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    return_reason = models.TextField(blank=True)

    # Supplier PO (filled by Purchasing at Level 6)
    supplier_po_number = models.CharField(max_length=100, blank=True)
    supplier_po_date = models.DateField(null=True, blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Model: `SalesOrderItem`

```python
class SalesOrderItem(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    part_number = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    warranty = models.CharField(max_length=150, blank=True)

    # Stock tracking (filled by Warehouse at Level 5)
    stock_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending Check'),
        ('in_stock', 'In Stock'),
        ('partial', 'Partial Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('on_order', 'On Order from Supplier'),
    ], default='pending')
    stock_notes = models.TextField(blank=True)
```

### Model: `SalesOrderApprovalStep`

```python
class SalesOrderApprovalStep(models.Model):
    STEP_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('returned', 'Returned for Correction'),
        ('skipped', 'Skipped (not required)'),
    ]

    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='approval_steps')
    level = models.PositiveIntegerField()  # 1-6
    level_name = models.CharField(max_length=50)  # e.g., "Sales Supervisor"
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='so_approvals')
    status = models.CharField(max_length=20, choices=STEP_STATUS_CHOICES, default='pending')
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Model: `SalesOrderChangeLog`

```python
class SalesOrderChangeLog(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='change_logs')
    action = models.CharField(max_length=50)  # created, submitted, approved, rejected, returned, edited, fulfilled
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(null=True, blank=True)
    comment = models.TextField(blank=True)
```

---

## 6. Workflow State Machine

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
┌─────────┐    ┌───────────┐    ┌─────────────┐    ┌────────┴───┐
│  DRAFT  │───▶│ SUBMITTED │───▶│ IN_PROGRESS │───▶│  APPROVED  │
└─────────┘    └───────────┘    └─────────────┘    └────────────┘
     ▲              │                  │                   │
     │              │                  │                   ▼
     │              ▼                  ▼            ┌────────────┐
     │        ┌──────────┐      ┌──────────┐       │ PO_ISSUED  │
     │        │ RETURNED │      │ REJECTED │       └────────────┘
     │        └──────────┘      └──────────┘              │
     │              │                                     ▼
     └──────────────┘                             ┌────────────┐
     (edit & resubmit)                            │ FULFILLED  │
                                                  └────────────┘
```

### State Transitions

| From | To | Trigger |
|---|---|---|
| `draft` | `submitted` | Salesperson clicks "Submit for Approval" |
| `submitted` | `in_progress` | First approver (Supervisor) sees it in their inbox |
| `in_progress` | `in_progress` | Each level approves → advances to next level |
| `in_progress` | `approved` | Level 6 (Purchasing) approves → fully approved |
| `in_progress` | `rejected` | Any approver rejects |
| `in_progress` | `returned` | Any approver returns for correction |
| `returned` | `draft` | Salesperson edits the SO |
| `draft` | `submitted` | Salesperson resubmits (approval restarts from Level 1) |
| `approved` | `po_issued` | Purchasing enters supplier PO number |
| `po_issued` | `fulfilled` | Warehouse confirms delivery complete |
| Any active | `cancelled` | Admin/GM cancels the order |

---

## 7. User Interface Plan

### Views Required

| View | URL | Access |
|---|---|---|
| Sales Order List | `/orders/` | All sales roles (scoped by hierarchy) |
| Create from Proposal | `/orders/create/?proposal=<pk>` | Salesperson |
| Sales Order Detail | `/orders/<pk>/` | All roles in chain |
| Edit Sales Order | `/orders/<pk>/edit/` | Salesperson (only in draft/returned) |
| Approval Inbox | `/orders/approvals/` | All approver roles |
| Approve/Reject/Return | `/orders/<pk>/approve/` | Current level approver |
| PDF View | `/orders/<pk>/pdf/` | All with access |
| Fulfillment | `/orders/<pk>/fulfill/` | Warehouse Supervisor |

### Create Sales Order Flow

1. Salesperson goes to Proposal detail → clicks **"Create Sales Order"** button
2. System pre-fills all fields from the Proposal (customer, items, terms)
3. Salesperson adds: Customer PO Number, PO Date, Delivery Address, Special Instructions
4. Salesperson can adjust quantities (if customer ordered partial)
5. Clicks **"Submit for Approval"** or saves as Draft

### Approval Inbox

Each approver role sees a unified inbox showing:
- SO Number, Customer, Amount, Submitted Date, Current Level
- Filter by: Pending My Action | All | My History
- Action buttons: Approve | Reject | Return for Correction
- Comment field (mandatory for Reject/Return)

### Sales Order Detail Page Layout

```
┌─────────────────────────────────────────────────────┐
│ Sales Order SO-MCB-2026-0001        [PDF] [Edit]    │
├─────────────────────────────────────────────────────┤
│ Status: ● Approval In Progress (Level 3/6)          │
│                                                     │
│ ┌─── Progress Bar ──────────────────────────────┐   │
│ │ ✓ Supervisor  ✓ SM/AVP  ● Accounting  ○ GM   │   │
│ │ ○ Warehouse  ○ Purchasing                     │   │
│ └───────────────────────────────────────────────┘   │
│                                                     │
│ Customer: MEDICARE PLUS INC                         │
│ Subject: Computer Laptops (164 units)               │
│ Amount: ₱47,001,908.00                              │
│ Customer PO#: PO-2026-1234                          │
│                                                     │
│ ┌─── Items Table ───────────────────────────────┐   │
│ │ # | Part Number | Description | Qty | Price   │   │
│ │ 1 | CW6L2PT#UUF| HP ZBook... | 164 | ₱278K   │   │
│ │ 2 | U85SHE     | HP 5y MWS   | 164 | ₱8,453  │   │
│ └───────────────────────────────────────────────┘   │
│                                                     │
│ ┌─── Approval History ──────────────────────────┐   │
│ │ Level 1: ✓ Approved by Cecil (Supervisor)     │   │
│ │ Level 2: ✓ Approved by Carmen (SM)            │   │
│ │ Level 3: ● Pending — Accounting Supervisor    │   │
│ └───────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 8. Email Notifications

| Event | Recipients | Subject Template |
|---|---|---|
| SO Submitted | Level 1 approver (Supervisor) | `[CRM] Sales Order {SO#} pending your approval` |
| Level Approved | Next level approver | `[CRM] Sales Order {SO#} advanced to your queue ({Level Name})` |
| SO Fully Approved | Salesperson + Customer contact | `[CRM] Sales Order {SO#} approved — proceeding to fulfillment` |
| SO Rejected | Salesperson | `[CRM] Sales Order {SO#} rejected by {Approver} at {Level}` |
| SO Returned | Salesperson | `[CRM] Sales Order {SO#} returned for correction by {Approver}` |
| PO Issued | Salesperson + Warehouse | `[CRM] Purchase Order issued for {SO#} — expected delivery {date}` |
| SO Fulfilled | Salesperson + Customer | `[CRM] Sales Order {SO#} fulfilled — delivery complete` |

---

## 9. Role-Based Access Matrix

| Action | Salesperson | Supervisor | SM/AVP | Accounting | GM | Warehouse | Purchasing | Admin |
|---|---|---|---|---|---|---|---|---|
| Create SO | ✅ | — | — | — | — | — | — | ✅ |
| Edit SO (draft) | ✅ | — | — | — | — | — | — | ✅ |
| Submit SO | ✅ | — | — | — | — | — | — | ✅ |
| View SO (own/team) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Approve at Level 1 | — | ✅ | — | — | — | — | — | — |
| Approve at Level 2 | — | — | ✅ | — | — | — | — | — |
| Approve at Level 3 | — | — | — | ✅ | — | — | — | — |
| Approve at Level 4 | — | — | — | — | ✅ | — | — | — |
| Approve at Level 5 | — | — | — | — | — | ✅ | — | — |
| Approve at Level 6 | — | — | — | — | — | — | ✅ | — |
| Enter Supplier PO | — | — | — | — | — | — | ✅ | ✅ |
| Mark Fulfilled | — | — | — | — | — | ✅ | — | ✅ |
| Cancel SO | — | — | — | — | ✅ | — | — | ✅ |
| View PDF | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 10. PDF Generation

The Sales Order PDF is a formal internal document (NOT sent to the customer — the Proposal PDF is the customer-facing document).

### PDF Layout

```
┌─────────────────────────────────────────┐
│       MICRO IMAGE INTERNATIONAL CORP.    │
│              SALES ORDER                 │
├─────────────────────────────────────────┤
│ SO#: SO-MCB-2026-0001                   │
│ Date: August 8, 2026                    │
│ Source Proposal: MCB-2026-0002          │
│ Customer PO#: PO-2026-1234             │
├─────────────────────────────────────────┤
│ Customer: MEDICARE PLUS INC             │
│ Contact: Mr. Sebastian Lancceta         │
│ Delivery Address: ...                   │
├─────────────────────────────────────────┤
│         ITEMS TABLE                     │
│ Part# | Description | Qty | Price | Tot │
│ ...                                     │
│            Total: ₱47,001,908.00        │
├─────────────────────────────────────────┤
│ Terms: 30 days | Delivery: 5-7 days     │
├─────────────────────────────────────────┤
│       APPROVAL SIGNATURES               │
│ Supervisor: _________ Date: ___         │
│ SM/AVP: _________ Date: ___             │
│ Accounting: _________ Date: ___         │
│ GM: _________ Date: ___                 │
│ Warehouse: _________ Date: ___          │
│ Purchasing: _________ Date: ___         │
└─────────────────────────────────────────┘
```

---

## 11. Integration with Existing Modules

### Sales Proposals → Sales Order

- "Create Sales Order" button on Proposal Detail page (only when `proposal.status == 'accepted'`)
- One proposal can have multiple SOs (partial orders, split orders)
- SO stores `source_proposal` FK for traceability

### Sales Funnel → Sales Order

- When SO reaches `approved` status → auto-update funnel entry `deal_outcome = 'won'`
- Funnel entry should link to the SO: add `sales_order` FK to SalesFunnel model (nullable)

### Sales Monitoring

- SO creation logged as `SalesActivity` with type "Sales Order Created"
- Each approval step logged for audit
- Points awarded via Gamification

### Dashboard Integration

- Salesperson home dashboard: "My Pending Sales Orders" widget
- Supervisor/SM dashboard: "SO Approvals Pending" badge count
- Executive dashboard: SO pipeline value summary

### Navbar Integration

- Add "Orders" icon to the navigation bar (between Proposals and Monitoring icons)
- Badge count for pending approvals (similar to proposal approvals)

---

## 12. New User Roles Required

The following roles need to be added to `User.ROLE_CHOICES`:

| Role Code | Display Name | Department | Approval Level |
|---|---|---|---|
| `accounting_supervisor` | Accounting Supervisor | Finance | Level 3 |
| `warehouse_supervisor` | Warehouse Supervisor | Operations | Level 5 |
| `purchasing_supervisor` | Purchasing Supervisor | Supply Chain | Level 6 |

> **Note:** These job titles ALREADY exist in `User.JOB_TITLE_CHOICES` but are NOT in `ROLE_CHOICES`. They need to be added to `ROLE_CHOICES` for the approval chain to resolve them.

### Alternative: Role-Based Assignment Table

Instead of hardcoding roles, create a `SalesOrderApprovalConfig` model:

```python
class SalesOrderApprovalConfig(models.Model):
    level = models.PositiveIntegerField(unique=True)  # 1-6
    level_name = models.CharField(max_length=50)
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_required = models.BooleanField(default=True)
    min_amount_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
```

This allows admin to configure WHO approves at each level without code changes.

---

## 13. Implementation Phases

### Phase 1 — Core (8–10 days)

| # | Task | Estimate |
|---|---|---|
| 1 | Create `sales_orders` Django app | 0.5 day |
| 2 | Define models: SalesOrder, SalesOrderItem, SalesOrderApprovalStep, SalesOrderChangeLog | 1 day |
| 3 | Add new roles to User.ROLE_CHOICES + migration | 0.5 day |
| 4 | Create SalesOrderApprovalConfig model for admin-configurable chain | 0.5 day |
| 5 | Build approval chain resolution logic (6-level with conditions) | 1 day |
| 6 | Create SO from Proposal view (copy items, terms, customer) | 1 day |
| 7 | SO List view (role-scoped) + SO Detail view | 1 day |
| 8 | Approval Inbox view + approve/reject/return actions | 1.5 days |
| 9 | Email notifications on state changes | 1 day |
| 10 | Register URLs, add to INSTALLED_APPS, navbar link | 0.5 day |

### Phase 2 — PDF & Polish (5–7 days)

| # | Task | Estimate |
|---|---|---|
| 11 | SO PDF generation (internal document with signature blocks) | 1.5 days |
| 12 | Edit SO form (only in draft/returned state) | 1 day |
| 13 | Supplier PO entry form (Purchasing fills after approval) | 0.5 day |
| 14 | Fulfillment marking (Warehouse confirms delivery) | 0.5 day |
| 15 | Dashboard widgets (pending approvals, SO pipeline) | 1 day |
| 16 | Context processor for SO approval badge in navbar | 0.5 day |
| 17 | Gamification integration (points for SO creation/approval) | 0.5 day |
| 18 | Sales Funnel auto-update on SO approval | 0.5 day |

### Phase 3 — Advanced (3–5 days)

| # | Task | Estimate |
|---|---|---|
| 19 | SO Change Log detail display (audit trail) | 1 day |
| 20 | SO Reporting: monthly volume, approval turnaround time | 1 day |
| 21 | REST API endpoints for Android app | 1 day |
| 22 | Export SO list to Excel | 0.5 day |
| 23 | Partial fulfillment tracking (item-level delivery status) | 1 day |

---

## 14. Files to Create / Modify

### New Files (sales_orders app)

| File | Purpose |
|---|---|
| `sales_orders/__init__.py` | App package |
| `sales_orders/apps.py` | AppConfig |
| `sales_orders/models.py` | SalesOrder, SalesOrderItem, SalesOrderApprovalStep, SalesOrderChangeLog, SalesOrderApprovalConfig |
| `sales_orders/forms.py` | SalesOrderForm, SalesOrderItemFormSet |
| `sales_orders/views.py` | List, detail, create, edit, approve, reject, return, fulfill, PDF |
| `sales_orders/urls.py` | All SO URL patterns |
| `sales_orders/admin.py` | Admin registration |
| `sales_orders/signals.py` | Email notifications on state changes |
| `sales_orders/context_processors.py` | Navbar badge count for pending approvals |
| `sales_orders/migrations/0001_initial.py` | Auto-generated |
| `templates/sales_orders/order_list.html` | SO list page |
| `templates/sales_orders/order_detail.html` | SO detail with progress bar |
| `templates/sales_orders/order_form.html` | Create/Edit SO |
| `templates/sales_orders/approval_inbox.html` | Approval queue |
| `templates/sales_orders/approve_form.html` | Approve/Reject/Return modal |

### Modified Files (existing apps)

| File | Change |
|---|---|
| `crm_project/settings.py` | Add `'sales_orders'` to INSTALLED_APPS, add context processor |
| `crm_project/urls.py` | Add `path('orders/', include('sales_orders.urls'))` |
| `users/models.py` | Add 3 new roles to ROLE_CHOICES |
| `sales_proposals/models.py` | (No change — SO references Proposal via FK) |
| `sales_funnel/models.py` | Add optional `sales_order` FK |
| `templates/sales_proposals/proposal_detail.html` | Add "Create Sales Order" button |
| `templates/base.html` | Add "Orders" nav icon with approval badge |
| `templates/core/home.html` | Add "Pending SO Approvals" widget for approver roles |

---

## 15. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| New roles not assigned to users | Approval chain breaks (no approver found) | Medium | Admin config model allows manual approver assignment per level; validation on SO submit warns if chain is incomplete |
| Approval bottleneck (approver absent) | SO stuck in queue indefinitely | High | Add "delegate" feature: approver can assign a backup. Admin can override/skip levels. |
| SO amount changes after partial approval | Confusion about what was approved | Medium | If SO is edited after return, ALL approvals restart from Level 1 |
| Multiple SOs from same Proposal | Over-ordering duplicate items | Low | Warning on SO creation if proposal already has an active SO. Allow override. |
| Warehouse marks "Out of Stock" | Order can't proceed | Medium | Warehouse can mark "On Order from Supplier" and Purchasing proceeds. SO doesn't get stuck. |
| GM level not always needed | Unnecessary delay for small orders | Low | Configurable threshold (default ₱500K). Below threshold → Level 4 auto-skipped. |
| Accounting supervisor role doesn't exist | Level 3 has no approver | High (Day 1) | Must create the role and assign user BEFORE feature goes live |

---

## 16. Acceptance Criteria

### Must-Have (Phase 1)

- [ ] Salesperson can create a Sales Order from an accepted Proposal
- [ ] SO auto-numbers: `SO-{INITIALS}-{YEAR}-{SEQ}`
- [ ] Items, terms, and customer data copied from Proposal
- [ ] Salesperson can edit SO in draft/returned states only
- [ ] Submit button initiates 6-level approval chain
- [ ] Each approver sees the SO in their approval inbox
- [ ] Approver can Approve / Reject / Return for Correction
- [ ] Reject stops workflow; Return sends back to salesperson
- [ ] Email notification sent on each state change
- [ ] Full audit trail (who approved, when, with comment)
- [ ] Progress bar shows current approval level visually
- [ ] SO List view scoped by user role (same pattern as proposals)
- [ ] Admin can configure approvers per level via Django admin

### Should-Have (Phase 2)

- [ ] PDF generation for internal SO document
- [ ] Dashboard widget showing pending approvals count
- [ ] Navbar badge for pending SO approvals
- [ ] Supplier PO entry by Purchasing Supervisor
- [ ] Fulfillment confirmation by Warehouse Supervisor
- [ ] Funnel auto-updates to 'won' on full approval
- [ ] Gamification points for SO creation and approval

### Nice-to-Have (Phase 3)

- [ ] REST API for Android app
- [ ] Excel export of SO list
- [ ] Reporting: average approval turnaround per level
- [ ] Partial fulfillment at item level
- [ ] Delegate/backup approver assignment

---

## 17. Decisions Required from Management

1. **Approval:** Proceed with implementation? (Y/N)
2. **GM Threshold:** What order value requires GM approval? (Suggested: ₱500,000)
3. **New Roles:** Approve adding `accounting_supervisor`, `warehouse_supervisor`, `purchasing_supervisor` to system roles?
4. **Who holds these roles?** Please designate specific users for:
   - Accounting Supervisor (Level 3)
   - Warehouse Supervisor (Level 5)
   - Purchasing Supervisor (Level 6)
5. **Delegation:** Should an absent approver be able to delegate to a backup?
6. **Multiple SOs per Proposal:** Allow splitting one proposal into multiple orders?
7. **SO visible to customer?** Or internal-only document?
8. **Phase scope:** Implement Phase 1 only, or Phase 1+2 together?
9. **Integration:** Should "Create Sales Order" appear only for `accepted` proposals, or also for `sent` proposals?

---

## Appendix A: SO Number Format

```
SO-{INITIALS}-{YEAR}-{SEQUENCE}
```

Example: `SO-MCB-2026-0001`

- INITIALS = 3-letter initials of the salesperson (same logic as Proposal numbering)
- YEAR = current year
- SEQUENCE = auto-incrementing per year (4 digits, zero-padded)

---

## Appendix B: Comparison with Proposal Approval

| Aspect | Proposal Approval | Sales Order Approval |
|---|---|---|
| Levels | 1–3 (Supervisor → ASM → AVP) | 1–6 (multi-department) |
| Triggered by | Amount ≥ ₱500K | Always (every SO requires approval) |
| Return for correction | Not supported | ✅ Supported |
| Reject | Stops chain | Stops chain |
| Conditional levels | All based on amount | Level 4 (GM) conditional on amount |
| Cross-department | Sales only | Sales + Accounting + Executive + Operations |
| Email notifications | Approver only | All stakeholders at each transition |
| Audit trail | ProposalChangeLog | SalesOrderChangeLog (richer) |
| PDF | Customer-facing | Internal document |

---

*Document prepared by the Development Team — Micro Image International Corp. — August 2026*  
*Pending management review and approval before implementation begins.*
