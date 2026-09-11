# Rejected Proposal Handling — Current Behavior & Proposed Options

**System:** MICRO IMAGE CRM — Sales Proposals
**Prepared for:** Management / Sales Ops review & approval
**Status:** For decision. Sections 1–3 describe **current, verified behavior** (no code
changed). Section 4 proposes optional improvements that require approval before any change.

---

## 1. Question

*When a proposal is rejected by an approver (Supervisor / SM / AVP), what happens to it?
Can the salesperson edit it again, and does editing reset the approval process?*

---

## 2. Current Behavior (as built today)

**Yes — a rejected proposal can be edited, and saving the edit automatically restarts
the approval workflow.** Nothing about rejection locks or deletes the proposal.

### Step-by-step

1. **Rejection.** An approver clicks Reject (optionally with a reason). The system:
   - Marks that approval step `rejected` and stores the reason as the step comment.
   - Sets the proposal's `approval_status = 'rejected'`.
   - Emails the salesperson the rejection notice **including the reason** (see
     `SALES_PROPOSALS_DOCUMENTATION.md` §10a).
   - Does **not** lock, hide, delete, or freeze the proposal.

2. **The proposal stays editable.** The **Edit** button remains available on the proposal
   detail page, and there is no status check blocking edits of a rejected proposal. The
   salesperson can open and revise it normally.

3. **Saving the edit resets approval automatically.** On save, the system recalculates
   totals and rebuilds the approval chain:
   - If the proposal still needs approval (PHP total ≥ ₱500,000), `approval_status` flips
     back to **pending**, the **old approval steps (including the rejected one) are deleted**,
     a **fresh approval chain is created from Level 1**, `approval_version` is incremented
     (audit trail), and the **first approver is emailed** the "Approval Needed" notice.
   - The workflow effectively starts clean — no stale rejection remains attached.

4. **Email is still blocked until re-approved.** A proposal that requires approval cannot
   be emailed to the customer until it reaches `approved` again — this guard is unchanged.

### In short

| Action after rejection | Result |
|---|---|
| Salesperson opens the rejected proposal | Allowed — fully editable |
| Salesperson edits & saves (total still ≥ ₱500K) | Approval **resets to pending**, fresh chain from Level 1, first approver emailed |
| Approver re-reviews | Normal approve/reject cycle again |

---

## 3. Edge Cases & Gaps (verified, for awareness)

These are the reasons this topic is worth a management decision rather than assuming the
current behavior is final:

### 3.1 Editing below the approval threshold bypasses approval
Approval is triggered purely by the **amount** (≥ ₱500,000), not by "this was rejected."
If a salesperson takes a **rejected ₱600,000** proposal and trims it **below ₱500,000**,
saving it sets `approval_required = False` and `approval_status = 'not_required'` — the
proposal can then be **emailed to the customer with no approval at all**.
- This may be acceptable (small proposals legitimately don't need approval), **or** it may
  be an unwanted loophole (a rejected deal being reshaped under the threshold and sent
  without oversight). **This needs a policy decision.**

### 3.2 No clear on-screen "rejected — please revise" cue
The rejection reason is visible inside the approval-steps list on the detail page, but
there is **no prominent banner or call-to-action** telling the salesperson their proposal
was rejected and what to do next. Easy to miss (they mainly rely on the email).

### 3.3 Rejection is immediate and final for that cycle
Any single approver in the chain can reject, which **ends the whole cycle immediately**
(remaining approvers are not consulted). There is no "send back for minor revision"
distinct from a hard reject. This is by design, but worth confirming it matches how
management wants the workflow to behave.

### 3.4 History is preserved
Each reset increments `approval_version`, and the `ProposalChangeLog` records edits, so
there **is** an audit trail of the reject → edit → resubmit cycle. Rejection reasons from
prior cycles live on the (now-deleted) step comments — they are shown at the time but not
retained after the chain is rebuilt.

---

## 4. Proposed Options (require approval before implementing)

The core behavior (edit resets approval) is sound. The following are **optional
enhancements** to close the gaps above. None are implemented yet.

### Option A — Prevent the "trim under threshold to bypass approval" loophole *(recommended)*
If a proposal was **previously rejected** and is edited to fall below ₱500,000, still
require one level of approval (or keep it pending) rather than auto-clearing to
`not_required`. Ensures a rejected deal can't be quietly reshaped and sent without review.
- **Effort:** ~0.5 day. **Risk:** low (adds a guard in `calculate_totals`/`ensure_approval_chain`).

### Option B — Add a visible "Rejected — revise & resubmit" banner *(recommended, low effort)*
Show a clear red banner on the detail page when `approval_status = 'rejected'`, displaying
the latest rejection reason and an **Edit to Resubmit** button. Improves clarity for the
salesperson beyond the email.
- **Effort:** ~0.5 day. **Risk:** none (template-only).

### Option C — Preserve rejection history across resubmissions
Keep a lightweight record of each rejection (approver, reason, date, `approval_version`) so
managers can see how many times a proposal was bounced and why, even after the chain is
rebuilt.
- **Effort:** ~1 day (small model or change-log entries). **Risk:** low.

### Option D — Distinguish "Reject" vs "Return for revision" *(optional, larger)*
Add a softer "return for revision" action (keeps the chain, asks for edits) separate from a
hard "reject" (kills the deal). Only if management wants two distinct outcomes.
- **Effort:** ~2 days. **Risk:** medium (workflow change).

### Do-nothing option
Keep current behavior as-is. It already allows edit + automatic reset; the only real
exposure is the sub-threshold bypass (3.1).

---

## 5. Recommendation

Adopt **Option A + Option B**: they are low-effort, low-risk, and together they (a) close
the approval-bypass loophole and (b) make the resubmission path obvious to salespeople.
Options C and D can be revisited later if management wants richer rejection history or a
two-tier reject/return workflow.

---

## 6. Approval

| Role | Name | Decision (Approve / Revise / Reject) | Date |
|------|------|--------------------------------------|------|
| Sales Operations | | | |
| IT / Development Lead | | | |
| Management | | | |

---

### Appendix — Technical references (for IT)
- Rejection: `reject_proposal` in `sales_proposals/views.py` (sets step + `approval_status='rejected'`).
- Reset on edit: `Proposal.calculate_totals()` (re-flips `approval_status` to `pending` when
  `approval_required` and status in `not_required/approved/rejected`) then
  `Proposal.ensure_approval_chain()` (deletes decided steps via `has_decisions`, rebuilds chain,
  bumps `approval_version`).
- Edit entry points: `proposal_update` and `multi_option_proposal_update` (no rejected-status guard).
- Email guard: customer send blocked while `approval_required and approval_status != 'approved'`.
