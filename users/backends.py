"""
Custom authentication backend with brute force protection.
Wraps Django's ModelBackend and checks lockout status before authenticating.
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

from .signals import is_account_locked

User = get_user_model()


class LockoutAwareBackend(ModelBackend):
    """
    Authentication backend that refuses to authenticate locked accounts.
    Replaces Django's default ModelBackend in settings.AUTHENTICATION_BACKENDS.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username:
            return None

        # Check lockout BEFORE attempting password verification
        locked, minutes_remaining = is_account_locked(username)
        if locked:
            # Return None = authentication fails.
            # The signal will log it with reason='account_locked'.
            return None

        # Proceed with normal authentication
        return super().authenticate(request, username=username, password=password, **kwargs)
