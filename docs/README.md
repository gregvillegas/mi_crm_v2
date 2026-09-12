All readme files are in folder "docs"
python modules requirements are in folder "dependencies"


Summary

I've resolved both of your issues:

✅ Issue 1: Admin Portal Login Fixed
•  Problem: The 'admin' user wasn't configured as a Django superuser
•  Solution: Updated the admin user to have is_superuser=True and is_staff=True, and ensured the password is properly hashed
•  Credentials: Username: admin, Password: admin123

✅ Issue 2: Team Creation Fixed  
•  Problem: Team creation requires an AVP user, but only admin role existed
•  Solution: Created an AVP user that can be assigned to teams
•  New AVP User: Username: avp_user, Password: avp123

Additional Users Created
I also created additional users to help you test the complete team hierarchy:
•  Supervisor: Username: supervisor_user, Password: supervisor123
•  Salesperson: Username: salesperson_user, Password: sales123

Current User List
How to Test

1. Admin Portal: Visit http://127.0.0.1:8000/admin/ and login with:
•  Username: admin
•  Password: admin123
2. Team Creation: Now you can create teams because you have an AVP user (avp_user) available to assign as the team manager.
3. Complete Workflow: You can now test the full hierarchy:
•  Admin creates teams and assigns AVP users
•  Teams can have groups managed by supervisors  
•  Salespeople can be assigned to groups

The system should now work as expected for both admin access and team management functionality.


---

## Feature Guides

- **[CUSTOMERS_APP.md](CUSTOMERS_APP.md)** — How the Customers app works, with a deep dive on duplicate management (normalization, similarity scoring, the "Show Duplicates" filter) and how the create-request approval workflow notifies the AVP/approvers. References the merge design in CUSTOMER_MERGE_ANALYSIS.md.
- **[CUSTOMER_MERGE_ANALYSIS.md](CUSTOMER_MERGE_ANALYSIS.md)** — Design/feasibility analysis for merging duplicate customers (not yet implemented).

## Proposals (for review/approval)

- **[PROPOSAL_REJECTION_HANDLING.md](PROPOSAL_REJECTION_HANDLING.md)** — What happens to a rejected sales proposal (it can be edited, and editing auto-resets the approval workflow), the edge cases (e.g. trimming under the ₱500K threshold bypasses approval), and proposed options for management sign-off.
- **[PROPOSAL_OPTIONAL_ITEMS_APPROVAL.md](PROPOSAL_OPTIONAL_ITEMS_APPROVAL.md)** — Why proposals whose value comes from "Optional" line items skip the ₱500K approval threshold (optional items are excluded from the binding total used for approval), with options for management sign-off.
- **[BIOMETRIC_AUTHENTICATION_PROPOSAL.md](BIOMETRIC_AUTHENTICATION_PROPOSAL.md)** — Feasibility & phased implementation plan for biometric login (WebAuthn/Passkeys via existing django-allauth). For management review and sign-off; no code changed yet.
- **[BIOMETRIC_ENROLLMENT_STAFF_GUIDE.md](BIOMETRIC_ENROLLMENT_STAFF_GUIDE.md)** — 1-page staff how-to for enrolling a device (Touch ID / Face ID / Windows Hello / Android) and signing in with biometrics. Ready for the Phase 1 pilot once approved.

## Maintenance & Operations

- **[ACTIVITY_LOG_ARCHIVING.md](ACTIVITY_LOG_ARCHIVING.md)** — Archive old `UserActivityLog` records to compressed files (and restore them later) to keep the database lean. Includes the `archive_activity_logs` management command and recommended cron setup.
