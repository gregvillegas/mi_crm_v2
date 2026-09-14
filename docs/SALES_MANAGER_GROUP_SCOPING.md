# Sales Manager (ASM) Group Scoping — How It Works & How to Assign Groups

**System:** MICRO IMAGE CRM
**Applies to:** Sales Managers (technical role `asm`), across the **Teams**,
**Sales Monitoring**, and **Sales Proposals** areas.

> Short version: A Sales Manager now sees **only the groups they handle** — not the
> whole team. Assigning a Sales Manager to a different/additional group is a
> **data change done in the UI** (the Edit Group screen). **No code edit or
> deployment is needed.**

---

## 1. Background — what changed and why

A "Sales Manager" in the app has the technical role **`asm`**. Previously, every
ASM was scoped by their **whole team** (`Team.asm` → all groups in that team), so:

- On the **Groups** page, Team B's Sales Manager (`scereno`) saw all four Team B
  groups (CSG-E, CSG-F, CSG-G, CSG-H) instead of just the two she handles.
- On the **Sales Proposals** dashboard, she saw every Team B salesperson and all
  Team B proposals.
- The **Sales Monitoring** dashboard behaved the same way.

The requirement: a Sales Manager should see **only the groups they handle**:

| Sales Manager | Team | Should see groups |
|---|---|---|
| `csenador` | TEAM A | CSG-C, CSG-D |
| `scereno` | TEAM B | CSG-G, CSG-H |

The **AVP** still sees **all** of their team's groups (unchanged).

---

## 2. The mechanism — assignment lives in the data, not the code

The link between a Sales Manager and the groups they handle is the
**`Group.sm_managers`** field (a many-to-many). Its reverse accessor on the user
is **`user.sm_groups`**.

- A Sales Manager assigned to a group via `sm_managers` → is scoped to that group.
- This is editable in the UI on the **Edit Group** screen under the
  **"Sales Manager Assignment"** checkboxes (`teams/forms.py` → `GroupEditForm`,
  field `sm_managers`, limited to roles `sm`/`asm`).

Because assignment is data, adding/removing a group for a Sales Manager is a
point-and-click operation — see §5.

### The single source of truth: `asm_scoped_groups()`

To avoid duplicating logic in ~15 places, all ASM scoping goes through one helper
in **`teams/models.py`**:

```python
def asm_scoped_groups(user):
    """Groups an ASM is scoped to (Option A)."""
    assigned = user.sm_groups.all()          # explicitly handled groups
    if assigned.exists():
        return assigned                       # -> only those groups
    return Group.objects.filter(team__in=user.asm_teams.all())  # fallback: whole team
```

**Option A behavior (chosen):**
- If the ASM **has** group assignments → they see **only those groups**.
- If the ASM has **no** assignments → they **fall back to the whole team**. This
  protects any ASM who genuinely oversees an entire team and hasn't been assigned
  to specific groups yet — nothing silently disappears.

---

## 3. What was changed (code)

All ASM branches were routed through `asm_scoped_groups()` (or the equivalent
group-level query). Summary by file:

| File | What changed |
|------|--------------|
| `teams/models.py` | **Added** the shared `asm_scoped_groups(user)` helper |
| `teams/migrations/0018_assign_asm_group_scope.py` | **Data migration**: assigned `csenador`→CSG-C/CSG-D and `scereno`→CSG-G/CSG-H (idempotent, reversible) |
| `teams/views.py` | ASM branches in `group_list`, `team_list`, `team_groups`, `group_members` (view + can-edit), `edit_group`, `update_member_quota`, `update_supervisor_commitment`, `commitment_history`, `update_personal_contribution` now use the helper |
| `sales_monitoring/views.py` | All ASM branches (dashboard + activity/report queries) use the helper |
| `sales_monitoring/forms.py` | Fixed an SM-branch bug that scoped by `asm_teams`; SM now uses `sm_groups`; ASM uses the helper |
| `sales_proposals/views.py` | ASM proposal-list scoping uses the helper; added a **Group filter** for ASM/SM limited to their own groups, with server-side validation of the selected group |
| `templates/sales_proposals/proposal_list.html` | Added an ASM/SM **Group-only** dropdown ("All My Groups" + their handled groups) |

### Sales Proposals dashboard specifics

