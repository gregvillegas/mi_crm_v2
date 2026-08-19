# Multi-Option Sales Proposal — Feature Plan

**Status:** Pending Management Approval  
**Author:** Development Team  
**Date:** August 2026  
**Priority:** Enhancement — does NOT break existing single-format proposals

---

## 1. Executive Summary

Add a **Multi-Option Proposal** format to the CRM where a single proposal document presents multiple product/pricing configurations (Option 1, Option 2, etc.) each with their own item tables and subtotals — allowing the customer to compare and choose.

**Key constraint:** The existing single-format proposal MUST continue working unchanged. The multi-option format is activated via a toggle switch when creating or editing a proposal.

---

## 2. Current System vs. Proposed Feature

### Current Behavior (Single Format)

```
Proposal Header
├── Item 1 (priced, included in total)
├── Item 2 (priced, included in total)
├── Item 3 (is_optional=True → labeled "Option 1", excluded from total)
└── Total Investment: ₱X,XXX,XXX.XX
```

- All items live in one flat list
- Individual items can be marked `is_optional=True` — these get a sequential label ("Option 1", "Option 2") and are excluded from the grand total
- Grand Total row is hidden entirely when any optional items exist

### Proposed Behavior (Multi-Option Format)

```
Proposal Header

OPTION 1
├── Item A (priced)
├── Item B (bundled sub-components)
├── Item C (priced)
└── Total Investment: ₱45,615,616.00

OPTION 2
├── Item A (priced, different config)
├── Item B (bundled sub-components)
├── Item C (priced)
└── Total Investment: ₱41,944,968.00

Terms & Conditions (shared across all options)
```

- Each option group has its own header ("OPTION 1", "OPTION 2")
- Each group has its own items table with its own subtotal row ("Total Investment")
- Terms & Conditions appear once at the bottom (shared)
- The customer can see side-by-side pricing for different configurations
- No "grand total" across options (each option stands alone)

---

## 3. Feasibility Assessment

| Aspect | Feasible? | Notes |
|---|---|---|
| Model changes | ✅ Yes | Add `ProposalOptionGroup` model + `option_group` FK on `ProposalItem` |
| Backward compatibility | ✅ Yes | Toggle field on Proposal: `is_multi_option=False` by default — existing proposals untouched |
| Form/UI | ✅ Yes | Conditional UI: show grouped formsets when toggle is ON |
| PDF generation | ✅ Yes | Conditional rendering in `generate_pdf_buffer()` — render per-group tables |
| Approval workflow | ✅ Yes | Approval uses `approval_total_php` — for multi-option, use the highest option's total |
| Sales Funnel sync | ✅ Yes | Funnel entry links to proposal — can use highest option total as retail value |
| Email sending | ✅ Yes | PDF is already an attachment — format is transparent to email |
| Existing data | ✅ No migration risk | `is_multi_option=False` default means all existing records keep their behavior |

**Verdict: Fully feasible with zero impact on existing proposals.**

---

## 4. Data Model Changes

### New Model: `ProposalOptionGroup`

```python
class ProposalOptionGroup(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='option_groups')
    name = models.CharField(max_length=100, default='Option 1')
    sort_order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, help_text='Optional notes for this option group')

    class Meta:
        ordering = ['sort_order', 'id']
        unique_together = ('proposal', 'sort_order')

    @property
    def subtotal(self):
        return sum(item.amount for item in self.items.all())

    @property
    def total_cost(self):
        return sum(item.total_cost for item in self.items.all())
```

### Modified Model: `ProposalItem`

```python
# Add one nullable FK field:
option_group = models.ForeignKey(
    ProposalOptionGroup,
    on_delete=models.CASCADE,
    related_name='items',
    null=True, blank=True,
    help_text='Set only for multi-option proposals'
)
```

### Modified Model: `Proposal`

```python
# Add one boolean toggle:
is_multi_option = models.BooleanField(
    default=False,
    help_text='Enable multi-option format (OPTION 1, OPTION 2, etc.)'
)
```

