# Teams App — How It Works & Role Permissions

This document explains the `teams` app and, more importantly, **what the AVP, SM
(Sales Manager), ASM, and Supervisor roles can see and do** across the three
areas that generate the most questions: **Customers**, **Sales Funnel**, and
**Sales Proposals**.

> Scope note: everything below reflects the code as it exists today, with file
> and line references so it can be re-verified. A key thing to understand up
> front: the `teams` app only *defines the hierarchy* (who belongs where). The
> actual permission enforcement for customers/funnel/proposals lives in **those**
> apps' views and querysets — the teams structure is what they read to decide
> "whose records can this manager see?"

---

## 1. Quick overview

- **What it manages:** the org hierarchy (`Team` → `Group` → `TeamMembership`),
  plus targets/quotas/commitments used by sales monitoring.
- **The chain of visibility** everywhere in the system is:
  `Customer.salesperson` / `Proposal.created_by` / `SalesFunnel.salesperson`
  → `TeamMembership.group` → `Group.team`. Managers are resolved back through
  this chain to figure out which salespeople they oversee.
- **Key files:**
  | File | Responsibility |
  |------|----------------|
  | `teams/models.py` | `Team`, `Group`, `TeamMembership`, and target/quota/commitment models |
  | `teams/views.py` | Team/Group management screens (list, create, edit, members, quotas, commitments) |
  | `teams/forms.py` | Team/Group forms and the SM/member assignment UI |
  | `customers/permissions.py` | **Central** role-scoping helpers reused across the app |
  | `customers/views.py` | Customer list/detail/edit scoping + create-request approvals |
  | `sales_funnel/views.py` | Funnel dashboard/entry scoping |
  | `sales_proposals/views.py` + `models.py` | Proposal list scoping + the approval chain |

---

## 2. The hierarchy models (`teams/models.py`)

### `Team`
- `avp` → `User` (FK, `related_name='managed_teams'`), limited to roles
  `avp/vp/gm/president`. A team must have **either** an AVP **or** a Technical
  Manager (`clean()`).
- `asm` → `User` (FK, `related_name='asm_teams'`), role `asm`.
- `tech_manager` → `User` (FK, `related_name='tsg_managed_teams'`), for Technical
  Sales Groups (TSG).

### `Group` (belongs to one `Team`)
- `group_type`: `regular` (has a supervisor) or `tsg` (managed by the team's
  Technical Manager; no supervisor).
- `supervisor` → `User` (FK, `related_name='managed_groups'`), roles
  `supervisor` **or** `asm` (an ASM can act as a supervisor).
- `sm_managers` → `User` (**M2M**, `related_name='sm_groups'`), roles `sm`/`asm`.
  This is how a Sales Manager is scoped to **specific groups** rather than a whole
  team. One SM can oversee several groups **within a team**.
- `teamlead` → `User` (FK, `related_name='led_groups'`), role `teamlead`.
- **`requires_sm_approval`** (bool, default `False`): controls the proposal
  approval chain. `False` → Supervisor → AVP. `True` → Supervisor → SM → AVP.
  This deliberately **separates visibility from approval authority**: an SM
  assigned via `sm_managers` can always *see* the group's data, but is only
  inserted into the *approval* chain when this flag is on.

### `TeamMembership`
- `user` (OneToOne) ↔ `group`. A salesperson can be in **only one group**.
- Carries the salesperson's `quota`.

### Other models (targets & quotas)
`SupervisorCommitment` (+ `SupervisorCommitmentLog`), `PersonalContribution`,
`AsmPersonalTarget`, `RoleMonthlyQuota`, and `CompanyAnnualTarget` (+ log). These
feed the sales-monitoring dashboards and are edited through the teams views in §3.

### The reverse-relation cheat sheet (used everywhere)
| Role | How they're linked | Reverse accessor |
|------|--------------------|------------------|
| AVP | `Team.avp` | `user.managed_teams` |
| ASM | `Team.asm` | `user.asm_teams` |
| SM | `Group.sm_managers` (M2M) | `user.sm_groups` |
| Supervisor | `Group.supervisor` | `user.managed_groups` |
| Teamlead | `Group.teamlead` | `user.led_groups` |
| Salesperson | `TeamMembership.user` | `user.team_membership` |

