# Preventing Over-Long Item Descriptions — Plan for Review & Approval

**System:** MICRO IMAGE CRM — Sales Proposals
**Prepared for:** Management / Sales Ops review & approval
**Status:** For decision. Sections 1–3 describe **current, verified behavior**. Sections
4–8 propose changes and require approval before work.

---

## 1. Problem

Users sometimes paste a **huge raw spec dump** into a line item's **Description**
(e.g. an item with a **2,406-character** description of comma-separated internal
config codes). In the PDF this becomes a table cell **taller than a whole page**.

- **Before:** the PDF crashed with `LayoutError` (a row taller than the page can't
  be placed).
- **After the hotfix** (`splitInRow=1`): it no longer crashes, but the output is
  **ugly** — the red column-header stripe (ITEM / PART NO / …) repeats on every
  page fragment, and a wall of raw codes looks unprofessional (see the reported
  screenshots).

We want to **stop over-long/raw specs from entering** a proposal item, so PDFs stay
clean and professional.

---

## 2. Root cause (verified in code)

- `ProposalItem.description` is an **unbounded `TextField`**
  (`sales_proposals/models.py`) — no maximum length.
- Neither `ProposalItemForm` nor `MultiOptionItemForm`
  (`sales_proposals/forms.py`, `multi_option_forms.py`) validates description
  length or content — the field is a free `Textarea`.
- The PDF renders the description as a single table cell in a ~1.9-inch column, so
  long text grows vertically without bound.

So there is currently **no guardrail** between "paste anything" and "render in PDF."

## 3. Why this is really a data-hygiene problem

The offending descriptions are **raw manufacturer config strings** (e.g.
`SI,MOD,SW,SWZL,NO UP,FT,FACT SI,MOD,INFO,IMAGE ...`) — internal codes that
shouldn't be on a customer-facing quote at all. The goal isn't just "make it fit,"
it's **"keep descriptions concise and human-readable."**

---

## 4. Recommended approach (defense in depth)

Mirror the pattern already used for the Availability/Warranty field (a shared
max-length constant enforced at model + form + widget level). Apply **three layers**:

### Layer 1 — Soft limit with live feedback (UI)
- Add a **character counter** and a **recommended limit** on the Description
  textarea (e.g. "320 / 500 characters"). Turns red past the limit.
- A **hard `maxlength`** HTML attribute on the widget so the browser stops typing/
  pasting beyond the cap (covers the copy-paste case directly).

### Layer 2 — Form validation (server)
- `clean_description()` on both `ProposalItemForm` and `MultiOptionItemForm`:
  reject descriptions longer than the limit with a clear message
  ("Description is 2,406 characters. Please shorten to under 500 — use concise
  specs, not raw config codes.").
- This is the real enforcement (the browser attribute can be bypassed).

### Layer 3 — Model safety net
- Add `ProposalItem.DESCRIPTION_MAX_LENGTH` constant and enforce it in
  `ProposalItem.save()` (truncate as a last resort) so **no** path — form,
  multi-option JSON, API, admin, shell, import — can store an over-long value.
  This mirrors the existing Availability/Warranty safety net.

### What limit?
- Recommend **500 characters** as the cap (roughly 8–10 lines in the PDF column —
  comfortably under a page, enough for a real product description). **Confirm the
  number** in §8; it's a one-line change.

### Keep the PDF hotfix
- Leave `splitInRow=1` in place as a **last-resort safety net** (so a legacy row or
  edge case never crashes), but with the length cap it should rarely, if ever,
  trigger — and we avoid the ugly repeated-header output for new data.

---

## 5. Handling existing over-long descriptions (backfill)

There is at least one item already over the limit (item 659 on proposal 268). Options:

- **(A) Report only (recommended first):** a one-off management command that lists
  proposals/items whose description exceeds the limit, so Sales can review and edit
  them by hand (preserves meaning; nothing auto-changed).
- **(B) Auto-truncate legacy rows:** a data migration/command that trims existing
  descriptions to the limit (fast, but may cut meaningful text).

Recommend **(A)** — list them, let owners clean them up — since these are
customer-facing and auto-cutting could remove real content mid-word.

---

## 6. Scope of work (proposed)

| # | File | Change | Risk |
|---|------|--------|------|
| 1 | `sales_proposals/models.py` | Add `DESCRIPTION_MAX_LENGTH` constant + truncate in `ProposalItem.save()` | Low |
| 2 | `sales_proposals/forms.py` | `maxlength` widget attr + `clean_description()` on `ProposalItemForm` | Low |
| 3 | `sales_proposals/multi_option_forms.py` | Same `clean_description()` on `MultiOptionItemForm` | Low |
| 4 | `templates/sales_proposals/proposal_form.html` + `multi_option_form.html` | Character counter + helper text ("concise specs, not raw codes") | Low |
| 5 | multi-option JS (`multi_option_form.html`) | Enforce the same cap on the JS-built item rows before submit | Low |
| 6 | management command (optional) | Report existing over-limit descriptions (backfill option A) | Low |
| 7 | (keep) `views.py` `splitInRow=1` | Retain as last-resort safety net | none |

No schema change is required (it's still a `TextField`); the cap is enforced in
code, so no migration for the field itself. (A migration is only needed if we also
run the optional backfill.)

## 7. Data safety & non-breakage

- Additive validation; existing proposals render exactly as before (the hotfix
  already prevents crashes).
- The model truncation is a last-resort net identical in spirit to the
  Availability/Warranty one already shipped, so the pattern is proven.
- Backfill option A changes **no** data (report only).

---

## 8. Open questions for approval

1. **Character limit:** confirm **500** (recommended) or another value.
2. **Hard vs soft:** block on save (recommended), or only warn and allow?
3. **Existing rows:** report-only (A, recommended) or auto-truncate (B)?
4. **Bundled items:** apply a similar per-line/overall cap to the "bundled items"
   textarea too? (It can also grow large.)

---

*Awaiting approval. On approval, implementation follows §6 — model + form + UI
guardrails, keeping the PDF `splitInRow` net, and a report of existing over-limit
items for Sales to clean up.*
