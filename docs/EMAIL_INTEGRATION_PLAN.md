# CRM Email Integration — Feasibility Assessment & Implementation Plan

**Status:** For Management Review  
**Date:** August 2026  
**Prepared by:** Development Team

---

## Executive Summary

**Goal:** Allow salespeople to reply to customer emails directly within the CRM, maintaining a full email trail for auditing. When a proposal is sent, the entire conversation thread (initial send, customer replies, follow-ups) should be visible inside the CRM without bypassing to Outlook.

**Is it feasible? Yes.** The current system uses the company mail server (`email.microimageph.com`) for outbound SMTP. The missing piece is **inbound email capture** — processing replies that currently land only in salespeople's Outlook inboxes.

---

## Current State Analysis

### What Exists Today

| Capability | Status | Details |
|---|---|---|
| Outbound proposal emails | Working | Via SMTP to `email.microimageph.com:587` |
| Email send logging | Working | `ProposalEmailLog` records success/failure |
| Reply-To header | Set | Points to salesperson's personal email |
| Mass mailing campaigns | Working | Management command with rate limiting |
| Inbound email processing | **None** | No IMAP, no webhooks, no Graph API |
| Email thread tracking | **None** | No Message-ID storage, no thread model |
| Microsoft Graph / OAuth | **None** | No packages installed |
| Bounce/open tracking | **None** | No delivery notifications processed |

### Email Configuration

```
EMAIL_HOST = email.microimageph.com
EMAIL_PORT = 587 (STARTTLS)
EMAIL_HOST_USER = crm_sales@microimageph.com
DEFAULT_FROM_EMAIL = sales@microimageph.com
Reply-To = salesperson's personal email (e.g., jrabe@microimageph.com)
```

### Current Flow (No Thread Visibility)

```
CRM sends proposal ──→ Customer receives email
                             │
                             ▼ (Customer replies)
                       Salesperson's Outlook inbox ──→ No CRM visibility
                             │
                             ▼ (Salesperson replies from Outlook)
                       Customer receives reply ──→ Thread continues outside CRM
```

---

## Proposed Architecture

### Target Flow (Full Thread Visibility)

```
CRM sends proposal ──→ Customer receives email
    │                        │
    │ (Message-ID stored)    ▼ (Customer replies)
    │                  Mail server receives reply
    │                        │
    │                        ▼ (IMAP polling or webhook)
    │                  CRM captures inbound email
    │                        │
    │                        ▼ (Matched via In-Reply-To header)
    │                  Thread linked to proposal + customer
    │                        │
    ▼                        ▼
Salesperson sees full conversation thread in CRM
    │
    ▼ (Replies from within CRM)
CRM sends reply with proper References headers ──→ Customer sees threaded email
```

---

## Implementation Options

### Option A: IMAP Polling (Recommended)

**How it works:** A background task periodically connects to the mail server via IMAP, fetches new emails from salespeople's inboxes (or a shared mailbox), and imports them into the CRM.

| Aspect | Details |
|---|---|
| **Approach** | Management command (`process_inbound_mail`) run via cron every 2–5 minutes |
| **Package** | `imapclient` (well-maintained Python IMAP library) |
| **Mailbox scope** | Shared CRM mailbox (e.g., `crm_inbox@microimageph.com`) OR per-salesperson mailboxes |
| **Thread matching** | Parse `In-Reply-To` and `References` headers → match to stored `message_id` |
| **Pros** | Works with the existing mail server; no external service needed; no server config changes |
| **Cons** | Slight delay (polling interval); needs IMAP credentials; doesn't capture emails sent from Outlook |
| **Effort** | ~3–4 weeks |

### Option B: Microsoft Graph API (If using Office 365)

**How it works:** Authenticate with Microsoft Graph using OAuth2, subscribe to mailbox notifications (webhooks), and read emails in real-time.

