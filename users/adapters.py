from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class MiCrmAccountAdapter(DefaultAccountAdapter):
    """
    Custom allauth account adapter.

    Overrides ONLY the "From" address used for account emails (password reset,
    etc.) so they come from a dedicated no-reply mailbox, without changing
    DEFAULT_FROM_EMAIL (which the rest of the CRM's emails still rely on).
    """

    def get_from_email(self):
        # Prefer a dedicated setting; fall back to Django's default if unset.
        return (
            getattr(settings, 'ACCOUNT_DEFAULT_FROM_EMAIL', None)
            or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
            or super().get_from_email()
        )
