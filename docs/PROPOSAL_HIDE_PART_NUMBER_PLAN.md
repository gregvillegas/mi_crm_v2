# Optional "Part No." Column — Plan & Documentation for Approval

**System:** MICRO IMAGE CRM — Sales Proposals
**Prepared for:** Management / Sales Ops review & approval
**Status:** For decision. Sections 1–3 describe **current, verified behavior** (no code changed). 
Sections 4–8 propose the change and require approval before implementation.

---

## 1. Observation / Request

Some proposals do not use manufacturer part numbers (e.g. a single camera quotation where the item lines are feature bullets like "20.1MP 1" Exmor RS BSI CMOS Sensor",
"BIONZ X Image Processor", etc.). On those proposals the **PART NO.** column is empty for
every row, which:

- wastes horizontal space, and
- looks less professional (a whole empty column running down the page).

Other proposals **do** use part numbers (e.g. `B4YT6AV`, `SNV3S/500G`) and need the column.

**Request:** Allow a proposal to **hide the Part No. column** so its space is given to the
**Description** column. This should be a per-proposal choice and must **not** change or break
any existing proposal.

---

## 2. How the Part No. column works today (verified in code)

The items table has a **fixed 7-column layout** in this exact order everywhere:

| Idx | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|-----|-----|--------------|-------------|-----|------------|-------------|-------------------|
| Col | ITEM | **PART NO.** | DESCRIPTION | QTY | UNIT PRICE | TOTAL PRICE | AVAILABILITY/WARRANTY |

The same 7-column structure is emitted in **four** places:

1. **PDF — single-format** builder — `sales_proposals/views.py`, `generate_pdf_buffer()`
   (standard `else:` branch).
2. **PDF — multi-option** builder — same function (the `if proposal.is_multi_option:` branch,
   one table per OPTION group).
3. **On-screen detail — standard table** — `templates/sales_proposals/proposal_detail.html`.
4. **On-screen detail — multi-option table** — same template (second table).

Important technical facts:

- **`part_number` data is always stored** on `ProposalItem` (`max_length=100, blank=True`).
  Hiding the column is a **display choice only** — no data is deleted or moved.
- In the PDF, columns are **index-based**, not name-based. The `col_widths` array and the
  ReportLab `TableStyle` rules (backgrounds, grids, the Total/Subtotal/Grand-Total spanning
  rows) all reference **absolute column numbers**. If Part No. (index 1) is removed, every
  coordinate to its right shifts by one and must be recomputed.
- **Bundle sub-items** (the indented component rows under a bundled item) also render a
  Part No. cell in all four places — they must be handled in lockstep.
- The **detail-view tables are plain HTML** — hiding a column there is a simple
  `{% if %}` around the `<th>`/`<td>` cells (low risk).

---

## 3. Existing pattern we will reuse

The system already has per-proposal display toggles that work exactly the way this feature
should: `use_availability_column`, `show_discount`, `show_vat`, `include_bank_details`,
`use_total_price_label`. Each is a `BooleanField` on `Proposal` with an explicit default,
surfaced as a checkbox on the proposal form, and read in the PDF/detail views.

We will **mirror this proven pattern** rather than invent a new mechanism. This keeps the
change consistent, low-risk, and familiar to future maintainers.

---

## 4. Recommended approach

Add a single per-proposal boolean toggle: **`hide_part_number`** (default `False`).

- **Default `False`** means **every existing proposal renders exactly as it does today** —
  the column stays visible. This is the key guarantee that no existing data or output breaks.
- When a user checks **"Hide Part No. column"** on a proposal:
  - The **Part No. column is omitted** from that proposal's PDF and detail view.
  - The freed width (**1.1 inch**) is **added to the Description column** (1.9" → 3.0"),
    which is exactly the "give the space to description" outcome requested.
  - Item / Qty / Unit Price / Total Price / Availability columns keep their current widths.

The toggle sits next to the existing checkboxes on the proposal form ("Show Availability column", "Include VAT", etc.), so it feels native to the UI.

### Why not the alternatives

- **Auto-hide when all part numbers are empty (no checkbox).** Rejected: it removes user control (a user may want an empty column for a specific client), and "all empty" is ambiguous for multi-option proposals where one option has part numbers and another does not.

  An explicit toggle is predictable.
