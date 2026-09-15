# Password Reset & MFA Recovery — How It Works (As Built)

**System:** MICRO IMAGE CRM (internet-accessible)
**Status:** Implemented and verified. This documents the shipped behavior. The
decision record / rationale is in `PASSWORD_RESET_SECURITY_PLAN.md`.

---

## 1. Overview

Users can recover a forgotten password **themselves** via an emailed, single-use,
time-limited link. Admins no longer type passwords for users; instead they can
**send a reset link** to the user (admin never sees the password) and, for the
lost-authenticator case, **reset a user's MFA** — both restricted to admins and
audited. Everything is hardened for the public internet (rate limits,
anti-enumeration).

---

## 2. Self-service password reset (all users)

- **Where:** the login page has a **"Forgot Password?"** link → `/accounts/password/reset/`.
- **Flow:** enter email → receive a single-use, time-limited link → set a new
  password → sign in (TOTP/MFA is still required at login).
- **Powered by** django-allauth's reset flow, with branded pages that match the
  system design (see `templates/account/password_reset*.html`).
- **Anti-enumeration:** the page shows the same neutral "if an account exists, we
  sent an email" message whether or not the email matches
  (`ACCOUNT_PREVENT_ENUMERATION = True`).

## 3. Admin actions (role `admin` only, audited)

In **User Management → per-user Actions menu**:

- **Send Password Reset Link** — emails the *user* a reset token. The admin never
  sees or sets the password. Disabled if the user has no email on file.
- **Reset MFA (Lost Authenticator)** — removes the user's two-factor
  authenticator(s) so they re-enrol at next login. **Verify the user's identity
  out of band first** (e.g. manager confirmation / known-channel callback).

Design choices:

- **Password reset and MFA reset are separate actions** — knowing/resetting a
  password never disables MFA, and vice-versa. This prevents a single compromised
  admin session from fully taking over an account.
- The old free-text "set a new password" field on the Edit User form was
  **removed** and replaced with guidance pointing to Send Password Reset Link.

## 4. Abuse resistance (internet-facing)

- **Rate limits** (`ACCOUNT_RATE_LIMITS` in settings): reset request 5/min/IP,
  reset email 3/5min per target address, plus login limits — resists
  email-bombing, enumeration probing, and SMTP abuse.
- **Login brute force** is separately handled by `LockoutAwareBackend`
  (`MAX_FAILED_LOGIN_ATTEMPTS` / lockout window) and the `FailedLoginAttempt` log.

## 5. Audit trail

Every reset/MFA event is logged in **`users.PasswordResetAudit`** (who/whom/IP/user
agent/when):

| Action | When it's recorded |
|--------|--------------------|
| `self_completed` | A user completes a self-service reset (via allauth signal) |
| `admin_send_link` | An admin sends a reset link to a user |
| `admin_reset_mfa` | An admin resets a user's MFA |

Viewable in the Django admin (Users → Password Reset Audit).

## 6. Email identity

- Reset emails are sent **From `no-reply@microimageph.com`** — scoped to
  account/reset emails only via a custom allauth adapter
  (`users.adapters.MiCrmAccountAdapter` + `ACCOUNT_DEFAULT_FROM_EMAIL`). The rest of
  the app's emails still use `DEFAULT_FROM_EMAIL` (`sales@microimageph.com`).
- The email subject/body/links show **"MI CRM"** (not "example.com"): the
  `django.contrib.sites` Site is set to name `MI CRM`, domain
  `micrm.microimageph.com` via data migration `core/0002_set_site_name.py`. This
  matches `MFA_TOTP_ISSUER = 'MI CRM'` used by authenticator apps.

## 7. Key files & settings

| File | Responsibility |
|------|----------------|
| `templates/account/login.html` | "Forgot Password?" link |
| `templates/account/password_reset*.html` | Branded reset pages (request, done, from-key, from-key-done) |
| `crm_project/settings.py` | `ACCOUNT_RATE_LIMITS`, `ACCOUNT_PREVENT_ENUMERATION`, `ACCOUNT_ADAPTER`, `ACCOUNT_DEFAULT_FROM_EMAIL` |
| `users/adapters.py` | `MiCrmAccountAdapter` — no-reply From for account emails |
| `users/models.py` | `PasswordResetAudit` model |
| `users/signals.py` | `record_reset_audit()` + allauth `password_reset` signal handler |
| `users/views.py` | `send_password_reset`, `reset_user_mfa` (admin-only, audited); free-text password removed from `edit_user` |
| `users/urls.py` | `send_password_reset`, `reset_user_mfa` routes |
| `templates/users/user_management.html` | Admin Send Reset Link / Reset MFA actions |
| `core/migrations/0002_set_site_name.py` | Sets the Site to MI CRM / production domain |

## 8. Operations notes

- **SMTP sender authorization:** the mail server must be allowed to send as
  `no-reply@microimageph.com`. If reset emails bounce, authorize that mailbox or
  set `ACCOUNT_DEFAULT_FROM_EMAIL` in `.env` to an address the server accepts.
- **Secrets:** `EMAIL_HOST_PASSWORD` is read from the environment (`.env`), with no
  plaintext default in source. Rotate the SMTP credential if it was ever committed,
  and note `python-decouple` keeps surrounding quotes literally (don't quote the
  value in `.env`).
- **Deploy:** run `python manage.py migrate` (applies `users.0013_passwordresetaudit`
  and `core.0002_set_site_name`).

## 9. Not implemented (by decision)

- **"Set Temporary Password"** (admin-set one-time password with forced change) was
  intentionally skipped — self-service + admin Send-Reset-Link covers the forgot
  case without any staff member ever knowing a user's password. See the plan doc if
  this is revisited.