| Aspect | Details |
|---|---|
| **Approach** | Register Azure AD app; OAuth2 flow for each salesperson; Graph API subscriptions for new mail |
| **Package** | `msal` + `requests` (or `O365` Python library) |
| **Pros** | Real-time (webhook push); reads emails directly from Outlook; full Outlook integration |
| **Cons** | Requires Azure AD tenant admin approval; OAuth consent per user; more complex auth flow; dependency on Microsoft cloud |
| **Effort** | ~5–6 weeks |
| **Prerequisites** | Office 365 / Exchange Online tenant; Azure AD App Registration with Mail.Read permission |

### Option C: BCC-to-CRM + Webhook (Hybrid)

**How it works:** All outbound CRM emails BCC a shared CRM address. Configure the mail server to forward all emails to that address to a webhook endpoint.

| Aspect | Details |
|---|---|
| **Approach** | Outbound: auto-BCC `crm-trail@microimageph.com`. Inbound: mail server pipes to a Django endpoint. |
| **Pros** | Captures both directions; simple concept |
| **Cons** | Requires mail server admin to configure pipe/forward; doesn't capture Outlook-originated threads unless users manually BCC |
| **Effort** | ~2–3 weeks (if mail server supports pipe) |

---

## Recommended Approach: Option A (IMAP Polling)

Given the current infrastructure (company-owned mail server, no Office 365 dependency), IMAP polling is the most practical and least disruptive path.

### New Django App: `email_threads`

```
email_threads/
├── models.py          # EmailThread, EmailMessage
├── views.py           # Thread viewer, compose reply
├── tasks.py           # IMAP polling logic
├── management/
│   └── commands/
│       └── poll_inbound_mail.py  # Cron-triggered command
├── templates/
│   └── email_threads/
│       ├── thread_detail.html    # Conversation view
│       └── compose_reply.html    # Reply form
└── urls.py
```

### Data Models

```python
class EmailThread(models.Model):
    """Groups related emails into a conversation thread."""
    subject = models.CharField(max_length=500)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, related_name='email_threads')
    proposal = models.ForeignKey(Proposal, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_threads')
    participants = models.TextField(help_text='All email addresses involved')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_threads')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-last_message_at']


class EmailMessage(models.Model):
    """Individual email in a thread."""
    DIRECTION_CHOICES = [
        ('outbound', 'Outbound (CRM → Customer)'),
        ('inbound', 'Inbound (Customer → CRM)'),
    ]

    thread = models.ForeignKey(EmailThread, on_delete=models.CASCADE, related_name='messages')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    message_id = models.CharField(max_length=500, unique=True, help_text='RFC 2822 Message-ID header')
    in_reply_to = models.CharField(max_length=500, blank=True)
    references = models.TextField(blank=True, help_text='Space-separated Message-IDs')

    from_email = models.EmailField()
    to_emails = models.TextField()
    cc_emails = models.TextField(blank=True)
    subject = models.CharField(max_length=500)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    has_attachments = models.BooleanField(default=False)

    sent_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    read_by_owner = models.BooleanField(default=False)

    # Link to CRM entities
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    proposal_email_log = models.ForeignKey(ProposalEmailLog, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['sent_at']
```

### Outbound Changes (Minimal)

Modify `proposal_email()` and mass mailing to:

1. **Generate a unique Message-ID** before sending:
   ```python
   import uuid
   msg_id = f"<proposal-{proposal.pk}-{uuid.uuid4().hex[:8]}@microimageph.com>"
   email.extra_headers = {'Message-ID': msg_id}
   ```

2. **Store the Message-ID** in `ProposalEmailLog` (new field) and create an `EmailMessage` record.

3. **On reply from CRM**: Set `In-Reply-To` and `References` headers so email clients thread correctly.

### Inbound Processing (New)

```python
# management/commands/poll_inbound_mail.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        # 1. Connect via IMAP to shared CRM mailbox
        # 2. Fetch UNSEEN emails
        # 3. For each email:
        #    a. Parse headers (Message-ID, In-Reply-To, References, From, To, Subject)
        #    b. Match In-Reply-To → existing EmailMessage.message_id → find thread
        #    c. If no match: try to match From email → Customer → create new thread
        #    d. Store as EmailMessage with direction='inbound'
        #    e. Mark as SEEN on IMAP server
        #    f. Notify the thread owner (salesperson) via in-app notification
```