- **Scoping:** an ASM sees proposals created by the members and supervisors of the
  groups they handle, plus their own. (The `sm` role already worked this way.)
- **Group filter (Option A):** ASM/SM get **only** a Group dropdown (no Team
  dropdown), populated **only** with the groups they handle. Executives and AVP
  keep both the Team and Group dropdowns as before.
- **Hardening:** the selected `?group=` value is validated against the manager's
  allowed set server-side, so a hand-typed group id cannot widen their view.

---

## 4. Verification performed

- `python manage.py check` — clean.
- Data migration `0018` applied; confirmed `sm_managers` rows:
  `csenador`→CSG-C, CSG-D and `scereno`→CSG-G, CSG-H.
- Rendered the real proposal-list view for both Sales Managers:
  - `scereno` — proposals limited to CSG-G/CSG-H (+ their supervisor + herself);
    Group dropdown = **CSG-G, CSG-H**.
  - `csenador` — proposals limited to CSG-C/CSG-D; Group dropdown = **CSG-C, CSG-D**.
- AVP visibility unchanged (still sees all of their team's groups).

---

## 5. Playbook — assigning another group to a Sales Manager (NO code)

Because scoping reads from `Group.sm_managers`, changing what a Sales Manager sees
is a **UI-only** operation. There is **nothing to hard-code and no deploy**.

### Option 1 — Edit Group screen (recommended, for most cases)

1. Log in as an Admin/GM/VP (or the AVP of the relevant team).
2. Go to **Teams → Groups**, open the group you want to assign (e.g. **CSG-F**).
3. Click **Edit**.
4. Under **"Sales Manager Assignment"**, tick the Sales Manager (e.g. `scereno`).
   One manager can be ticked on **multiple** groups within their team.
5. **Save.**

The Sales Manager immediately sees that group (its members, proposals, monitoring)
and it appears in their **Group filter** dropdown. To **unassign**, untick and save.

> Notes
> - Assignments are scoped **within a team** — a Sales Manager oversees groups in
>   their own team.
> - The **fallback rule** matters: if you remove **all** of a Sales Manager's group
>   assignments, they revert to seeing the **whole team** (Option A). To restrict a
>   Sales Manager to specific groups, keep at least one group assigned.
> - Assigning/removing groups changes **visibility**. Whether that manager also
>   sits in a proposal's **approval chain** is separate and controlled by the
>   group's **`requires_sm_approval`** flag (see the Teams doc).

### Option 2 — Django admin (bulk / quick edits)

1. Go to `/admin/` → **Teams → Groups** → open a group.
2. In the **Sales managers** field, add/remove the user(s).
3. Save. Same effect as Option 1.

### Option 3 — Data migration (only for scripted, repeatable rollouts)

Use this **only** when you need the assignment applied automatically across
environments (e.g. staging → production) rather than clicking the UI. Mirror the
existing, idempotent pattern in
`teams/migrations/0018_assign_asm_group_scope.py`:

```python
ASSIGNMENTS = {
    'scereno': ['CSG-G', 'CSG-H', 'CSG-F'],   # add CSG-F
}
# for each username/group: group.sm_managers.add(user)   # idempotent
# reverse: group.sm_managers.remove(user)
```

Match by **username + group name**, skip missing records, and provide a reverse
function so the migration is reversible. This is the same approach used for the
initial assignment.

### Which option to use

| Situation | Use |
|-----------|-----|
| Day-to-day reassignment by a manager/admin | **Option 1** (Edit Group) |
| One-off bulk fixups by an admin | **Option 2** (Django admin) |
| Repeatable change that must ship with a deploy | **Option 3** (data migration) |

---

## 6. FAQ / gotchas

- **"A new Sales Manager sees the whole team — is that a bug?"** No — that's the
  fallback. Assign them to specific groups (Option 1) to restrict them.
- **"I assigned a group but the manager still can't approve its proposals."**
  Visibility and approval authority are separate. Approval requires the group's
  **`requires_sm_approval`** flag; otherwise the chain is Supervisor → AVP.
- **"Does this affect the AVP?"** No. AVP scoping is unchanged — they see all
  groups in their team(s).
- **"Do I need to restart / redeploy after assigning a group?"** No. It takes
  effect on the manager's next page load.
- **Role vs job title:** these users' job title is "Sales Manager," but their
  technical **role is `asm`**. That's why the ASM code paths govern their scope.
