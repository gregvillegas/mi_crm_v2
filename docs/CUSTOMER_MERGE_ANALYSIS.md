# Customer Duplicate Merge — Feasibility Analysis

## Executive Summary

**Is merging duplicate customers possible? Yes**, but it requires careful re-pointing of all related records before deleting the duplicate. The codebase uses `on_delete=CASCADE` extensively, meaning a naive delete would destroy proposals, funnel entries, sales activities, tickets, and audit history. A dedicated "Merge Customers" feature is the recommended approach.

---

## Current State: Duplicate Detection Filter

The "Show Duplicates" filter (added to customer list) identifies customers whose company names normalize to the same string after:
- Lowercasing
- Stripping punctuation
- Removing common suffixes (Corp, Inc, Ltd, Corporation, etc.)

Example matches from the screenshot:
| Customer A | Customer B |
|---|---|
| BEN LINE AGENCIES INC (Rolzeena Wati) | BEN LINE AGENCIES INC (Devine David) |
| FOLARES PHARMACEUTICALS, INC | Folares Pharmaceuticals, Inc. |
| FUNDACION EDUCACION Y COOPERACION - EDUCO PHILIPPINES | FUNDACION EDUCACION Y COOPERACION - EDUCO PHILIPPINES |
| M.B.A CONSULTING PHILIPPINES | M.B.A CONSULTING PHILIPPINES |

---

## Foreign Key Relationships to Customer

Every model referencing `Customer` that would be affected by a merge:

| App | Model | Field | on_delete | Records at risk |
|-----|-------|-------|-----------|-----------------|
| customers | `CustomerContact` | customer | CASCADE | Additional contacts |
| customers | `CustomerNote` | customer | CASCADE | Notes/comments |
| customers | `CustomerHistory` | customer | CASCADE | Full audit trail |
| customers | `CustomerBackup` | customer | CASCADE | Data backups |
| sales_proposals | `Proposal` | customer | CASCADE | All proposals |
| sales_funnel | `SalesFunnel` | customer | CASCADE | Pipeline entries |
| sales_monitoring | `SalesActivity` | customer | CASCADE | All activities |
| sales_monitoring | `ProofOfConcept` | customer | CASCADE | POC records |
| customer_service | `Ticket` | customer | CASCADE | Support tickets |
| mass_mailing | `CampaignRecipient` | customer | CASCADE | Email campaign records |
| mass_mailing | `OptOut` | customer | SET_NULL | Opt-out records (safe) |
| lead_generation | `Lead` | converted_to_customer | SET_NULL | Conversion link (safe) |

---

## CustomerContact Model (max 4 contacts per customer)

```
CustomerContact:
  - customer (FK → Customer, CASCADE)
  - name (CharField, max 120)
  - position (CharField, max 120)
  - email (EmailField)
  - phone (CharField, max 50)
  - is_primary (BooleanField)
```

**Current constraint:** `save()` enforces max 4 contacts per customer and only 1 primary per customer.

During merge, contacts from the duplicate would be added as additional contacts to the surviving customer. The 4-contact limit would need to be relaxed or the merge would warn when it exceeds the limit.

---

## Recommended Solution: Merge Customers Feature

### Merge Workflow

1. **Admin selects a duplicate group** from the "Show Duplicates" filter view
2. **Admin picks the "surviving" (primary) customer** — this is the record that stays
3. **System shows a preview** of what will be merged:
   - Contacts that will be added
   - Number of proposals, activities, funnel entries, tickets that will be re-pointed
   - Whether the duplicate has different field values (address, industry, territory)