---

## 3. Managing teams & groups (`teams/views.py`)

Access is gated by three helpers:

- `can_view_teams` — `admin, president, gm, vp, avp, asm, sm, supervisor, techmgr, asst_techmgr`.
- `can_manage_teams` (create/edit **teams**) — `admin, president, gm, vp` **only**.
  So **AVP/SM/Supervisor cannot create teams.**
- `can_manage_groups` (create/edit **groups**, members, quotas, commitments) —
  the full manager set including `avp, asm, sm, supervisor`.

Within `can_manage_groups` screens, each view re-checks **scope** so a manager
only touches their own slice (raising `Http404` otherwise):

- **AVP:** only groups whose `group.team.avp == self` (via `Team.objects.filter(avp=user)`).
- **ASM:** only groups whose `team in user.asm_teams`.
- **SM:** only groups in `user.sm_groups` (their explicitly assigned groups).
- **Supervisor:** only their own `group.supervisor == self` groups.

`group_list`, `team_groups`, `group_members`, `edit_group`, `update_member_quota`,
`update_supervisor_commitment`, `commitment_history`, and
`update_personal_contribution` all apply this same per-role scoping. `quota_management`
is **AVP-only** (returns 403 for anyone else) and shows the AVP's teams → groups →
member quotas. `update_company_target` is `gm/vp/admin` only.

---

## 4. Role permissions — Customers

**Central logic:** `customers/permissions.py`. The scoping helpers here are the
source of truth and are reused by the customer views.

Key helper — `get_user_team_ids(user)`:
- AVP → `user.managed_teams`
- ASM → `user.asm_teams`
- SM → teams derived from `user.sm_groups` (group-scoped, then their teams)
- Supervisor → teams of `Group.objects.filter(supervisor=user)`

### 4.1 Who can SEE which customers — `visible_customers_queryset(user)`

| Role | Customers visible |
|------|-------------------|
| Exec (`admin/president/gm/vp/marketing`) | **All** customers |
| Salesperson | Only their own (`salesperson=user`) |
| **Supervisor** | Customers of salespeople in their `managed_groups`, plus their own |
| **AVP** | Customers of all **team-scoped users** across `managed_teams` (via `get_team_scoped_users`, roles limited to `salesperson/supervisor/asm/sm/avp`) |
| **ASM** | Same pattern as AVP but scoped to `asm_teams` |
| **SM** | Customers of salespeople in their **assigned groups only** (`sm_groups`), plus those groups' supervisors, plus themselves |

A manager with **no resolvable scope** (e.g. an AVP with no team, an SM with no
assigned groups) sees **nothing** — the queryset returns `Customer.objects.none()`
rather than falling through to "see all." This is the safe default.

### 4.2 Who can EDIT a customer — `can_edit_customer(user, customer)`

- Execs: always.
- The **assigned salesperson**: always (their own record).
- Otherwise the manager must (a) have the customer's salesperson within their
  team/group scope **and** (b) satisfy `can_manage_role(actor_role, target_role)`:
  - AVP can manage `asm, sm, supervisor, salesperson`.
  - SM can manage `asm, supervisor, salesperson`.
  - ASM can manage `supervisor, salesperson`.
  - Supervisor can manage `salesperson` only.
  - No role can manage a peer of the **same** role.

In `customers/views.py`, `can_manage_customers` (transfer/reassign, etc.) is
granted to `admin, gm, vp, marketing, avp, asm, sm, supervisor`. The **Team/Group
granular search filters** on the customer list are shown to `admin, gm, vp,
president, avp` (AVP's team dropdown is limited to their own teams via
`get_user_team_ids`).

### 4.3 New-customer create-request approvals (AVP focus)

The customer create-request workflow has **three tiers of involvement**
(`customers/permissions.py`):

- **Global reviewers** (`admin, gm, vp, marketing`): see **all** pending requests
  and may approve/reject.
