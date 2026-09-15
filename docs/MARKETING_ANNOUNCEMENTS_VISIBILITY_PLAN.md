# Marketing Announcements & Events — Company-Wide Visibility Plan

**System:** MICRO IMAGE CRM — Mass Mailing (Marketing)
**Prepared for:** Management / Marketing review & approval
**Status:** For decision. Sections 1–3 describe **current, verified behavior**
(no code changed). Sections 4–9 propose the change and require approval before
implementation.

---

## 1. Request

Marketing creates **announcements and events** (and posts new EDMs/promos). Right
now only Marketing/Admin can see them. The ask:

- Let **salespeople and other roles view** the announcements/events Marketing creates.
- Decide whether this needs a **dedicated page**.
- Give everyone a way to **know when something new** is posted (announcement,
  event, or new EDM/promo).

---

## 2. What already exists today (verified in code)

Good news — the data model and Marketing's authoring tools are already built. The
only missing piece is **read access + notification for everyone else**.

- **Model:** `mass_mailing/models.py` → `Announcement` with:
  - `title`, `body`, `announcement_type` (`event`, `news`, `promo`, `edm`),
    `event_date`, `location`, `link_url`, `is_active`, `created_by`,
    `created_at`, `updated_at`.
  - Helpers: `is_event`, `is_upcoming` (future-dated events), `badge_class`
    (color per type). So events vs news vs promo vs EDM are already distinguishable.
- **Authoring (Marketing/Admin only):** full CRUD in `mass_mailing/views.py`
  (`announcement_list/create/edit/delete/toggle`), gated by
  `can_manage_announcements` = roles `admin`, `marketing`.
- **Where shown now:** the Marketing dashboard / `announcement_list.html`. There is
  **no** view for non-marketing roles, and **no** notification.

## 3. Reusable patterns already in the app (so we don't reinvent)

The CRM already has a proven **notification bell** driven by context processors:

- Registered in `crm_project/settings.py` →
  `customers.context_processors.customer_request_notifications` and
  `sales_proposals.context_processors.proposal_approval_notifications`.
- Rendered in `templates/base.html` as the 🔔 bell with a red count badge and a
  dropdown list of items (title + message + timestamp + link).
- The customer-request flow also demonstrates a **"seen" mechanism**
  (`requester_seen_at`) to drive an unread count.

We will **mirror these patterns** so the new feature looks and behaves like the
rest of the system.

---

## 4. Recommended solution (overview)

Three small, additive pieces:

1. **A dedicated "Announcements & Events" page** that all authenticated users can
   view (read-only for non-Marketing). Marketing keeps their existing manage page.
2. **A notification bell entry** ("Marketing Updates") showing recent
   announcements/events/EDMs, with an **unread count** badge so users know when
   something new is posted.
3. **A nav link** (under a Marketing/Announcements menu, or the existing bell
   "View all" footer) pointing to the page.

Everything reuses the existing `Announcement` model and the existing bell UI. No
emails are required (keeps it low-noise), though an optional email digest is noted
as a future add-on in §8.

---

## 5. Does it need a dedicated page? — Yes (recommended)

**Recommendation: add a read-only page at `/mass-mailing/announcements/feed/`**
(name TBD), visible to all authenticated users.

Why a page (not just the bell):
- The bell is for *"something changed"* glancing; a page is where users **browse
  all active** announcements, upcoming events (sorted by `event_date`), promos, and
  new EDMs — including items they've already seen.
- Events benefit from a richer layout (date, location, register link).
- Keeps the bell dropdown short (recent 5) while the page holds the full list.

Page behavior:
- Shows only `is_active=True` items, newest first; **events** grouped/sorted by
  `event_date` with upcoming highlighted (`is_upcoming`).
- Filter chips by type (Event / News / Promo / EDM) reusing `badge_class` colors.
- Read-only for everyone; Marketing/Admin see inline **Edit** links (reusing their
  existing manage views).

---

## 6. How will users know something is new? — The bell + unread count

**Recommendation: a "Marketing Updates" section in the existing notification bell**,
with a red count badge, exactly like the other two notification sources.

The challenge: unlike a customer request (seen by one requester), an announcement is
seen by **many** users — so "seen" must be tracked **per user**, not per
announcement. Proposed mechanism:

- **New tiny model** `AnnouncementView` (or a `last_seen` timestamp per user):
  `user` + `last_seen_at`. When a user opens the Announcements page (or clicks the
  bell section), we stamp `last_seen_at = now()`.