### Migration Strategy

1. `is_multi_option` defaults to `False` → no existing proposal affected
2. `ProposalItem.option_group` is nullable → existing items remain unassigned (single-format behavior)
3. `ProposalOptionGroup` is a new table — no data migration needed

---

## 5. UI/UX Plan

### Proposal Form (Create / Edit)

**Toggle Control:** A checkbox/switch at the top of the form:
```
☐ Multi-Option Proposal (present multiple pricing options to the customer)
```

**When OFF (default):** Form looks exactly as it does today — flat item list.

**When ON:**

```
┌─────────────────────────────────────────────┐
│ OPTION 1                        [Remove Option] │
│ ┌─────────────────────────────────────────┐   │
│ │ Item rows (same fields as today)         │   │
│ │ [+ Add Item]                             │   │
│ └─────────────────────────────────────────┘   │
│ Subtotal: ₱XX,XXX,XXX.XX                      │
├─────────────────────────────────────────────┤
│ OPTION 2                        [Remove Option] │
│ ┌─────────────────────────────────────────┐   │
│ │ Item rows                                │   │
│ │ [+ Add Item]                             │   │
│ └─────────────────────────────────────────┘   │
│ Subtotal: ₱XX,XXX,XXX.XX                      │
├─────────────────────────────────────────────┤
│          [+ Add Another Option]                │
└─────────────────────────────────────────────┘
```

**UI Details:**
- Each option group has a collapsible card with a header showing "OPTION N"
- Option name is editable (e.g., "Option 1 — HP ZBook Ultra 9" or just "OPTION 1")
- Items within each option use the same formset UI (part number, description, qty, cost, price, warranty, bundle)
- `is_optional` checkbox is HIDDEN when multi-option is ON (options replace individual optional items)
- Per-option subtotal calculated live with JavaScript (same pattern as current total)

### Proposal Detail Page

When `is_multi_option=True`:
- Show each option group as a separate section with its own items table and subtotal
- No combined grand total shown

### Proposal List Page

- Show the **highest** option total as the "Amount" column (or show a range like "₱41.9M – ₱48.7M")
- Badge indicator: `[Multi-Option]` next to amount

---

## 6. PDF Generation Changes

### Conditional Logic in `generate_pdf_buffer()`

```python
if proposal.is_multi_option:
    # Render per-option-group tables
    for group in proposal.option_groups.all():
        # Section header: "OPTION 1" in bold red
        elements.append(Paragraph(group.name.upper(), heading_style))
        
        # Items table (same structure as current single table)
        items = group.items.all().order_by('id')
        table_data = build_item_table(items)  # reuse existing table builder
        elements.append(Table(table_data, ...))
        
        # Subtotal row: "Total Investment: ₱XX,XXX,XXX.XX"
        elements.append(subtotal_table_for_group(group))
        elements.append(Spacer(1, 18))
    
    # Terms & Conditions (same as current — shared across all options)
    elements.append(terms_section)
else:
    # Existing single-format rendering (unchanged)
    ...
```

### PDF Layout (matching screenshot reference)

- Option header: Bold text, left-aligned, "OPTION 1" / "OPTION 2"
- Item table: Red header row with columns: PART NUMBER | Description | QTY | UNIT PRICE | TOTAL PRICE | WARRANTY
- Subtotal row: Yellow/highlighted "Total Investment" at bottom of each table
- Spacing between options: ~18pt vertical spacer

---

## 7. Business Logic Impacts

### Approval Workflow

When `is_multi_option=True`:
- `approval_total_php` = **maximum** total across all option groups
- Reasoning: the approval threshold should trigger on the highest possible commitment

### Sales Funnel Integration

- `update_sales_funnel()` uses `proposal.quoted_amount_php`
- For multi-option: use the highest option group subtotal (optimistic forecast)
- Alternative: let the user manually select which option to link to funnel (Phase 2)

### Financial Properties

