# Optional Items & the ₱500K Approval Threshold — Behavior & Options

**System:** MICRO IMAGE CRM — Sales Proposals
**Prepared for:** Management / Sales Ops review & approval
**Status:** For decision. Sections 1–3 describe **current, verified behavior** (no code
changed). Section 4 proposes options that require approval before any change.

---

## 1. Observation

A proposal quoting **₱684,000** showed **Approval: Not Required**, even though it is well
above the ₱500,000 approval threshold. The single line item on that proposal was flagged as
**Optional ("Option 1")**.

*Question: Why does using the "Optional item" checkbox cause a high-value proposal to skip
approval?*

---

## 2. Root Cause (verified in code)

Approval is triggered inside `Proposal.calculate_totals()`
(`sales_proposals/models.py`). The very first step **excludes optional items** from the
totals, and the approval threshold is then checked against that (optional-excluded) total:

```python
priced_items = self.items.filter(is_optional=False)      # optional items excluded
subtotal      = sum(item.amount for item in priced_items)
total_amount  = discounted_subtotal + tax
approval_total_php = total_amount                        # 0 if the only item is optional
approval_required  = (approval_total_php >= 500000)      # 0 >= 500000 → False
```

So when a line item is marked **Optional**:
- It is **not counted** in `subtotal` / `total_amount`.
- Therefore it is **not counted** toward `approval_total_php`.
- A proposal whose large item(s) are all optional has a binding total of **₱0**, so
  `approval_required` becomes **False** → "Not Required".

**This is a design consequence, not a threshold-math bug.** Optional items are intentionally
treated as "not yet committed," so they are excluded from binding totals *and* from the
approval trigger.

---

## 3. Why the System Was Built This Way (context)

The "optional item" concept is used consistently across the module:

- When any item is optional (`has_optional_items = True`), the PDF and detail view
  **hide the Grand Total** entirely — the interpretation being "there is no single binding
  total; the customer chooses."
- Two sets of totals exist deliberately:
  - `subtotal` / `total_amount` — **exclude** optional items. Used for the binding value
    **and** the approval threshold.
  - `quoted_subtotal` / `quoted_amount_php` — **include** optional items. Used for
    sales-funnel value and list displays (what the customer was shown).

The approval logic currently uses the **binding** total (`total_amount`), which is why
optional value does not trigger approval.

### The edge case that looks wrong
When the **only** item (or the largest item) is optional — as in the ₱684K example — the
binding total is ₱0, so a large quote reaches the customer with **no approval**. That is the
scenario management flagged.

---

## 4. Options (require approval before implementing)

### Option A — Trigger approval on the quoted value (includes optional items) *(recommended)*
Base the approval check on `quoted_amount_php` (which **includes** optional items) instead of
`total_amount`. Effect: **any proposal quoting ≥ ₱500,000 requires approval, regardless of
whether items are optional.**
- **Pro:** Matches the expectation that "if we're presenting ₱684K to a customer, an approver
  should see it."
- **Con:** More proposals will require approval (those relying on optional line items).
- **Effort:** ~0.5 day. **Risk:** low (one calculation change + re-test of the threshold).

### Option B — Trigger on the higher of the two totals
Use `max(total_amount_php, quoted_amount_php)`. Keeps the binding-total logic for normal
proposals but still catches large **optional-only** quotes.
- **Pro:** Least disruptive to existing non-optional proposals; closes the loophole.
- **Con:** Slightly more complex to explain.
- **Effort:** ~0.5 day. **Risk:** low.

### Option C — Leave as-is
Optional truly means non-committal, so no approval is required until the item is made
non-optional. The salesperson would need to un-check "Optional" (making it binding) before it
can be committed, at which point approval fires normally.
- **Pro:** No change; internally consistent.
- **Con:** The ₱684K-with-no-approval scenario remains possible.

---

## 5. Important Notes for the Decision

- **Whichever option is chosen, it only takes effect for proposals saved/edited afterward.**
  Existing proposals keep their current `approval_required` value until they are re-saved
  (which re-runs `calculate_totals()`). A one-time re-sync could be run if management wants
  existing proposals re-evaluated.
- **Multi-option proposals are unaffected by this specific issue** — they use a different
  calculation (`_calculate_multi_option_totals`, based on the highest option-group subtotal),
  and multi-option items are not marked "optional" in the same way.
- **This is separate from the "rejected proposal" behavior** documented in
  `PROPOSAL_REJECTION_HANDLING.md`, though both touch the approval workflow. If Option A is
  adopted here, consider it alongside Option A there (preventing sub-threshold bypass) for a
  consistent policy.

---

## 6. Recommendation

Adopt **Option A** (or **Option B** if management wants to minimize impact on existing
non-optional proposals). Both close the loophole where a large, optional-only quote skips
approval, aligning the trigger with the value actually presented to the customer.

---

## 7. Approval

| Role | Name | Decision (Approve A / Approve B / Keep C) | Date |
|------|------|-------------------------------------------|------|
| Sales Operations | | | |
| IT / Development Lead | | | |
| Management | | | |

---

### Appendix — Technical reference (for IT)
- Trigger: `Proposal.calculate_totals()` in `sales_proposals/models.py`.
- Optional exclusion: `priced_items = self.items.filter(is_optional=False)`.
- Threshold: `approval_required = approval_total_php >= Decimal('500000')`, where
  `approval_total_php` derives from `total_amount` (optional-excluded).
- Optional-inclusive totals already available: `quoted_subtotal`, `quoted_amount_php`.
- Multi-option path (unaffected): `sales_proposals/multi_option_views.py`
  `_calculate_multi_option_totals()`.