- **Approvers** = global reviewers **+ AVP**: may approve/reject **within scope**.
  The **AVP can only approve requests raised by users within their own team(s)**
  (`_managed_requester_ids` → `get_team_scoped_users(get_user_team_ids(avp))`).
- **Watchers** (`supervisor, sm, asm`): may **see** requests within their scope for
  awareness, but **cannot** approve/reject — the decision stays with the AVP/exec.

So on the notification bell / pending queue (`pending_requests_for_reviewer`):
an **AVP of Team A sees only Team A's requests**; an AVP of Team B sees only Team
B's — exactly matching their customer data scope. Supervisors/SM/ASM see their
narrower slice but the buttons to decide are withheld.

---

## 5. Role permissions — Sales Funnel (`sales_funnel/views.py`)

Access gate `can_access_funnel` includes `salesperson, supervisor, teamlead, asm,
sm, avp` (plus execs/admin). The dashboard queryset scoping:

| Role | Funnel entries visible |
|------|------------------------|
| Salesperson | Own entries only |
| **Supervisor** | Entries of salespeople in `Group.objects.filter(supervisor=user)`, plus own |
| **ASM** | Entries of members **and** supervisors of all groups in `user.asm_teams`, plus own |
| **SM** | Entries of members + supervisors of their **assigned groups** (`user.sm_groups`) only, plus own |
| **AVP** | Entries of members + supervisors + team ASMs across `Team.objects.filter(avp=user)`, plus own |
| Exec/Admin | All |

The same scoping is repeated for the "closed deals" section of the dashboard. Note
the funnel builds its `visible_ids` inline in the view (it does **not** call
`customers/permissions.py`), but the resulting scope mirrors the customer scope.

There is also an AVP-notes email notification: when an AVP edits the notes on a
funnel entry, the AE (salesperson) and that AE's **group supervisor** are emailed
(`_send_avp_notes_notification`).

---

## 6. Role permissions — Sales Proposals (`sales_proposals/views.py` + `models.py`)

### 6.1 Who can SEE which proposals (list scoping)

Scoping is by `Proposal.created_by`:

| Role | Proposals visible |
|------|-------------------|
| Salesperson | Own (`created_by=user`) |
| **Supervisor** | Members of `managed_groups` + self |
| **AVP** | For each team in `managed_teams`: group members + group supervisors + each group's `sm_managers` + team `asm` + self |
| **ASM** | All groups in `asm_teams`: members + supervisors + self |
| **SM** | Members + supervisors of **assigned groups** (`sm_groups`) only + self |
| Teamlead | Members of `led_groups` + self |
| Exec/Admin (`admin/vp/gm/...`) | All |

The **Team/Group granular filter** dropdowns on the proposal list are shown to
`admin, gm, vp, president, avp` (AVP limited to their own `managed_teams`). The
proposal list also has a **format filter** (single vs multi-option) and resolves a
"team name" per proposal, with fallbacks that resolve an SM via `sm_groups`, an ASM
via `asm_teams`, and a supervisor via `managed_groups`.

### 6.2 The approval chain — who approves what (`Proposal.get_approval_chain`)

Approval is required when the binding PHP total crosses the threshold
(default **₱500,000**, or the matching active `ProposalApprovalTier`). The chain is
built by resolving the **creator's group** (with fallbacks for SM via `sm_groups`,
ASM via `Team.asm`, supervisor via `managed_groups`), then assembling approvers:

1. **Supervisor** — `group.get_manager()`.
2. **SM/ASM** — **only if `group.requires_sm_approval` is True.** When on, the
   group's `sm_managers.first()` is used (falling back to the team ASM). When off,
   this level is skipped entirely. *(This is the visibility-vs-authority split: an
   SM always sees the group's proposals, but only approves when the flag is set.)*
3. **AVP** — `group.team.avp`.

Two important guards:

- **Rank guard (`_approver_outranks_creator`):** an approver is only added if their
  role level is **strictly above** the creator's (`ROLE_LEVEL`: salesperson 1 …
  supervisor 3 … asm/sm 4 … avp 5 … gm 6 …). So a proposal *created by* a
  supervisor skips the supervisor level; one created by an AVP won't route to a
  peer AVP; etc.