### UI Integration

1. **Proposal Detail page**: Add "Email Trail" tab showing all `EmailThread` messages linked to this proposal
2. **Customer Detail page**: Add "Email History" section showing all threads for this customer
3. **Reply Compose**: Inline form to reply within a thread (sends via SMTP with proper threading headers)
4. **Notification**: Badge on navbar when new inbound emails arrive

---

## Effort Estimate

| Phase | Tasks | Duration |
|-------|-------|----------|
| **Phase 1: Foundation** | EmailThread + EmailMessage models, migrations, admin registration | 3 days |
| **Phase 2: Outbound Enhancement** | Add Message-ID generation to proposal_email and mass_mailing; store in new model | 2 days |
| **Phase 3: IMAP Polling** | poll_inbound_mail command, email parsing, thread matching, cron setup | 5 days |
| **Phase 4: Reply from CRM** | Compose reply view, send with In-Reply-To/References headers | 3 days |
| **Phase 5: UI** | Thread viewer on proposal/customer detail, notification badge, compose form | 5 days |
| **Phase 6: Testing & QA** | End-to-end testing with real mail server, edge cases, performance | 3 days |
| **Total** | | **~4 weeks** |

---

## Prerequisites & Dependencies

| Requirement | Status | Action Needed |
|---|---|---|
| IMAP access to mail server | Unknown | Confirm `email.microimageph.com` supports IMAP; get credentials |
| Shared CRM mailbox | Not created | Request IT to create (e.g., `crm-threads@microimageph.com`) |
| Cron job capability on server | Likely available | Confirm with DevOps; needed for `poll_inbound_mail` every 2 min |
| `imapclient` package | Not installed | `pip install imapclient` (MIT license, well-maintained) |
| Reply-To address change | Minor code change | Point Reply-To to shared CRM mailbox instead of personal email |
| Storage for email bodies | Minimal | Text fields in DB; attachments in `media/email_attachments/` |

---

## Security & Compliance Considerations

| Concern | Mitigation |
|---|---|
| Email body storage (Data Privacy Act) | Encrypt at rest; retention policy (auto-delete after N months) |
| IMAP credentials | Store in `.env`, never in code; use app-specific password |
| Access control | Only thread owner + supervisors + execs can view thread content |
| Attachment handling | Scan for malware before storage; size limits |
| Audit trail | All actions logged (who viewed, who replied, timestamps) |

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|-----------|
| Mail server doesn't support IMAP | Blocks Option A | Low (most servers do) | Verify with IT before starting |
| High email volume causes polling delays | Replies visible after 2–5 min | Medium | Adjust polling frequency; consider webhook if delay unacceptable |
| Thread matching fails (no In-Reply-To) | Orphaned inbound emails | Medium | Fallback: match by subject line + customer email |
| Salespeople continue replying from Outlook | Partial trail in CRM | High (habit) | Training; consider BCC-to-CRM rule on mail server |
| Storage growth from email bodies | DB size increases | Low | Archive/purge policy; store bodies as files not DB text |

---

## Decision Points for Management

1. **Shared mailbox vs. per-salesperson IMAP?**
   - Shared: simpler setup, one IMAP connection; requires Reply-To change
   - Per-user: captures everything but needs each salesperson's IMAP credentials

2. **Mandatory or optional?**
   - Can salespeople still reply from Outlook, or must all replies go through CRM?
   - If mandatory: need enforcement (training + potentially removing Reply-To from outbound)

3. **Scope of Phase 1:**
   - Proposals only? Or all customer emails (including ad-hoc conversations)?
   - Recommendation: Start with proposals only, expand later

4. **Timeline priority:**
   - Can this wait for Q4 2026, or is it blocking current sales processes?

---

## Conclusion

Email integration is technically feasible with the current infrastructure. The recommended path (IMAP polling + thread models) requires ~4 weeks of development, one new Python package (`imapclient`), and coordination with IT for IMAP access and a shared mailbox. The solution preserves the existing workflow while adding full audit visibility into the proposal email trail.

No code changes are being made at this time. This document serves as the implementation blueprint pending management approval.
