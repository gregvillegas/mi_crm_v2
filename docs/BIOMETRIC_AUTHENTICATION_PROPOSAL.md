# Biometric Authentication — Feasibility & Implementation Proposal

**Prepared for:** Management Review & Approval
**System:** MICRO IMAGE CRM
**Prepared by:** Development Team
**Status:** For approval (no code changes made yet)

---

## 1. Executive Summary

**Question:** Can we add biometric authentication (fingerprint / Face ID / Windows Hello) to the CRM login?

**Answer: Yes — and it is a low-risk, well-supported addition.** The CRM already runs on
`django-allauth` (v65.18), whose multi-factor module includes **native WebAuthn / Passkey
support**, and the required `fido2` library (v2.2) is already installed. This means biometric
login can be delivered largely through **configuration and UI**, not a custom, from-scratch
security build.

Biometrics would work through the industry-standard **WebAuthn / FIDO2 ("Passkeys")** protocol,
which uses the biometric sensor already built into each staff member's device — Touch ID / Face ID
on Mac & iPhone, Windows Hello on PCs, and fingerprint / face unlock on Android.

**Critical clarification for management:** The company's servers will **never receive, store, or
process anyone's actual fingerprint or face data.** The biometric never leaves the employee's
device. This is explained in Section 4.

---

## 2. What "Biometric Authentication" Actually Means Here

There are two common misconceptions worth settling up front:

1. **We are NOT building a fingerprint database.** The CRM does not capture, transmit, or store
   biometric images/templates. There is no biometric data on our servers to protect or breach.

2. **The biometric unlocks a secure key ON THE DEVICE.** The employee's phone/laptop holds a
   private cryptographic key protected by the device's own secure hardware. When they log in, the
   device asks for their fingerprint/face **locally** to unlock that key, and only a mathematical
   signature is sent to our server. This is the same mechanism used by online banking apps and
   Google/Microsoft passkeys.

In short: **the fingerprint is just the "unlock" for a hardware security key that lives on the
employee's own device.**

---

## 3. How It Fits Our Current System

The CRM already has a layered authentication setup that this builds on cleanly:

| Existing today | Role in the plan |
|----------------|------------------|
| Username + password login (`django-allauth`) | Remains the baseline / fallback |
| TOTP two-factor (authenticator app) | Already supported; biometrics becomes an *additional* option |
| Recovery codes | Remain as the account-recovery safety net |
| Brute-force lockout, failed-login logging | Unchanged; continues to protect the password step |
| "MFA required" site setting | Can be extended to accept biometrics as a valid second factor |

Because allauth already ships the WebAuthn module, we are **enabling and surfacing an existing
capability**, not bolting on a foreign system.

---

## 4. Data Privacy & Compliance (Data Privacy Act)

This is the most important section for management and is strongly in our favor:

- **No biometric data is collected or stored** by the CRM. Under the WebAuthn standard, the
  fingerprint/face is verified **on the user's device only**. Our database stores just a **public
  key and a credential ID** — random values that are useless to an attacker and are not personal
  biometric information.
- This significantly **reduces** our Data Privacy Act (RA 10173) exposure compared to any solution
  that would store fingerprints, because there is no sensitive biometric personal information held
  by the company.
- It also **strengthens** security posture: passkeys are **phishing-resistant** (they only work on
  our real domain) and eliminate password reuse/theft risk for enrolled users.

---

## 5. Feasibility Assessment

| Factor | Assessment |
|--------|------------|
| Technical feasibility | **High.** Native allauth WebAuthn module + `fido2` already installed. |
| Custom code required | **Low.** Mostly settings, URL exposure, and a small enrollment UI on the profile page. |
| New third-party services | **None.** No paid vendor, no external biometric service. |
| Server hardware/biometric readers | **None.** Uses each employee's existing device sensors. |
| Requires HTTPS | **Already satisfied** — production runs on `https://micrm.microimageph.com`. WebAuthn requires HTTPS, which we have. |
| Migration/DB impact | **Minimal.** allauth manages its own credential storage via its migrations. |

### Prerequisites (all already met or trivial)
- HTTPS in production ✅ (confirmed)
- allauth + fido2 installed ✅ (confirmed: allauth 65.18, fido2 2.2)
- Modern browsers (Safari, Edge, Chrome, Firefox) — all support WebAuthn ✅
- Devices with a biometric sensor OR a security key — most staff laptops/phones qualify ✅