4. **Admin confirms** the merge
5. **System executes** (in a transaction):
   - Re-points all FK references from duplicate → surviving customer
   - Migrates contacts (duplicate's contacts become additional contacts on survivor)
   - Migrates the legacy main contact (contact_person_name/email/phone) as a CustomerContact
   - Updates `SalesFunnel.company_name` if it matches the duplicate's name
   - Logs a `CustomerHistory` entry on the surviving customer documenting the merge
   - Creates a backup of both customers before merge
   - Deletes the duplicate customer record (now safely, no CASCADE data loss)
6. **Admin sees confirmation** with summary of what was merged

### Implementation Plan

#### Step 1: New View — `merge_customers(request, primary_pk, duplicate_pk)`

```python
@login_required
@user_passes_test(is_admin_or_exec)
def merge_customers(request, primary_pk, duplicate_pk):
    """Merge duplicate customer into primary customer."""
    primary = get_object_or_404(Customer, pk=primary_pk)
    duplicate = get_object_or_404(Customer, pk=duplicate_pk)
    
    if request.method == 'POST':
        with transaction.atomic():
            # 1. Backup both customers
            primary.create_backup(request.user, reason=f"Pre-merge backup (merging #{duplicate.pk})")
            duplicate.create_backup(request.user, reason=f"Pre-merge backup (will be merged into #{primary.pk})")
            
            # 2. Re-point all FK references
            Proposal.objects.filter(customer=duplicate).update(customer=primary)
            SalesFunnel.objects.filter(customer=duplicate).update(customer=primary)
            SalesActivity.objects.filter(customer=duplicate).update(customer=primary)
            ProofOfConcept.objects.filter(customer=duplicate).update(customer=primary)
            Ticket.objects.filter(customer=duplicate).update(customer=primary)
            CampaignRecipient.objects.filter(customer=duplicate).update(customer=primary)
            OptOut.objects.filter(customer=duplicate).update(customer=primary)
            Lead.objects.filter(converted_to_customer=duplicate).update(converted_to_customer=primary)
            CustomerNote.objects.filter(customer=duplicate).update(customer=primary)
            CustomerHistory.objects.filter(customer=duplicate).update(customer=primary)
            CustomerBackup.objects.filter(customer=duplicate).update(customer=primary)
            
            # 3. Update denormalized company_name in SalesFunnel
            SalesFunnel.objects.filter(
                customer=primary, company_name=duplicate.company_name
            ).update(company_name=primary.company_name)
            
            # 4. Migrate contacts
            _migrate_contacts(primary, duplicate)
            
            # 5. Merge lifetime_won_revenue
            primary.lifetime_won_revenue += duplicate.lifetime_won_revenue
            primary.save(update_fields=['lifetime_won_revenue'])
            
            # 6. Log the merge
            CustomerHistory.log_customer_change(
                customer=primary,
                action='updated',
                description=f'Merged duplicate customer #{duplicate.pk} "{duplicate.company_name}" into this record.',
                changed_by=request.user,
                old_value={'merged_customer_id': duplicate.pk, 'merged_company_name': duplicate.company_name},
            )
            
            # 7. Delete the duplicate (safe — all FKs already re-pointed)
            duplicate.delete()
        
        messages.success(request, f'Successfully merged "{duplicate.company_name}" into "{primary.company_name}".')
        return redirect('customer_detail', pk=primary.pk)
    
    # GET — show confirmation page with merge preview
    ...
```

#### Step 2: Contact Migration Helper

```python
def _migrate_contacts(primary, duplicate):
    """Move duplicate's contacts into primary, converting main contact to CustomerContact."""
    # Convert duplicate's legacy main contact into a CustomerContact
    if duplicate.contact_person_name:
        CustomerContact.objects.get_or_create(
            customer=primary,
            name=duplicate.contact_person_name,
            defaults={
                'position': duplicate.contact_person_position,
                'email': duplicate.email,
                'phone': duplicate.phone_number,
            }
        )
    
    # Re-point existing CustomerContact records
    for contact in CustomerContact.objects.filter(customer=duplicate):
        contact.customer = primary
        contact.is_primary = False  # Don't override primary's primary contact
        contact.save()
```

**Important:** The current 4-contact limit in `CustomerContact.save()` would need to be relaxed for merge operations (either by temporarily bypassing it, or raising the limit). Otherwise contacts beyond 4 get auto-deleted.

#### Step 3: URL

```python
path('<int:primary_pk>/merge/<int:duplicate_pk>/', views.merge_customers, name='merge_customers'),
```

#### Step 4: UI Integration

Add a "Merge" button in the duplicates view. When the user is viewing duplicates, each group would show:
- A radio button or selection to pick the "primary" (surviving) record
- A "Merge into selected" button that triggers the merge confirmation page

---

## What NOT to Do

- **Don't just delete duplicates** — CASCADE will destroy all related business data
- **Don't merge automatically** — human review is needed to decide which record is the "primary"
- **Don't ignore the salesperson assignment** — if duplicates are assigned to different salespeople, the admin must decide who keeps the account

---

## Edge Cases to Handle

| Scenario | Resolution |
|----------|-----------|
| Different salesperson assigned | Admin picks which salesperson stays (default: primary customer's salesperson) |
| Different industry/territory | Keep primary's values; log the difference in merge history |
| Both have proposals with same customer | All proposals end up under one customer — fine, no conflicts |
| Contact limit exceeded after merge | Raise limit to 8, or warn admin and let them choose which to keep |
| Duplicate has higher lifetime_won_revenue | Sum both values into the surviving customer |
| One is millionaire, one is not | Surviving customer gets `is_millionaire_account=True` if either was |

---

## Effort Estimate

| Component | Effort |
|-----------|--------|
| Backend view + merge logic | 3–4 hours |
| Merge confirmation template | 2 hours |
| Contact migration + limit handling | 1 hour |
| UI button integration in duplicates list | 1 hour |
| Testing (manual + unit) | 2 hours |
| **Total** | **~9–10 hours** |

---

## Conclusion

Merging is fully feasible. The key insight is that all related records use simple ForeignKey relationships (no M2M, no composite keys), so a bulk `UPDATE ... SET customer_id = primary_id WHERE customer_id = duplicate_id` on each table safely transfers ownership. The `CustomerContact` model's 4-contact soft limit is the only constraint that needs special handling.

Recommended next step: Implement the merge view with a confirmation page showing what will be combined, restricted to admin/exec roles only.