- **Escalation:** if approval is required but every lower approver was skipped
  (creator outranks them), it escalates to the AVP/GM.

`ensure_approval_chain()` materializes this into ordered `ProposalApprovalStep`
rows and is called on save (after `calculate_totals`).

### 6.3 The approval inbox & notification bell (team-scoped)

Both the **inbox** (`approvals_inbox`) and the **navbar bell**
(`context_processors.proposal_approval_notifications`) show a manager **only the
steps assigned to them that are the current pending level**:

```
ProposalApprovalStep.objects
    .filter(approver=request.user, status='pending')
    .annotate(current_pending_level=Min(level, where step is pending))
    .filter(level == current_pending_level)
```

Because each approver is placed on the chain by team/group resolution, an **AVP of
Team A only receives approval requests from Team A members**, and an AVP of Team B
only from Team B — the notification scope follows the chain, not a global queue.
Approval **order is enforced**: `approve_proposal`/`reject_proposal` refuse to act
if an earlier level is still pending ("Approval order is enforced. Please wait for
Level N…"). Approving the last step marks the proposal approved and emails the
creator; any rejection sets `rejected` and emails the creator with the reason.

**Approval-tier configuration** (the amount thresholds/chains) is exec-only:
`_is_exec` = `admin, president, vp, avp, gm`.

---

## 7. Permissions matrix (at a glance)

Scope key: **Own** = only self; **Group(s)** = their assigned/managed group(s);
**Team(s)** = their whole team(s); **All** = everything.

| Area / Action | Supervisor | SM | ASM | AVP |
|---|---|---|---|---|
| **Customers — view** | Group(s) + own | Assigned groups + own | Team(s) + own | Team(s) + own |
| **Customers — edit** | Salespeople in group(s) | asm/sup/sales in scope | sup/sales in scope | asm/sm/sup/sales in scope |
| **Customer create-request** | See (watcher) | See (watcher) | See (watcher) | **Approve/reject (own team)** |
| **Funnel — view** | Group(s) + own | Assigned groups + own | Team(s) + own | Team(s) + own |
| **Proposals — view** | managed_groups + own | Assigned groups + own | asm_teams + own | managed_teams + own |
| **Proposal approval** | Level 1 (if outranks creator) | Only if `requires_sm_approval` | Only if `requires_sm_approval` | Final team-level approver |
| **Create teams** | ✗ | ✗ | ✗ | ✗ (exec only) |
| **Create/edit groups, quotas, commitments** | Own groups | Assigned groups | Own teams' groups | Own teams' groups |
| **Team/Group search filters** | ✗ | ✗ | ✗ | ✓ (own teams) |
| **Approval-tier config** | ✗ | ✗ | ✗ | ✓ (exec-tier) |

---

## 8. Notes, edge cases & gotchas

- **Visibility ≠ approval authority for SM/ASM.** `sm_managers` grants *sight* of a
  group's customers/funnel/proposals; being in the *approval chain* additionally
  requires `Group.requires_sm_approval=True`. If a manager expects to approve but
  isn't getting requests, check that flag first.
- **No-scope = no data (fail safe).** An AVP with no `managed_teams`, or an SM with
  no `sm_groups`, sees an **empty** set — not everything. This is intentional.
- **Two scoping code paths.** Customers/proposals lean on
  `customers/permissions.py`; the sales funnel re-implements equivalent inline
  filters. They mirror each other today — if you change one, review the other so
  they don't drift.
- **SM vs ASM linkage differs.** ASM is linked at the **team** level (`Team.asm`),
  SM at the **group** level (`Group.sm_managers`). That's why an ASM sees a whole
  team while an SM sees only their assigned groups, even though both display as
  "Sales Manager."
- **ASM can double as a supervisor.** `Group.supervisor` accepts `asm`, so an ASM
  may act as a group's supervisor until a permanent one is hired.