---

## 6. Device & Browser Support

| Platform | Biometric method | Supported |
|----------|------------------|-----------|
| iPhone / iPad (Safari) | Face ID / Touch ID | ✅ |
| Mac (Safari/Chrome) | Touch ID | ✅ |
| Windows 10/11 (Edge/Chrome) | Windows Hello (fingerprint/face/PIN) | ✅ |
| Android (Chrome) | Fingerprint / face unlock | ✅ |
| Any device | Physical security key (YubiKey, etc.) | ✅ optional |

**Fallback:** Any employee whose device lacks biometrics continues to use password (+ optional TOTP)
exactly as today. Biometrics is **opt-in per user**, not forced.

---

## 7. Proposed Rollout (Phased)

### Phase 1 — Enable & Pilot (recommended first step)
- Enable the WebAuthn/passkey option in allauth configuration.
- Add a "Register this device (Fingerprint / Face ID)" button on the existing **Profile → Security**
  page (next to the current TOTP setup).
- Pilot with a small group (e.g. IT + a few managers) on their own devices.
- Password + recovery codes remain fully functional throughout.

### Phase 2 — Company Rollout
- Short how-to guide for staff (1 page + screenshots) on enrolling their device.
- Encourage enrollment; keep it optional.
- Monitor adoption and any support issues via the existing login logs.

### Phase 3 — Optional Hardening (management decision, later)
- Optionally allow biometrics to satisfy the existing "MFA required" policy.
- Optionally allow **passwordless** login for enrolled devices (password becomes the fallback).
- These are policy choices to revisit **after** the pilot proves stable.

---

## 8. Effort & Impact Estimate

| Work item | Estimated effort |
|-----------|------------------|
| Configure allauth WebAuthn (settings, URLs) | 0.5 day |
| Enrollment UI on Profile → Security page | 1 day |
| Login-page "Sign in with biometrics" option | 0.5 day |
| Testing across Safari/Edge/Chrome + devices | 1 day |
| Staff guide + internal documentation | 0.5 day |
| **Total** | **~3.5 days** |

- **Downtime:** None expected (additive feature; existing login untouched).
- **Cost:** No licensing/vendor cost. Uses existing libraries and staff devices.
- **Risk:** Low. Password login remains the guaranteed fallback; recovery codes remain the safety net.

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Employee loses/replaces enrolled device | Password + recovery codes still work; they simply re-enroll the new device. |
| Older device without biometrics | Falls back to password (+ optional TOTP) — no one is locked out. |
| User confusion during rollout | Opt-in, phased pilot + a simple 1-page guide before company-wide rollout. |
| Admin portal access | Unaffected — admin remains behind its existing network/IP restriction. |

---

## 10. Recommendation

We recommend **approving Phase 1 (Enable & Pilot).** It is low-effort, uses capabilities already
present in the system, introduces **no new biometric-data privacy liability**, and measurably
improves login security (phishing-resistant passkeys) — while keeping the current password login as
a safe fallback for everyone.

Upon approval, the development team will implement Phase 1, pilot internally, and report back before
any company-wide rollout or policy change (Phases 2–3).

---

## 11. Approval

| Role | Name | Decision (Approve / Revise / Reject) | Date |
|------|------|--------------------------------------|------|
| IT / Development Lead | | | |
| Operations / Management | | | |
| Data Privacy Officer (if applicable) | | | |

---

### Appendix A — Technical Notes (for IT reference)

- **Protocol:** WebAuthn / FIDO2 (W3C standard).
- **Library:** `django-allauth` `allauth.mfa.webauthn` (v65.18 installed), backed by `fido2` (v2.2 installed).
- **Data stored server-side:** credential ID + public key + sign counter per registered authenticator
  (managed by allauth's `Authenticator` model). **No biometric templates.**
- **Config additions (Phase 1):** add `'webauthn'` (and optionally `'webauthn'` as a passkey login
  method) to `MFA_SUPPORTED_TYPES`, expose the allauth MFA URLs already included, and add the
  enrollment control to the profile Security section.
- **Requirement:** HTTPS + a stable domain (Relying Party ID = `micrm.microimageph.com`) — already in place.
- **No change** to the REST API token auth used by the Android app.