- **Delete the part_number field / merge into description.** Rejected: destructive, breaks
  historical proposals and the change-log, and is irreversible. We keep the data.
- **Zero-width the column instead of removing it.** Rejected: leaves faint grid lines and
  header remnants; removing the column cleanly looks more professional.

---

## 5. Scope of changes (what will be touched)

| # | File | Change | Risk |
|---|------|--------|------|
| 1 | `sales_proposals/models.py` | Add `hide_part_number = BooleanField(default=False, help_text=…)` | Very low |
| 2 | `sales_proposals/migrations/0038_proposal_hide_part_number.py` | One `AddField` (auto-generated) | Very low |
| 3 | `sales_proposals/forms.py` | Add field to `ProposalForm.Meta.fields` + a friendly label | Very low |
| 4 | `sales_proposals/multi_option_forms.py` | Add field to `MultiOptionProposalForm.Meta.fields` (so multi-option proposals can use it too) | Very low |
| 5 | `templates/sales_proposals/proposal_form.html` | Add the checkbox next to the existing toggles | Very low |
| 6 | `templates/sales_proposals/multi_option_form.html` | Add the checkbox next to the existing toggles | Very low |
| 7 | `templates/sales_proposals/proposal_detail.html` | Wrap the 4 Part No. `<th>`/`<td>` locations (2 tables) in `{% if not proposal.hide_part_number %}` | Low |
| 8 | `sales_proposals/views.py` `generate_pdf_buffer()` | Build the column set conditionally in **both** PDF builders: omit Part No. from headers, data rows, bundle sub-rows and total/spacer rows; recompute `col_widths` and every shifted `TableStyle` coordinate | **Medium (highest risk)** |

No changes are needed to the save paths (single-format formset or multi-option JSON) because
`part_number` is still stored exactly as before — this is display-only.

---

## 6. Data safety & backward compatibility

- **No data is modified or deleted.** `part_number` values remain on every item.
- **`default=False`** guarantees all existing proposals (single and multi-option) keep the
  current 7-column layout, so previously issued/emailed PDFs remain reproducible.
- The migration is a pure additive column (`AddField`) — safe on SQLite (dev) and MySQL
  (production). It requires the standard `python manage.py migrate sales_proposals` on deploy.
- Fully **reversible**: unchecking the box (or a future rollback) restores the column with no
  data loss.

---

## 7. Testing plan (before sign-off)

1. **Existing proposal, toggle OFF (default):** PDF + detail view render identical to today
   (7 columns, Part No. present). Verify on one single-format and one multi-option proposal.
2. **Toggle ON, single-format:** Part No. column gone; Description wider; Subtotal / VAT /
   Discount / Grand Total rows still align; grid/borders intact; totals unchanged.
3. **Toggle ON, multi-option:** each OPTION table drops Part No.; "OPTION N" heading, repeated
   header on page breaks, and "Total Investment" row all still align.
4. **Toggle ON with bundle sub-items:** indented component rows render correctly without the
   Part No. cell (no misaligned/broken grid).
5. **Regression:** `python manage.py check` clean; render the real proposals from the two
   screenshots and confirm no `500`/layout errors.

---

## 8. Rollout

1. Approve this plan.
2. Implement items 1–8 (Section 5).
3. Run `python manage.py makemigrations && migrate` on dev; run the test plan (Section 7).
4. Deploy; run `python manage.py migrate sales_proposals` on production.
5. Brief Sales Ops: "New checkbox — *Hide Part No. column* — use it for proposals that don't
   quote part numbers (e.g. camera/feature-bullet quotes) for a cleaner look."

---

## 9. Effort & risk summary

- **Effort:** ~½ day including tests. The only non-trivial work is the two ReportLab PDF
  builders (index recalculation); the rest mirrors existing toggles.
- **Risk:** Low overall, isolated to proposal rendering. Medium only for the PDF column-index
  recomputation, which is fully covered by the test plan and guarded by `default=False`.
- **User-visible benefit:** cleaner, more professional proposals for part-number-less quotes,
  with the description getting the reclaimed space — with zero impact on existing proposals.

---

*Awaiting approval. On approval, implementation will follow exactly the scope in Section 5.*
