# Secure Password Reset — Plan for Review & Approval

**System:** MICRO IMAGE CRM (internet-accessible)
**Prepared for:** Management / IT Security review & approval
**Status:** ✅ IMPLEMENTED (recommended approach: self-service reset + rate limits +
anti-enumeration + admin "Send Reset Link" + gated "Reset MFA"; the optional
"Set Temporary Password" was intentionally skipped). This document is retained as
the decision record / rationale. For the as-built behavior and file map, see
**[PASSWORD_RESET_AND_MFA.md](PASSWORD_RESET_AND_MFA.md)**.

---

## 1. Problem

Users forget the password they set. Today the **only** recovery path is: an admin
edits the user and types a new password into a form field. That is operationally
heavy (admin bottleneck), and because the app is on the public internet, we want a
reset process that is **self-service where safe** and **abuse-resistant**, without
handing admins a button that can be misused to take over accounts.

---

## 2. What already exists (verified in code)

Good news — most of the secure building blocks are already installed; they're just
not fully wired up or surfaced.

- **Auth stack:** `django-allauth` (`allauth.account`) is installed and its URLs are
  mounted at `/accounts/` (`crm_project/urls.py`). That means allauth's
  **self-service password reset already exists** at
  `/accounts/password/reset/` (URL name `account_reset_password`) — token-based,
  emailed link, time-limited. It is referenced from `password_change.html`
  ("Forgot Password?") but **not linked from the login page**.
- **MFA:** `allauth.mfa` with **TOTP + recovery codes** is enabled
  (`MFA_SUPPORTED_TYPES`), enforced by `core.middleware.MFARequiredMiddleware`.
- **Brute-force protection on login:** custom `users.backends.LockoutAwareBackend`
  with `MAX_FAILED_LOGIN_ATTEMPTS` / `FAILED_LOGIN_WINDOW_MINUTES` /
  `ACCOUNT_LOCKOUT_MINUTES`, plus a `FailedLoginAttempt` audit log.
- **Email:** SMTP configured (`EMAIL_HOST=email.microimageph.com`), with a
  file-based fallback in dev.
- **Admin-side reset today:** `users/views.py` → `edit_user` sets a new password via
  `set_password()` when an admin types one into the edit form.

### Gaps (the actual work)

1. **No "Forgot Password?" link on the login page** → self-service reset is hidden,
   so everything funnels to admins.
2. **No rate limiting on the reset flow** (`ACCOUNT_RATE_LIMITS` is not set) → the
   public reset endpoint could be hammered (email-bombing a victim, user enumeration
   probing, SMTP abuse).
3. **Admin reset is a plaintext password field** → the admin sees/sets the password
   (knows the user's credential), and it's easy to abuse for silent account takeover
   with no forced rotation or audit trail.
4. **Reset ↔ MFA interaction is undefined** → if a user resets their password but
   also lost their authenticator, they're still locked out (and a reset must NOT
   silently bypass MFA, or it becomes an account-takeover vector).
5. **Secret hygiene:** `settings.py` currently has a **hardcoded SMTP password**
   default and a real `EMAIL_HOST_PASSWORD` value in source. This must move to
   environment variables (see §9) — otherwise reset emails depend on a leaked
   credential.

---

## 3. Principles for an internet-facing reset