| Property | Single Format | Multi-Option |
|---|---|---|
| `subtotal` | Sum of non-optional items | Highest option group subtotal |
| `total_amount` | subtotal − discount | Highest option group subtotal − discount |
| `quoted_amount_php` | As today | Highest option group total in PHP |
| Per-group totals | N/A | Each `ProposalOptionGroup.subtotal` |

---

## 8. Implementation Phases

### Phase 1 — Core (Estimated: 3-4 days)

1. Add `is_multi_option` field to `Proposal` model
2. Create `ProposalOptionGroup` model
3. Add `option_group` FK to `ProposalItem`
4. Migration
5. Update `calculate_totals()` to handle multi-option
6. Update `generate_pdf_buffer()` with conditional multi-option rendering
7. Update proposal form UI with toggle and grouped formsets
8. Update proposal detail page

### Phase 2 — Polish (Estimated: 2 days)

9. Clone option group (duplicate an option with all its items)
10. Reorder option groups (drag-and-drop or up/down arrows)
11. Per-option notes/remarks field
12. Proposal list "amount range" display for multi-option proposals

### Phase 3 — Advanced (Estimated: 1-2 days)

13. Convert single-format → multi-option (move all items into "Option 1")
14. Export comparison table (side-by-side Excel with all options)
15. Let customer select preferred option from an email link (future)

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Breaking existing proposals | High | `is_multi_option=False` default; all code paths check this flag before choosing format |
| Complex nested formsets in Django | Medium | Use JavaScript-driven dynamic forms (same pattern as current item formset but nested) |
| PDF page overflow with many options | Medium | Use ReportLab `KeepTogether` + page break logic between option groups |
| Approval workflow confusion | Low | Clear rule: always use highest option total for threshold check |
| Change log tracking per option | Low | Extend changelog `details` dict with `option_groups` key |

---

## 10. Files That Will Be Modified

| File | Changes |
|---|---|
| `sales_proposals/models.py` | Add `ProposalOptionGroup`, add `option_group` FK to `ProposalItem`, add `is_multi_option` to `Proposal` |
| `sales_proposals/forms.py` | Add `ProposalOptionGroupFormSet`, conditional logic in `ProposalItemFormSet` |
| `sales_proposals/views.py` | Update `proposal_create`, `proposal_update`, `generate_pdf_buffer()` |
| `templates/sales_proposals/proposal_form.html` | Toggle switch + grouped item UI |
| `templates/sales_proposals/proposal_detail.html` | Conditional grouped display |
| `sales_proposals/admin.py` | Register `ProposalOptionGroup` |
| `sales_proposals/migrations/00XX_*.py` | New migration |

**Files NOT modified (unchanged):**
- Approval workflow logic (just uses `approval_total_php` — already calculated)
- Email sending (sends PDF attachment — format is transparent)
- Proposal list template (amount column already uses `quoted_amount_php`)

---

## 11. Acceptance Criteria

- [ ] Admin can toggle "Multi-Option Proposal" when creating/editing a proposal
- [ ] When toggled ON, the form shows grouped option sections with add/remove
- [ ] Each option group has its own item table and subtotal in both UI and PDF
- [ ] PDF output matches the reference screenshot layout (red headers, per-option totals)
- [ ] Existing single-format proposals are completely unaffected
- [ ] Approval workflow uses the highest option total for threshold evaluation
- [ ] Sales funnel sync uses the highest option total as retail value
- [ ] Change log captures option group additions/deletions/modifications

---

## 12. Decision Required from Management

1. **Approval:** Proceed with implementation? (Y/N)
2. **Phase scope:** Implement Phase 1 only, or Phase 1 + 2 together?
3. **Funnel integration:** Use highest option total automatically, or let user manually select?
4. **Option limit:** Maximum number of options per proposal? (Suggested: 5)
5. **Naming:** Allow custom option names ("Economy / Premium") or fixed ("OPTION 1 / OPTION 2")?

---

*Document prepared by the Development Team — Micro Image International Corp. — August 2026*