- **Unread count** = number of `is_active` announcements with
  `created_at > user.last_seen_at` (or all active if they've never viewed).
- A new **context processor** `mass_mailing.context_processors.marketing_updates`
  returns the recent items + unread count, registered in `settings.py` alongside
  the existing two. `base.html` gets a small "Marketing Updates" block in the bell
  dropdown (title, type badge, date, link to the item/page).

This gives the "how do they know" answer: **a red badge on the bell** the moment
Marketing posts a new announcement/event/EDM, cleared once the user views the feed.

### Alternative/)complementary signals (optional, for approval)
- **Home-dashboard widget:** a compact "Latest from Marketing" card on the
  salesperson home page (a few most-recent items). Low effort, high visibility.
- **Email digest:** a weekly or on-publish email. Higher noise; recommend **off by
  default** and only if Marketing explicitly wants it (see §8).

---

## 7. Access model (who sees what)

| Role | Announcements page | Bell "Marketing Updates" | Create/Edit/Delete |
|------|--------------------|--------------------------|--------------------|
| Marketing / Admin | ✓ (with Edit links) | ✓ | ✓ (existing) |
| Salesperson, Supervisor, ASM, SM, AVP, teamlead, VP, GM, President | ✓ (read-only) | ✓ | ✗ |

All authenticated users get read access; only `admin`/`marketing` retain authoring
(unchanged `can_manage_announcements`). Announcements are **company-wide** (not
team-scoped) — everyone sees the same marketing content, which matches intent.

---

## 8. Scope of work (what will be added)

| # | File | Change | Risk |
|---|------|--------|------|
| 1 | `mass_mailing/models.py` | Add `AnnouncementView` (user + last_seen_at) for per-user unread tracking | Low |
| 2 | `mass_mailing/migrations/000X_*.py` | Migration for the new model (additive) | Low |
| 3 | `mass_mailing/views.py` | Add read-only `announcement_feed` view (all users) + a small endpoint/logic to stamp `last_seen_at` | Low |
| 4 | `mass_mailing/urls.py` | Add the feed route | Very low |
| 5 | `mass_mailing/context_processors.py` (new) | `marketing_updates` → recent items + unread count | Low |
| 6 | `crm_project/settings.py` | Register the new context processor | Very low |
| 7 | `templates/mass_mailing/announcement_feed.html` (new) | Read-only feed page (type filters, event layout) | Low |
| 8 | `templates/base.html` | Add "Marketing Updates" block to the bell dropdown + include its count in the badge total; add a nav link | Low |
| 9 | (optional) home dashboard template | "Latest from Marketing" card | Low |

No change to Marketing's existing authoring views/permissions.

## 9. Data safety & non-breakage

- **Purely additive:** one new model + one new page + one new context processor.
  No existing model, view, or template behavior changes (the bell just gains a
  third section and adds its count into the existing total).
- **Company-wide, no team scoping**, so none of the recent ASM/SM group-scoping
  work is affected.
- The new context processor must be **null-safe** for anonymous users (return empty)
  exactly like the existing two, so no page breaks.
- Reuses existing `Announcement` records — nothing to migrate/backfill beyond the
  new empty `AnnouncementView` table.

---

## 10. Verification plan (before sign-off)

1. As **salesperson**: Announcements page loads read-only; no Edit controls; bell
   shows a count when Marketing posts something new; count clears after viewing.
2. As **marketing/admin**: existing manage page unchanged; new item appears in the
   feed and raises everyone's bell count.
3. **Events** sort by `event_date`; upcoming highlighted; EDM/promo/news badges
   colored via `badge_class`.
4. Anonymous/logout: no errors from the new context processor.
5. `python manage.py check` clean; migration applies on dev.

---

## 11. Open questions for approval

1. **Dedicated page:** confirm yes (recommended) vs. bell-only.
2. **Unread tracking granularity:** per-user "last seen" timestamp (simple,
   recommended) vs. per-item read receipts (more precise, more storage).
3. **Home-dashboard "Latest from Marketing" card:** include now or later?
4. **Email digest:** skip (recommended), on-publish, or weekly?
5. **Menu placement:** top-nav link, bell "View all" footer, or both?

---

*Awaiting approval. On approval, implementation follows the scope in §8 with the
verification in §10.*