- **Prefer self-service** (token to the user's own mailbox) over admin-set passwords,
  so no staff member ever knows a user's password.
- **No user enumeration:** the reset page must show the same "if the account exists,
  we sent an email" message whether or not the email matches.
- **Rate-limit everything** that sends email or checks a token.
- **Tokens are single-use, short-lived, and invalidate on use / password change.**
- **Reset password ≠ reset MFA.** Knowing the password must not by itself disable
  two-factor; MFA reset is a separate, higher-assurance path.
- **Everything is audited** (who/when/from where), reusing the existing
  `FailedLoginAttempt`-style logging.
- **Least privilege for admins:** an admin can *initiate* a reset (send the user a
  link) but should **not** routinely *set* a known password.

---

## 4. Recommended design (two complementary paths)

### Path A — Self-service reset (primary, covers the common "I forgot")

Turn on and surface allauth's existing flow, hardened:

1. Add a **"Forgot Password?"** link on the login page → `account_reset_password`.
2. User enters email → receives a **single-use, time-limited token link** →
   sets a new password → tokens invalidated.
3. **Rate-limit** the request (per-IP and per-email) via `ACCOUNT_RATE_LIMITS`.
4. **Anti-enumeration** response (allauth already shows a neutral message; we verify
   and keep `ACCOUNT_PREVENT_ENUMERATION` on).
5. On success, **email the user a security notice** ("your password was changed").
6. **MFA stays intact:** after reset the user still completes the TOTP challenge at
   next login. Their existing authenticator keeps working.

### Path B — Admin-initiated reset (fallback, controlled)

Replace the "type a new password" habit with a **safer admin action**:

- Admin opens the user and clicks **"Send Password Reset Link"** → the system emails
  the **user** a reset token (admin never sees/sets the password).
- Optional, restricted: **"Set Temporary Password"** that (a) is shown once, (b) sets
  `must_change_password = True` so the user is **forced to change it at next login**,
  and (c) is logged. Use only when the user has no working email.
- Admin reset actions are **restricted to `admin`** (and optionally require the admin
  to be MFA-verified), and **audited**.

> Recommendation: ship **Path A + the "Send Reset Link" part of Path B** first.
> Treat "Set Temporary Password" as optional and gated, since it's the highest-risk
> piece.

---

## 5. Handling the MFA "double lockout" (forgot password AND lost authenticator)

This is the scenario most likely to still bottleneck admins. Proposed policy:

- **Password reset** (Path A) restores password access but does **not** touch MFA.
- **Lost authenticator** is a **separate, higher-assurance** admin action:
  **"Reset MFA"** on the user (removes their TOTP authenticator so they re-enrol at
  next login). This must be:
  - restricted to `admin`,
  - **identity-verified out of band** (e.g. the user confirms via a known channel /
    manager approval — a process step, documented),
  - audited (who reset whose MFA, when).
- Never combine "reset password" and "reset MFA" into one click — requiring two
  distinct actions (ideally two people, or verified identity) prevents a single
  compromised admin session from fully taking over an account.

---

## 6. Abuse-resistance controls (the core of the ask)

| Threat | Control |
|--------|---------|
| Email-bombing a victim via reset form | `ACCOUNT_RATE_LIMITS` (e.g. reset: a few/min per IP and per email) |
| User enumeration (probing which emails exist) | Neutral response + `ACCOUNT_PREVENT_ENUMERATION` |
| Token brute force / replay | allauth tokens are single-use + time-limited; invalidate on use |
| SMTP abuse / cost | Rate limit + monitor `FailedLoginAttempt`-style logs |
| Admin abuse (silent takeover) | Admin can only *send a link*; "set temp password" is gated, one-time, forces change, audited |
| Reset used to bypass 2FA | Reset never disables MFA; MFA reset is a separate verified action |
| Login brute force after reset | Existing `LockoutAwareBackend` still applies |

Reset attempts (request + completion) and all admin reset/MFA actions get an **audit
log** entry (reuse the `users` app's logging pattern used for `FailedLoginAttempt`).

---

## 7. User experience (what each role sees)

- **All users:** "Forgot Password?" on the login page → email link → set new password
  → log in (then normal MFA challenge). Self-serve, no admin needed.
- **Admin (in User Management):** per-user **"Send Password Reset Link"** button;
  gated **"Reset MFA"** button; optional gated **"Set Temporary Password"** (one-time,
  forces change). The current free-text password field on the edit form is
  **removed** (or hidden behind the gated temp-password action) to stop casual use.

---

## 8. Scope of work (proposed)

| # | Area | Change | Risk |
|---|------|--------|------|
| 1 | `templates/account/login.html` | Add "Forgot Password?" link → `account_reset_password` | Very low |
| 2 | `crm_project/settings.py` | Add `ACCOUNT_RATE_LIMITS` (reset/login), confirm `ACCOUNT_PREVENT_ENUMERATION=True` | Low |
| 3 | `templates/account/email/*` + reset pages | Brand the reset email + pages (MI CRM styling) | Low |
| 4 | `users/views.py` + `users/urls.py` | Admin **"Send Reset Link"** action (emails user token); admin-only + audited | Medium |
| 5 | `users/models.py` | Add `must_change_password` flag (for optional temp-password path) | Low |
| 6 | `core/middleware.py` | If `must_change_password`, force redirect to change-password page | Medium |
| 7 | `users/views.py` | Admin **"Reset MFA"** action (remove TOTP authenticator), gated + audited | Medium |
| 8 | `users/views.py` (`edit_user`) | Remove/relocate the free-text password field | Low |
| 9 | audit logging | Log reset requests/completions + admin reset/MFA actions | Low |
| 10 | `settings.py` / `.env` | Move `EMAIL_HOST_PASSWORD` (and other secrets) out of source into env | **Do first** |

## 9. Security fix to do regardless — secrets in source

`crm_project/settings.py` currently contains a **real SMTP password as a default**
(`EMAIL_HOST_PASSWORD`) and other credential-looking defaults committed to source.
Because password reset depends on outbound email, and this repo is deployed to an
internet-facing host, this credential should be:

1. **Rotated** (assume it may be exposed).
2. Moved to environment variables / `.env` (already the pattern via `config(...)`) with
   **no plaintext default** in `settings.py`.
3. Confirmed that `.env` is gitignored.

This is independent of the reset feature but directly affects its safety.

## 10. Data safety & non-breakage

- Path A reuses allauth's built-in, well-tested reset — minimal new code.
- New admin actions are **additive** and gated to `admin`; the existing login,
  lockout, and MFA flows are unchanged.
- `must_change_password` defaults `False` (additive migration) so existing users are
  unaffected until an admin issues a temp password.
- No change to how passwords are stored (Django's hasher).

---

## 11. Verification plan (before sign-off)

1. **Self-service:** request reset for a real email → receive link → set new password
   → log in → MFA challenge still required. Wrong/unknown email → same neutral message.
2. **Rate limit:** repeated reset requests are throttled (per IP + per email).
3. **Admin send-link:** admin triggers reset → user (not admin) gets the email; action
   is logged; admin never sees the password.
4. **Temp password (if built):** one-time display, `must_change_password` forces change
   at next login, logged.
5. **Reset MFA (gated):** admin resets a user's MFA → user re-enrols at next login;
   password reset alone never removes MFA.
6. **Secrets:** SMTP password no longer in source; reset emails still send.
7. `python manage.py check` clean; migration applies.

---

## 12. Open questions for approval

1. **Admin capabilities:** Send-Reset-Link only (recommended), or also allow the gated
   "Set Temporary Password"? And should admin reset actions require the admin to be
   MFA-verified?
2. **MFA reset process:** what out-of-band identity check do we require before an admin
   resets a user's MFA (manager approval? phone confirmation)?
3. **Rate-limit thresholds:** confirm acceptable limits (e.g. 3 reset emails / 5 min /
   email; 5 / hour / IP).
4. **Temp password lifetime:** if used, how long valid (e.g. 24h) before it expires?
5. **Secret rotation:** confirm we can rotate the SMTP credential now (§9).

---

*Awaiting approval. On approval, implementation follows §8 — starting with §10
(secrets), then Path A (self-service + rate limits), then the gated admin actions.*
